"""Focus Engine Core: Independent 1-second tick session thread.

Structural Privacy Law:
- All identifying tokens (app IDs, window titles, tab URLs, spoken labels, verbal intent)
  are strictly private to the engine instance and NEVER exported to FocusState.
- FocusState contains only booleans, counters, and progress integers.
- Session runs independently of the HUD lifecycle on a dedicated daemon thread.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

from core.sentry.focus.reader import BasePlatformReader, SurfaceIdentity, get_platform_reader
from core.sentry.focus.state import (
    DEFAULT_SESSION_MIN,
    MAX_SESSION_MIN,
    NAG_DEFAULT_S,
    NAG_MAX_S,
    NAG_MIN_S,
    SNOOZE_DEFAULT_S,
    TICK_INTERVAL_S,
    FocusState,
)
from core.sentry.mode_manager import get_sentry_mode_manager

_LOGGER = logging.getLogger(__name__)


class FocusEngine:
    """Manages a FOCUS mode session independent of UI lifecycles."""

    _instance: FocusEngine | None = None
    _instance_lock = threading.Lock()

    @classmethod
    def instance(cls) -> FocusEngine:
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(
        self,
        reader: BasePlatformReader | None = None,
        on_complete: Callable[[], None] | None = None,
        on_drift: Callable[[SurfaceIdentity, int], None] | None = None,
        auto_tick: bool = True,
    ) -> None:
        self._reader = reader or get_platform_reader()
        self._on_complete = on_complete
        self._on_drift = on_drift
        self._auto_tick = auto_tick

        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

        # Session timing
        self._active = False
        self._paused = False
        self._planned_s = DEFAULT_SESSION_MIN * 60
        self._elapsed_s = 0
        self._on_target_s = 0
        self._remaining_s = self._planned_s

        # Lock targets (PRIVATE: never exposed in FocusState)
        self._intent = ""
        self._target_app_id = ""
        self._target_tab_host_hash = ""
        self._deferred_lock = True
        self._locked_app = False
        self._locked_tab = False

        # Drift tracking
        self._drifting = False
        self._drift_count = 0
        self._current_drift_s = 0
        self._tier = 0
        self._snoozed_until_s = 0.0
        self._excused = False
        self._nag_interval_s = NAG_DEFAULT_S

    @property
    def is_active(self) -> bool:
        with self._lock:
            return self._active

    @property
    def is_paused(self) -> bool:
        with self._lock:
            return self._paused

    def set_reader(self, reader: BasePlatformReader) -> None:
        """Inject custom platform reader (used in unit tests)."""
        with self._lock:
            self._reader = reader

    def set_callbacks(
        self,
        on_complete: Callable[[], None] | None = None,
        on_drift: Callable[[SurfaceIdentity, int], None] | None = None,
    ) -> None:
        with self._lock:
            if on_complete is not None:
                self._on_complete = on_complete
            if on_drift is not None:
                self._on_drift = on_drift

    # ── Session Lifecycle ─────────────────────────────────────────────────────

    def start(
        self,
        duration_minutes: int = DEFAULT_SESSION_MIN,
        intent: str = "",
        lock_app: bool = False,
        lock_tab: bool = False,
    ) -> dict[str, Any]:
        """Start a new FOCUS session."""
        mins = max(1, min(duration_minutes, MAX_SESSION_MIN))
        planned_s = mins * 60

        with self._lock:
            self._active = True
            self._paused = False
            self._planned_s = planned_s
            self._elapsed_s = 0
            self._on_target_s = 0
            self._remaining_s = planned_s
            self._intent = (intent or "").strip()

            self._drifting = False
            self._drift_count = 0
            self._current_drift_s = 0
            self._tier = 0
            self._snoozed_until_s = 0.0
            self._excused = False
            self._nag_interval_s = NAG_DEFAULT_S

            # Settle rule / deferred lock by default
            self._deferred_lock = True
            self._locked_app = bool(lock_app)
            self._locked_tab = bool(lock_tab)
            self._target_app_id = ""
            self._target_tab_host_hash = ""

            if self._auto_tick and not self._running:
                self._running = True
                self._thread = threading.Thread(target=self._session_loop, name="sentry-focus-loop", daemon=True)
                self._thread.start()

        self._sync_mode_manager()
        return {
            "active": True,
            "planned_s": planned_s,
            "deferred_lock": self._deferred_lock,
            "locked_app": self._locked_app,
            "locked_tab": self._locked_tab,
        }

    def pause(self) -> None:
        with self._lock:
            if not self._active:
                return
            self._paused = True
        self._sync_mode_manager()

    def resume(self) -> None:
        with self._lock:
            if not self._active:
                return
            self._paused = False
        self._sync_mode_manager()

    def extend(self, minutes: int = 10) -> int:
        """Extend the current session by N minutes."""
        add_s = max(1, minutes) * 60
        with self._lock:
            if not self._active:
                return 0
            self._planned_s += add_s
            self._remaining_s += add_s
            remaining = self._remaining_s
        self._sync_mode_manager()
        return remaining

    def abort(self, reason: str = "Aborted by user.") -> dict[str, Any]:
        """Abort or stop the session cleanly."""
        with self._lock:
            if not self._active:
                return {"active": False, "reason": reason}
            self._active = False
            self._paused = False
            self._remaining_s = 0
            self._drifting = False
            self._current_drift_s = 0

        self._sync_mode_manager()
        return {"active": False, "reason": reason}

    def snooze(self, seconds: int = SNOOZE_DEFAULT_S) -> float:
        """Temporarily silence drift alerts for N seconds."""
        until = (time.time() + seconds) if seconds > 0 else 0.0
        with self._lock:
            self._snoozed_until_s = until
        self._sync_mode_manager()
        return until

    def excuse(self, reason: str = "Research") -> None:
        """Excuse current excursion, refunding drift time until back on target."""
        with self._lock:
            self._excused = True
            self._current_drift_s = 0
        self._sync_mode_manager()

    def set_nag_interval(self, seconds: int) -> int:
        """Tune nag cadence within [NAG_MIN_S, NAG_MAX_S]."""
        cadence = max(NAG_MIN_S, min(seconds, NAG_MAX_S))
        with self._lock:
            self._nag_interval_s = cadence
        self._sync_mode_manager()
        return cadence

    def lock_surface(self, app_id: str, tab_host_hash: str = "") -> None:
        """Explicitly lock the session onto a specific app / tab hash."""
        with self._lock:
            self._target_app_id = (app_id or "").strip().lower()
            self._target_tab_host_hash = (tab_host_hash or "").strip()
            self._locked_app = bool(self._target_app_id)
            self._locked_tab = bool(self._target_tab_host_hash)
            self._deferred_lock = False
        self._sync_mode_manager()

    # ── State Whitelist Query ─────────────────────────────────────────────────

    def get_state(self) -> FocusState:
        """Return the immutable FocusState whitelist. Zero private strings."""
        with self._lock:
            return FocusState(
                active=self._active,
                paused=self._paused,
                deferred_lock=self._deferred_lock,
                locked_app=self._locked_app,
                locked_tab=self._locked_tab,
                planned_s=self._planned_s,
                elapsed_s=self._elapsed_s,
                on_target_s=self._on_target_s,
                remaining_s=self._remaining_s,
                drifting=self._drifting,
                drift_count=self._drift_count,
                current_drift_s=self._current_drift_s,
                tier=self._tier,
                snoozed_until_s=self._snoozed_until_s,
                excused=self._excused,
                nag_interval_s=self._nag_interval_s,
                intent_set=bool(self._intent),
            )

    # ── 1 Hz Engine Loop ──────────────────────────────────────────────────────

    def _session_loop(self) -> None:
        while True:
            time.sleep(TICK_INTERVAL_S)
            with self._lock:
                if not self._running:
                    break
                active = self._active
                paused = self._paused

            if active and not paused:
                self.tick()

    def tick(self) -> None:
        """Execute a single 1-second session tick."""
        complete_cb = None
        drift_cb = None

        with self._lock:
            if not self._active or self._paused:
                return

            self._elapsed_s += 1
            self._remaining_s = max(0, self._planned_s - self._elapsed_s)

            if self._remaining_s == 0:
                self._active = False
                complete_cb = self._on_complete
                self._sync_mode_manager_locked()
                if complete_cb:
                    try:
                        complete_cb()
                    except Exception as exc:
                        _LOGGER.debug("Complete callback error: %s", exc)
                return

            # Query the frontmost surface afresh
            surface = self._reader.get_frontmost_surface()

            # Handle deferred lock on first non-home-base interaction
            if self._deferred_lock and not surface.is_home_base and surface.capability in ("FULL", "APP_ONLY"):
                self._target_app_id = surface.app_id
                self._target_tab_host_hash = surface.tab_host_hash
                self._locked_app = True
                self._locked_tab = bool(surface.tab_host_hash)
                self._deferred_lock = False

            # Comparison
            if surface.is_home_base or surface.capability == "UNKNOWN":
                # ALFRED HUD is home base: never a drift
                on_target = True
            elif not self._locked_app:
                # Still awaiting lock
                on_target = True
            else:
                app_ok = (surface.app_id.lower() == self._target_app_id.lower())
                tab_ok = True
                if self._locked_tab and self._target_tab_host_hash:
                    tab_ok = (surface.tab_host_hash == self._target_tab_host_hash)
                on_target = app_ok and tab_ok

            now = time.time()
            is_snoozed = (now < self._snoozed_until_s)

            if on_target:
                self._on_target_s += 1
                self._drifting = False
                self._current_drift_s = 0
                self._excused = False  # returning on-target clears excuse
            else:
                if not self._excused and not is_snoozed:
                    was_drifting = self._drifting
                    self._drifting = True
                    self._current_drift_s += 1
                    if not was_drifting:
                        self._drift_count += 1
                    drift_cb = self._on_drift

            self._sync_mode_manager_locked()

        if drift_cb and surface:
            try:
                drift_cb(surface, self._current_drift_s)
            except Exception as exc:
                _LOGGER.debug("Drift callback error: %s", exc)

    def _sync_mode_manager_locked(self) -> None:
        mgr = get_sentry_mode_manager()
        mgr.update_focus_state(
            active=self._active,
            paused=self._paused,
            deferred_lock=self._deferred_lock,
            locked_app=self._locked_app,
            locked_tab=self._locked_tab,
            planned_s=self._planned_s,
            elapsed_s=self._elapsed_s,
            on_target_s=self._on_target_s,
            remaining_s=self._remaining_s,
            drifting=self._drifting,
            drift_count=self._drift_count,
            current_drift_s=self._current_drift_s,
            tier=self._tier,
            snoozed_until_s=self._snoozed_until_s,
            excused=self._excused,
            nag_interval_s=self._nag_interval_s,
            intent_set=bool(self._intent),
        )

    def _sync_mode_manager(self) -> None:
        with self._lock:
            self._sync_mode_manager_locked()


def get_focus_engine() -> FocusEngine:
    """Convenience accessor for singleton FocusEngine."""
    return FocusEngine.instance()
