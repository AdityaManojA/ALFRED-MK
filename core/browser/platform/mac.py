"""
core/browser/platform/mac.py — macOS AppleScript / System Events browser driver.
"""
from __future__ import annotations

import logging
import subprocess
from typing import Optional

from core.browser.platform.base import BaseBrowserPlatformDriver, DEFAULT_TIMEOUT_S

# ── Named Constants ──────────────────────────────────────────────────────────
KNOWN_MAC_BROWSERS: dict[str, str] = {
    "com.google.Chrome": "Google Chrome",
    "com.brave.Browser": "Brave Browser",
    "com.microsoft.edgemac": "Microsoft Edge",
    "company.thebrowser.Browser": "Arc",
    "org.mozilla.firefox": "Firefox",
    "com.apple.Safari": "Safari",
    "com.operasoftware.Opera": "Opera",
}

_LOGGER = logging.getLogger(__name__)


class MacBrowserDriver(BaseBrowserPlatformDriver):
    """macOS driver using AppleScript front-browser targeting and System Events keystrokes."""

    def _run_osascript(self, script: str) -> tuple[bool, str]:
        try:
            res = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=DEFAULT_TIMEOUT_S,
            )
            return (res.returncode == 0, res.stdout.strip())
        except Exception as exc:
            _LOGGER.warning("[MacBrowserDriver] osascript failed: %s", exc)
            return (False, str(exc))

    def get_frontmost_browser(self) -> Optional[str]:
        script = 'tell application "System Events" to get bundle identifier of (first process whose frontmost is true)'
        ok, out = self._run_osascript(script)
        if ok and out in KNOWN_MAC_BROWSERS:
            return KNOWN_MAC_BROWSERS[out]
        return None

    def close_active_tab(self) -> bool:
        browser = self.get_frontmost_browser()
        if not browser:
            _LOGGER.debug("[MacBrowserDriver] Frontmost application is not a recognized browser.")
            return False

        # 1. Try clean AppleScript tab closure for supported browsers
        if browser in ("Google Chrome", "Brave Browser", "Microsoft Edge"):
            script = f'tell application "{browser}" to close active tab of front window'
            ok, _ = self._run_osascript(script)
            if ok:
                return True
        elif browser == "Safari":
            script = 'tell application "Safari" to close current tab of front window'
            ok, _ = self._run_osascript(script)
            if ok:
                return True

        # 2. Universal fallback: Cmd+W via System Events
        fallback_script = 'tell application "System Events" to keystroke "w" using command down'
        ok, _ = self._run_osascript(fallback_script)
        return ok

    def new_tab(self, url: Optional[str] = None) -> bool:
        if url:
            try:
                subprocess.run(["open", url], check=True, timeout=DEFAULT_TIMEOUT_S)
                return True
            except Exception as exc:
                _LOGGER.warning("[MacBrowserDriver] Failed to open URL %s: %s", url, exc)
                return False

        browser = self.get_frontmost_browser()
        if not browser:
            return False
        script = 'tell application "System Events" to keystroke "t" using command down'
        ok, _ = self._run_osascript(script)
        return ok

    def switch_tab(self, direction: str = "next") -> bool:
        browser = self.get_frontmost_browser()
        if not browser:
            return False
        if direction.lower() in ("prev", "previous", "back", "left"):
            script = 'tell application "System Events" to keystroke "[" using {command down, shift down}'
        else:
            script = 'tell application "System Events" to keystroke "]" using {command down, shift down}'
        ok, _ = self._run_osascript(script)
        return ok

    def reopen_closed_tab(self) -> bool:
        browser = self.get_frontmost_browser()
        if not browser:
            return False
        script = 'tell application "System Events" to keystroke "t" using {command down, shift down}'
        ok, _ = self._run_osascript(script)
        return ok

    def close_window(self) -> bool:
        browser = self.get_frontmost_browser()
        if not browser:
            return False
        script = 'tell application "System Events" to keystroke "w" using {command down, shift down}'
        ok, _ = self._run_osascript(script)
        return ok
