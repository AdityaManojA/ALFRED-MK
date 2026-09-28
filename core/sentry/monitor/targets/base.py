"""Base interfaces and data structures for MonitorTarget."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

MONITOR_DEFAULT_INTERVAL_S: float = 5.0


class TargetStatus(str, Enum):
    RUNNING = "running"
    ALERTED = "alerted"
    FINISHED = "finished"
    ERROR = "error"


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class TargetAlert:
    target_id: str
    message: str
    severity: AlertSeverity = AlertSeverity.INFO
    timestamp: float = 0.0


class MonitorTarget(ABC):
    """Abstract base class for all Sentry monitor targets."""

    def __init__(
        self,
        target_id: str,
        name: str,
        interval_s: float = MONITOR_DEFAULT_INTERVAL_S,
    ) -> None:
        self.target_id = target_id
        self.name = name
        self.interval_s = max(1.0, float(interval_s))
        self.last_poll_t = 0.0
        self.status = TargetStatus.RUNNING
        self._last_alert_message = ""
        self._pending_alert: str | None = None

    @abstractmethod
    def describe(self) -> str:
        """Terse human-readable description of what is being monitored."""
        ...

    @abstractmethod
    def poll(self) -> TargetStatus:
        """Poll the monitored surface once. Updates internal state and status."""
        ...

    def should_alert(self) -> tuple[bool, str]:
        """Returns (True, message) if an alert condition is met, then resets it."""
        if self._pending_alert:
            msg = self._pending_alert
            self._pending_alert = None
            self._last_alert_message = msg
            return True, msg
        return False, ""

    def close(self) -> None:
        """Release any platform resources, open handles, or subprocesses."""
        self.status = TargetStatus.FINISHED
