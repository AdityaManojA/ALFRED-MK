"""Focus Engine Core: Independent 1-second tick session thread with drift escalation.

Structural Privacy Law:
- Distraction labels ride for one engine tick into the spoken string and are stored NOWHERE.
- No app names, window titles, URLs, or spoken labels appear in FocusState, snapshot, or logs.
- FocusState contains only booleans, counters, and progress integers.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

from core.sentry.focus.labels import resolve_distraction_label
from core.sentry.focus.lines import get_drift_line
from core.sentry.focus.reader import BasePlatformReader, SurfaceIdentity, get_platform_reader
from core.sentry.focus.state import (
    DEFAULT_SESSION_MIN,
    DRIFT_GRACE_MS,
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
        speak_fn: Callable[[str], None] | None = None,
        on_complete: Callable[[], None] | None = None,
        on_drift: Callable[[SurfaceIdentity, int], None] | None = None,
        auto_tick: bool = True,
    ) -> None:
        self._reader = reader or get_platform_reader()
        self._speak_fn = speak_fn
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

        # Drift tracking & escalation
        self._drifting = False
        self._drift_count = 0
        self._current_drift_s = 0
        self._tier = 0
        self._snoozed_until_s = 0.0
        self._excused = False
        self._nag_interval_s = NAG_DEFAULT_S
        self._last_nag_time = 0.0
        self._first_callout_done = False
        self._drill_sergeant = False

        # Grace window tracking (DRIFT_GRACE_MS = 800)
        self._candidate_drift_start: float | None = None

    @property
    def is_active(self) -> bool:
        with self._lock:
            return self._active

    @property
    def is_paused(self) -> bool:
        with self._lock:
            return self._paused

    @property
    def is_drill_sergeant(self) -> bool:
        with self._lock:
            return self._drill_sergeant

    def set_reader(self, reader: BasePlatformReader) -> None:
        with self._lock:
            self._reader = reader

    def set_callbacks(
        self,
        speak_fn: Callable[[str], None] | None = None,
        on_complete: Callable[[], None] | None = None,
        on_drift: Callable[[SurfaceIdentity, int], None] | None = None,
    ) -> None:
        with self._lock:
            if speak_fn is not None:
                self._speak_fn = speak_fn
            if on_complete is not None:
                self._on_complete = on_complete
            if on_drift is not None:
                self._on_drift = on_drift

    def set_drill_sergeant(self, enabled: bool) -> bool:
        with self._lock:
            self._drill_sergeant = bool(enabled)
            return self._drill_sergeant

    # ── Session Lifecycle ─────────────────────────────────────────────────────

    def start(
        self,
        duration_minutes: int = DEFAULT_SESSION_MIN,
        intent: str = "",
        lock_app: bool = False,
        lock_tab: bool = False,
    ) -> dict[str, Any]:
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
            self._last_nag_time = 0.0
            self._first_callout_done = False
            self._candidate_drift_start = None

            # Settle rule / deferred lock
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
        with self._lock:
            if not self._active:
                return {"active": False, "reason": reason}
            self._active = False
            self._paused = False
            self._remaining_s = 0
            self._drifting = False
            self._current_drift_s = 0
            self._candidate_drift_start = None

        self._sync_mode_manager()
        return {"active": False, "reason": reason}

    def snooze(self, seconds: int = SNOOZE_DEFAULT_S) -> float:
        until = (time.time() + seconds) if seconds > 0 else 0.0
        with self._lock:
            self._snoozed_until_s = until
        self._sync_mode_manager()
        return until

    def excuse(self, reason: str = "Research") -> None:
        with self._lock:
            self._excused = True
            self._current_drift_s = 0
            self._candidate_drift_start = None
        self._sync_mode_manager()

    def set_nag_interval(self, seconds: int) -> int:
        cadence = max(NAG_MIN_S, min(seconds, NAG_MAX_S))
        with self._lock:
            self._nag_interval_s = cadence
        self._sync_mode_manager()
        return cadence

    def lock_surface(self, app_id: str, tab_host_hash: str = "") -> None:
        with self._lock:
            self._target_app_id = (app_id or "").strip().lower()
            self._target_tab_host_hash = (tab_host_hash or "").strip()
            self._locked_app = bool(self._target_app_id)
            self._locked_tab = bool(self._target_tab_host_hash)
            self._deferred_lock = False
            self._candidate_drift_start = None
        self._sync_mode_manager()

    # ── State Whitelist Query ─────────────────────────────────────────────────

    def get_state(self) -> FocusState:
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
        """Execute a single 1-second session tick with grace window and escalation."""
        complete_cb = None
        drift_cb = None
        spoken_line = ""

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

            # Settle rule: Deferred lock onto first non-home-base interaction
            if self._deferred_lock and not surface.is_home_base and surface.capability in ("FULL", "APP_ONLY"):
                self._target_app_id = surface.app_id
                self._target_tab_host_hash = surface.tab_host_hash
                self._locked_app = True
                self._locked_tab = bool(surface.tab_host_hash)
                self._deferred_lock = False

            # Comparison
            if surface.is_home_base or surface.capability == "UNKNOWN":
                on_target = True
            elif not self._locked_app:
                on_target = True
            else:
                app_ok = (surface.app_id.lower() == self._target_app_id.lower())
                tab_ok = True
                if self._locked_tab and self._target_tab_host_hash:
                    tab_ok = (surface.tab_host_hash == self._target_tab_host_hash)
                on_target = app_ok and tab_ok

            now_mono = time.monotonic()
            now_epoch = time.time()
            is_snoozed = (now_epoch < self._snoozed_until_s)

            if on_target:
                self._on_target_s += 1
                self._drifting = False
                self._current_drift_s = 0
                self._candidate_drift_start = None
                self._excused = False  # returning on target clears excuse
            else:
                # Potential drift: Apply grace window (DRIFT_GRACE_MS = 800)
                if self._candidate_drift_start is None:
                    self._candidate_drift_start = now_mono

                grace_elapsed_ms = (now_mono - self._candidate_drift_start) * 1000.0
                if grace_elapsed_ms >= DRIFT_GRACE_MS:
                    # Grace window passed: official drift confirmed
                    if not self._excused and not is_snoozed:
                        was_drifting = self._drifting
                        self._drifting = True
                        self._current_drift_s += 1

                        if not was_drifting:
                            self._drift_count += 1
                            # Tier escalation: 1 -> 2 -> 3
                            self._tier = min(3, self._drift_count)
                            should_callout = True
                        else:
                            # Repeating nag cadence
                            should_callout = (now_mono - self._last_nag_time) >= self._nag_interval_s

                        if should_callout:
                            self._last_nag_time = now_mono
                            label = resolve_distraction_label(surface)
                            is_first = not self._first_callout_done
                            spoken_line = get_drift_line(
                                tier=self._tier,
                                label=label,
                                intent=self._intent,
                                is_first=is_first,
                                drill_sergeant=self._drill_sergeant,
                            )
                            self._first_callout_done = True
                            drift_cb = self._on_drift

            self._sync_mode_manager_locked()

        # Speak callout (Privacy: label lives only in this ephemeral spoken string)
        if spoken_line and self._speak_fn:
            try:
                self._speak_fn(spoken_line)
            except Exception as exc:
                _LOGGER.debug("Speak error: %s", exc)

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
    return FocusEngine.instance()
