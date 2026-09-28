"""Terminal Target: Monitors terminal builds, processes, or CLI outputs."""
from __future__ import annotations

import re
import time
from core.sentry.monitor.targets.base import MonitorTarget, TargetStatus

COMPLETION_PATTERNS = re.compile(
    r"\b(done|complete|completed|finished|succeeded|build succeeded|success|failed|failure|error|terminated)\b",
    re.I,
)


class TerminalTarget(MonitorTarget):
    """Monitors a terminal window or build session for completion/error signals."""

    def __init__(
        self,
        target_id: str = "terminal_default",
        name: str = "Terminal build",
        terminal_app: str = "terminal",
        pattern: str = "",
        interval_s: float = 3.0,
    ) -> None:
        super().__init__(target_id, name, interval_s)
        self.terminal_app = terminal_app
        self.pattern = re.compile(pattern, re.I) if pattern else COMPLETION_PATTERNS
        self._target_found = False

    def describe(self) -> str:
        return f"terminal '{self.name}' ({self.terminal_app})"

    def poll(self) -> TargetStatus:
        self.last_poll_t = time.time()
        try:
            from actions.screen_processor import get_active_window_info
            info = get_active_window_info()
            app = info.get("app", "")
            title = info.get("title", "")

            # Check if current window matches terminal app or title keywords
            if self._matches_terminal(app, title):
                self._target_found = True
                m = self.pattern.search(title)
                if m:
                    match_word = m.group(0).lower()
                    if any(err in match_word for err in ("fail", "error")):
                        self._pending_alert = f"Sir, {self.name} encountered an error: {match_word}."
                    else:
                        self._pending_alert = f"Sir, {self.name} has finished."
                    self.status = TargetStatus.FINISHED
                    return self.status

            self.status = TargetStatus.RUNNING
            return self.status
        except Exception:
            self.status = TargetStatus.RUNNING
            return self.status

    def _matches_terminal(self, app: str, title: str) -> bool:
        low_app = (app or "").lower()
        low_title = (title or "").lower()
        terms = ("terminal", "powershell", "cmd", "bash", "zsh", "alacritty", "iterm", "wt", "conhost", "code")
        return any(t in low_app or t in low_title for t in terms) or (self.terminal_app.lower() in low_app)
