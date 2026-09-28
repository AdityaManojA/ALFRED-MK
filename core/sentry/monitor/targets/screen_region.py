"""Screen Region Target: Reuses existing screen capture facility for change detection."""
from __future__ import annotations

import time
from core.sentry.monitor.targets.base import MonitorTarget, TargetStatus


class ScreenRegionTarget(MonitorTarget):
    """Reuses actions.screen_processor.capture_screen to monitor display changes."""

    def __init__(
        self,
        target_id: str = "screen_region",
        name: str = "Screen region",
        monitor_id: int = 1,
        goal: str = "",
        interval_s: float = 5.0,
    ) -> None:
        super().__init__(target_id, name, interval_s)
        self.monitor_id = monitor_id
        self.goal = goal
        self._last_hash = None

    def describe(self) -> str:
        return f"screen monitor {self.monitor_id} for '{self.goal or self.name}'"

    def poll(self) -> TargetStatus:
        self.last_poll_t = time.time()
        try:
            from actions.screen_processor import capture_screen
            obs = capture_screen(monitor=self.monitor_id)
            # Compare payload or image size hash
            img_bytes = obs.payload().get("image_bytes") if hasattr(obs, "payload") else b""
            if img_bytes:
                h = hash(img_bytes[:1024])
                if self._last_hash is not None and h != self._last_hash:
                    self._pending_alert = f"Sir, visual change detected for {self.name}."
                    self.status = TargetStatus.ALERTED
                    self._last_hash = h
                    return self.status
                self._last_hash = h

            self.status = TargetStatus.RUNNING
            return self.status
        except Exception:
            self.status = TargetStatus.RUNNING
            return self.status
