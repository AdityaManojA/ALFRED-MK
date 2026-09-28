"""Monitor Scheduler: Shared 1 Hz poll loop and alert manager."""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable

from core.sentry.monitor.targets.base import MonitorTarget, TargetStatus

MONITOR_SCHEDULER_TICK_S: float = 1.0
MONITOR_DEFAULT_INTERVAL_S: float = 5.0
MONITOR_ALERT_COOLDOWN_S: float = 15.0
MONITOR_MIN_COOLDOWN_S: float = 5.0
MONITOR_MAX_COOLDOWN_S: float = 120.0

_LOGGER = logging.getLogger(__name__)


class MonitorScheduler:
    """Coordinates polling across multiple MonitorTargets on one 1 Hz thread."""

    def __init__(
        self,
        on_alert: Callable[[str], None] | None = None,
        on_status: Callable[[str], None] | None = None,
        on_follow_up: Callable[[], None] | None = None,
    ) -> None:
        self._on_alert = on_alert
        self._on_status = on_status
        self._on_follow_up = on_follow_up

        self._lock = threading.Lock()
        self._targets: list[MonitorTarget] = []
        self._running = False
        self._thread: threading.Thread | None = None
        self._cooldown_s = MONITOR_ALERT_COOLDOWN_S
        self._last_alert_t = 0.0

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    @property
    def target_count(self) -> int:
        with self._lock:
            return len(self._targets)

    @property
    def cooldown(self) -> float:
        with self._lock:
            return self._cooldown_s

    def set_callbacks(
        self,
        on_alert: Callable[[str], None] | None = None,
        on_status: Callable[[str], None] | None = None,
        on_follow_up: Callable[[], None] | None = None,
    ) -> None:
        with self._lock:
            if on_alert is not None:
                self._on_alert = on_alert
            if on_status is not None:
                self._on_status = on_status
            if on_follow_up is not None:
                self._on_follow_up = on_follow_up

    def set_cooldown(self, seconds: float) -> float:
        with self._lock:
            self._cooldown_s = max(MONITOR_MIN_COOLDOWN_S, min(float(seconds), MONITOR_MAX_COOLDOWN_S))
            return self._cooldown_s

    def quieter(self) -> float:
        with self._lock:
            self._cooldown_s = min(MONITOR_MAX_COOLDOWN_S, self._cooldown_s + 15.0)
            return self._cooldown_s

    def louder(self) -> float:
        with self._lock:
            self._cooldown_s = max(MONITOR_MIN_COOLDOWN_S, self._cooldown_s - 10.0)
            return self._cooldown_s

    # ── Target Management ─────────────────────────────────────────────────────

    def add_target(self, target: MonitorTarget) -> None:
        with self._lock:
            self._targets.append(target)
            desc = ", ".join(t.describe() for t in self._targets)
        self._update_status(f"Monitoring: {desc}")

    def remove_target(self, target_id_or_name: str) -> bool:
        removed = False
        with self._lock:
            target_low = target_id_or_name.lower().strip()
            new_targets = []
            for t in self._targets:
                if t.target_id.lower() == target_low or target_low in t.name.lower():
                    t.close()
                    removed = True
                else:
                    new_targets.append(t)
            self._targets = new_targets

        if removed:
            with self._lock:
                desc = ", ".join(t.describe() for t in self._targets) if self._targets else "None"
            self._update_status(f"Monitoring: {desc}")
        return removed

    def clear_targets(self) -> None:
        with self._lock:
            for t in self._targets:
                t.close()
            self._targets.clear()
        self._update_status("Monitoring stopped")

    def describe_active(self) -> str:
        with self._lock:
            if not self._targets:
                return "Nothing is currently being monitored, sir."
            names = [t.describe() for t in self._targets]
        return f"Currently monitoring {len(names)} target(s): " + "; ".join(names) + "."

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._scheduler_loop, name="sentry-monitor-loop", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        thread = None
        with self._lock:
            if not self._running:
                return
            self._running = False
            thread = self._thread
            self._thread = None
            for t in self._targets:
                t.close()
            self._targets.clear()

        if thread and thread.is_alive() and threading.current_thread() != thread:
            thread.join(timeout=1.5)
        self._update_status("Monitoring off")

    # ── Polling Loop ──────────────────────────────────────────────────────────

    def _scheduler_loop(self) -> None:
        while True:
            with self._lock:
                if not self._running:
                    break
                targets_snapshot = list(self._targets)
                cooldown = self._cooldown_s

            now = time.time()
            finished_targets: list[MonitorTarget] = []

            for target in targets_snapshot:
                if target.status == TargetStatus.FINISHED:
                    finished_targets.append(target)
                    continue

                if (now - target.last_poll_t) >= target.interval_s:
                    try:
                        target.poll()
                    except Exception as exc:
                        _LOGGER.warning("Error polling target %s: %s", target.target_id, exc)

                    alert_needed, message = target.should_alert()
                    if alert_needed and message:
                        with self._lock:
                            last_alert = self._last_alert_t
                        if (now - last_alert) >= cooldown:
                            with self._lock:
                                self._last_alert_t = now
                            self._trigger_alert(message)
                        else:
                            _LOGGER.debug("Alert throttled by cooldown (%.1fs remaining): %s", cooldown - (now - last_alert), message)

                    if target.status == TargetStatus.FINISHED:
                        finished_targets.append(target)

            # Cleanup finished targets
            if finished_targets:
                with self._lock:
                    self._targets = [t for t in self._targets if t not in finished_targets]
                    remaining = len(self._targets)

                # Follow-up check when all targets complete
                if remaining == 0 and self._on_follow_up:
                    try:
                        self._on_follow_up()
                    except Exception as exc:
                        _LOGGER.debug("Follow-up error: %s", exc)

            time.sleep(MONITOR_SCHEDULER_TICK_S)

    def _trigger_alert(self, message: str) -> None:
        if self._on_alert:
            try:
                self._on_alert(message)
            except Exception as exc:
                _LOGGER.warning("Alert callback error: %s", exc)
        self._update_status(f"Alert: {message}")

    def _update_status(self, text: str) -> None:
        if self._on_status:
            try:
                self._on_status(text)
            except Exception:
                pass
