"""Clipboard Target: Monitors clipboard updates for matching patterns."""
from __future__ import annotations

import re
import time
from core.sentry.monitor.targets.base import MonitorTarget, TargetStatus


class ClipboardTarget(MonitorTarget):
    """Alerts when new clipboard content matches a regex pattern."""

    def __init__(
        self,
        target_id: str = "clipboard_monitor",
        name: str = "Clipboard Pattern",
        pattern: str = "",
        interval_s: float = 2.0,
    ) -> None:
        """Compile the optional case-insensitive pattern to match clipboard text against."""
        super().__init__(target_id, name, interval_s)
        self.regex = re.compile(pattern, re.I) if pattern else None
        self._last_text = ""

    def describe(self) -> str:
        """Describe the watched clipboard pattern ("any" when no pattern is set)."""
        return f"clipboard pattern '{self.regex.pattern if self.regex else 'any'}'"

    def poll(self) -> TargetStatus:
        """Read the clipboard; queue an alert when new text matches the pattern."""
        self.last_poll_t = time.time()
        try:
            import pyperclip
            current = pyperclip.paste() or ""
        except Exception:
            current = ""

        if current and current != self._last_text:
            self._last_text = current
            if self.regex and self.regex.search(current):
                m = self.regex.search(current).group(0)
                self._pending_alert = f"Sir, clipboard match: '{m[:40]}'."
                self.status = TargetStatus.ALERTED
                return self.status

        self.status = TargetStatus.RUNNING
        return self.status
