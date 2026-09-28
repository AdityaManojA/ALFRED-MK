"""File Log Target: Tails a file and alerts on regex or silence timeout."""
from __future__ import annotations

import os
import re
import time
from pathlib import Path
from core.sentry.monitor.targets.base import MonitorTarget, TargetStatus


class FileLogTarget(MonitorTarget):
    """Tails a file for regex matches or alerts on silence > N minutes."""

    def __init__(
        self,
        target_id: str,
        name: str,
        file_path: str | Path,
        pattern: str = "",
        silence_timeout_min: float = 0.0,
        interval_s: float = 4.0,
    ) -> None:
        super().__init__(target_id, name, interval_s)
        self.file_path = Path(file_path).resolve()
        self.regex = re.compile(pattern, re.I) if pattern else None
        self.silence_timeout_min = max(0.0, float(silence_timeout_min))
        self._last_offset = 0
        self._last_activity_t = time.time()

        if self.file_path.exists():
            try:
                self._last_offset = self.file_path.stat().st_size
                self._last_activity_t = self.file_path.stat().st_mtime
            except Exception:
                pass

    def describe(self) -> str:
        return f"log file '{self.file_path.name}'"

    def poll(self) -> TargetStatus:
        self.last_poll_t = time.time()
        if not self.file_path.exists():
            self.status = TargetStatus.RUNNING
            return self.status

        try:
            stat = self.file_path.stat()
            current_size = stat.st_size

            # Check silence timeout if enabled
            if self.silence_timeout_min > 0:
                elapsed_min = (time.time() - self._last_activity_t) / 60.0
                if elapsed_min >= self.silence_timeout_min:
                    self._pending_alert = f"Sir, {self.file_path.name} has been silent for {int(elapsed_min)} minutes."
                    self.status = TargetStatus.FINISHED
                    return self.status

            if current_size > self._last_offset:
                self._last_activity_t = time.time()
                with open(self.file_path, "r", encoding="utf-8", errors="ignore") as f:
                    f.seek(self._last_offset)
                    new_text = f.read()
                    self._last_offset = f.tell()

                if self.regex:
                    for line in new_text.splitlines():
                        m = self.regex.search(line)
                        if m:
                            self._pending_alert = f"Sir, log match in {self.file_path.name}: {m.group(0)[:50]}."
                            self.status = TargetStatus.ALERTED
                            return self.status

            self.status = TargetStatus.RUNNING
            return self.status
        except Exception:
            self.status = TargetStatus.RUNNING
            return self.status
