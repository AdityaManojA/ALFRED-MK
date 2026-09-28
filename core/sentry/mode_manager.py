"""Sentry Mode v2 Centralized Mode Manager (MONITOR + FOCUS).

Owns global state for both modes, exposes whitelisted snapshots, rate-limits
state change emissions to <= 1 Hz, and decouples mode orchestration from HUD widgets.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable

from PyQt6.QtCore import QObject, pyqtSignal

# ── Named Constants (Ground Rule: Every knob is named at the top) ─────────────
STATE_EMIT_INTERVAL_S: float = 1.0
MONITOR_DEFAULT_INTERVAL_S: float = 3.0
DEFAULT_SESSION_MIN: int = 25
MAX_SESSION_MIN: int = 180
SNOOZE_DEFAULT_S: int = 15
NAG_DEFAULT_S: int = 30

_LOGGER = logging.getLogger(__name__)


# ── Whitelist State Dataclasses (Ground Rule: Privacy is structural) ──────────

@dataclass(frozen=True, slots=True)
class MonitorState:
    """Whitelisted state for MONITOR mode.

    Contains no confidential strings, no raw window titles or command payloads.
    """
    active: bool = False
    target_count: int = 0
    last_alert_s: float = 0.0
    label: str = ""


@dataclass(frozen=True, slots=True)
class FocusState:
    """Whitelisted state for FOCUS mode.

    Contains only booleans, counters, and progress integers.
    The verbal user intent string is stored strictly on the session engine.
    """
    active: bool = False
    paused: bool = False
    deferred_lock: bool = False
    locked_app: bool = False
    locked_tab: bool = False
    planned_s: int = 0
    elapsed_s: int = 0
    on_target_s: int = 0
    remaining_s: int = 0
    drifting: bool = False
    drift_count: int = 0
    current_drift_s: int = 0
    tier: int = 0
    snoozed_until_s: float = 0.0
    excused: bool = False
    nag_interval_s: int = NAG_DEFAULT_S
    intent_set: bool = False


@dataclass(frozen=True, slots=True)
class SentrySnapshot:
    """Consolidated immutable snapshot of Sentry Mode state."""
    monitor: MonitorState
    focus: FocusState
    timestamp: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SentryModeManager(QObject):
    """Central singleton controller for Sentry Mode v2.

    Owned by the application lifecycle (JarvisLive), not by HUD widgets.
    """
    state_changed = pyqtSignal(object)  # Emits SentrySnapshot at most 1 Hz

    _instance: SentryModeManager | None = None
    _instance_lock = threading.Lock()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._lock = threading.Lock()
        self._monitor_state = MonitorState()
        self._focus_state = FocusState()
        self._last_emit_time = 0.0

        # Plug-in handlers for external mode drivers
        self._on_monitor_start: Callable[[str, float], dict[str, Any]] | None = None
        self._on_monitor_stop: Callable[[str], dict[str, Any]] | None = None
        self._on_focus_start: Callable[[int, str], dict[str, Any]] | None = None
        self._on_focus_stop: Callable[[str], dict[str, Any]] | None = None

    @classmethod
    def instance(cls) -> SentryModeManager:
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = SentryModeManager()
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Testing hook to clear singleton."""
        with cls._instance_lock:
            cls._instance = None

    # ── State Accessors ───────────────────────────────────────────────────────

    @property
    def monitor_state(self) -> MonitorState:
        with self._lock:
            return self._monitor_state

    @property
    def focus_state(self) -> FocusState:
        with self._lock:
            return self._focus_state

    def get_snapshot(self) -> SentrySnapshot:
        with self._lock:
            return SentrySnapshot(
                monitor=self._monitor_state,
                focus=self._focus_state,
                timestamp=time.time(),
            )

    # ── Handler Registration ──────────────────────────────────────────────────

    def register_monitor_handlers(
        self,
        on_start: Callable[[str, float], dict[str, Any]],
        on_stop: Callable[[str], dict[str, Any]],
    ) -> None:
        """Register callbacks for the MONITOR engine."""
        with self._lock:
            self._on_monitor_start = on_start
            self._on_monitor_stop = on_stop

    def register_focus_handlers(
        self,
        on_start: Callable[[int, str], dict[str, Any]],
        on_stop: Callable[[str], dict[str, Any]],
    ) -> None:
        """Register callbacks for the FOCUS engine."""
        with self._lock:
            self._on_focus_start = on_start
            self._on_focus_stop = on_stop

    # ── Mode Orchestration: MONITOR ───────────────────────────────────────────

    def start_monitor(
        self,
        goal: str = "",
        interval_seconds: float = MONITOR_DEFAULT_INTERVAL_S,
    ) -> dict[str, Any]:
        """Start MONITOR mode with an optional goal and polling cadence."""
        handler = None
        with self._lock:
            handler = self._on_monitor_start

        result: dict[str, Any] = {}
        if handler is not None:
            try:
                result = handler(goal, interval_seconds)
            except Exception as exc:
                _LOGGER.exception("Error in monitor start handler: %s", exc)
                result = {"active": False, "error": str(exc)}
        else:
            result = {"active": True, "label": "Screen/Terminal Monitoring"}

        active = bool(result.get("active", True))
        label = str(result.get("label", goal or "Active"))
        target_count = int(result.get("target_count", 1 if active else 0))

        with self._lock:
            self._monitor_state = MonitorState(
                active=active,
                target_count=target_count,
                last_alert_s=time.time(),
                label=label,
            )

        self._emit_state_change()
        return result

    def stop_monitor(self, reason: str = "Stopped by user.") -> dict[str, Any]:
        """Stop MONITOR mode."""
        handler = None
        with self._lock:
            handler = self._on_monitor_stop

        result: dict[str, Any] = {}
        if handler is not None:
            try:
                result = handler(reason)
            except Exception as exc:
                _LOGGER.exception("Error in monitor stop handler: %s", exc)
                result = {"active": False, "error": str(exc)}
        else:
            result = {"active": False, "label": "Monitoring Stopped"}

        with self._lock:
            self._monitor_state = MonitorState(
                active=False,
                target_count=0,
                last_alert_s=self._monitor_state.last_alert_s,
                label=reason,
            )

        self._emit_state_change()
        return result

    def toggle_monitor(self) -> dict[str, Any]:
        """Toggle MONITOR mode on or off."""
        if self.monitor_state.active:
            return self.stop_monitor("Toggled off from UI.")
        return self.start_monitor()

    def update_monitor_state(self, **kwargs: Any) -> None:
        """Update monitor state fields from target drivers."""
        with self._lock:
            cur = asdict(self._monitor_state)
            cur.update(kwargs)
            self._monitor_state = MonitorState(**cur)
        self._emit_state_change()

    # ── Mode Orchestration: FOCUS ─────────────────────────────────────────────

    def start_focus(
        self,
        duration_minutes: int = DEFAULT_SESSION_MIN,
        intent: str = "",
    ) -> dict[str, Any]:
        """Start FOCUS mode with session duration in minutes."""
        duration_minutes = max(1, min(duration_minutes, MAX_SESSION_MIN))
        planned_s = duration_minutes * 60

        handler = None
        with self._lock:
            handler = self._on_focus_start

        result: dict[str, Any] = {}
        if handler is not None:
            try:
                result = handler(duration_minutes, intent)
            except Exception as exc:
                _LOGGER.exception("Error in focus start handler: %s", exc)
                result = {"active": False, "error": str(exc)}
        else:
            result = {"active": True, "deferred_lock": True}

        active = bool(result.get("active", True))
        with self._lock:
            self._focus_state = FocusState(
                active=active,
                paused=False,
                deferred_lock=bool(result.get("deferred_lock", True)),
                locked_app=bool(result.get("locked_app", False)),
                locked_tab=bool(result.get("locked_tab", False)),
                planned_s=planned_s,
                elapsed_s=0,
                on_target_s=0,
                remaining_s=planned_s,
                drifting=False,
                drift_count=0,
                current_drift_s=0,
                tier=0,
                snoozed_until_s=0.0,
                excused=False,
                nag_interval_s=NAG_DEFAULT_S,
                intent_set=bool(intent.strip()),
            )

        self._emit_state_change()
        return result

    def stop_focus(self, reason: str = "Stopped by user.") -> dict[str, Any]:
        """Stop FOCUS mode."""
        handler = None
        with self._lock:
            handler = self._on_focus_stop

        result: dict[str, Any] = {}
        if handler is not None:
            try:
                result = handler(reason)
            except Exception as exc:
                _LOGGER.exception("Error in focus stop handler: %s", exc)
                result = {"active": False, "error": str(exc)}
        else:
            result = {"active": False, "reason": reason}

        with self._lock:
            self._focus_state = FocusState(
                active=False,
                paused=False,
                deferred_lock=False,
                locked_app=False,
                locked_tab=False,
                planned_s=self._focus_state.planned_s,
                elapsed_s=self._focus_state.elapsed_s,
                on_target_s=self._focus_state.on_target_s,
                remaining_s=0,
                drifting=False,
                drift_count=self._focus_state.drift_count,
                current_drift_s=0,
                tier=0,
                snoozed_until_s=0.0,
                excused=False,
                nag_interval_s=self._focus_state.nag_interval_s,
                intent_set=False,
            )

        self._emit_state_change()
        return result

    def toggle_focus(self) -> dict[str, Any]:
        """Toggle FOCUS mode on or off."""
        if self.focus_state.active:
            return self.stop_focus("Toggled off from UI.")
        return self.start_focus()

    def update_focus_state(self, **kwargs: Any) -> None:
        """Update focus state fields from engine ticks."""
        with self._lock:
            cur = asdict(self._focus_state)
            cur.update(kwargs)
            self._focus_state = FocusState(**cur)
        self._emit_state_change()

    # ── Rate-Limited Signal Emission (Ground Rule: <= 1 Hz) ───────────────────

    def _emit_state_change(self, force: bool = False) -> None:
        """Emit state_changed signal respecting the 1 Hz rate limit."""
        now = time.monotonic()
        with self._lock:
            if not force and (now - self._last_emit_time) < STATE_EMIT_INTERVAL_S:
                return
            self._last_emit_time = now
            snapshot = SentrySnapshot(
                monitor=self._monitor_state,
                focus=self._focus_state,
                timestamp=time.time(),
            )

        # Qt signal emission outside the mutex
        try:
            self.state_changed.emit(snapshot)
        except Exception as exc:
            _LOGGER.debug("Could not emit state_changed signal: %s", exc)


def get_sentry_mode_manager() -> SentryModeManager:
    """Convenience accessor for the global singleton."""
    return SentryModeManager.instance()
