"""Window Title Target: Monitors applications and windows for specific title regex."""
from __future__ import annotations

import re
import sys
import time
from core.sentry.monitor.targets.base import MonitorTarget, TargetStatus


class WindowTitleTarget(MonitorTarget):
    """Alerts when a specific window or application title matches a regex pattern."""

    def __init__(
        self,
        target_id: str,
        name: str,
        app_name: str = "",
        title_pattern: str = "",
        alert_on_close: bool = False,
        interval_s: float = 3.0,
    ) -> None:
        super().__init__(target_id, name, interval_s)
        self.app_name = (app_name or "").strip()
        self.pattern_str = title_pattern or ""
        self.regex = re.compile(title_pattern, re.I) if title_pattern else None
        self.alert_on_close = alert_on_close
        self._was_present = False

    def describe(self) -> str:
        desc = f"window '{self.app_name or 'any'}'"
        if self.pattern_str:
            desc += f" title matching '{self.pattern_str}'"
        return desc

    def poll(self) -> TargetStatus:
        self.last_poll_t = time.time()
        try:
            titles = self._get_matching_window_titles()
            if not titles:
                if self._was_present and self.alert_on_close:
                    self._pending_alert = f"Sir, {self.app_name or self.name} has closed."
                    self.status = TargetStatus.FINISHED
                    return self.status
                self.status = TargetStatus.RUNNING
                return self.status

            self._was_present = True
            for title in titles:
                if self.regex and self.regex.search(title):
                    m = self.regex.search(title).group(0)
                    self._pending_alert = f"Sir, {self.app_name or 'Window'} title says '{m}'."
                    self.status = TargetStatus.FINISHED
                    return self.status

            self.status = TargetStatus.RUNNING
            return self.status
        except Exception:
            self.status = TargetStatus.RUNNING
            return self.status

    def _get_matching_window_titles(self) -> list[str]:
        """Query open window titles matching app_name across operating systems."""
        titles: list[str] = []
        low_app = self.app_name.lower()

        # Check foreground window first via existing screen_processor
        try:
            from actions.screen_processor import get_active_window_info
            info = get_active_window_info()
            fg_app = info.get("app", "")
            fg_title = info.get("title", "")
            if not low_app or low_app in fg_app.lower() or low_app in fg_title.lower():
                titles.append(fg_title)
        except Exception:
            pass

        # Windows: EnumWindows for background window inspection
        if sys.platform.startswith("win"):
            try:
                import win32gui
                def _enum(hwnd, _):
                    if win32gui.IsWindowVisible(hwnd):
                        t = win32gui.GetWindowText(hwnd)
                        if t and (not low_app or low_app in t.lower()):
                            titles.append(t)
                win32gui.EnumWindows(_enum, None)
            except Exception:
                pass

        return list(dict.fromkeys(titles))
