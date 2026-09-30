"""
core/browser/platform/win.py — Windows Win32 / UIA browser driver.
"""
from __future__ import annotations

import ctypes
import logging
import os
import time
from typing import Optional

from core.browser.platform.base import BaseBrowserPlatformDriver, DEFAULT_KEY_SETTLE_MS

# ── Named Constants ──────────────────────────────────────────────────────────
VK_SHIFT: int = 0x10
VK_CONTROL: int = 0x11
VK_MENU: int = 0x12       # Alt
VK_TAB: int = 0x09
VK_W: int = 0x57
VK_T: int = 0x54
VK_F4: int = 0x73

KEYEVENTF_KEYUP: int = 0x0002

KNOWN_WIN_BROWSERS: dict[str, str] = {
    "chrome.exe": "Chrome",
    "msedge.exe": "Edge",
    "brave.exe": "Brave",
    "firefox.exe": "Firefox",
    "opera.exe": "Opera",
    "operagx.exe": "Opera GX",
    "vivaldi.exe": "Vivaldi",
    "arc.exe": "Arc",
}

_LOGGER = logging.getLogger(__name__)


class WinBrowserDriver(BaseBrowserPlatformDriver):
    """Windows browser driver using targeted Win32 virtual keys and process inspection."""
    KNOWN_WIN_BROWSERS = KNOWN_WIN_BROWSERS

    def __init__(self) -> None:
        self._user32 = getattr(ctypes.windll, "user32", None)

    def _get_foreground_hwnd_and_proc(self) -> tuple[int, str]:
        if not self._user32:
            return 0, ""
        hwnd = self._user32.GetForegroundWindow()
        if not hwnd:
            return 0, ""
        pid = ctypes.c_ulong()
        self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return hwnd, ""
        try:
            import psutil
            name = psutil.Process(pid.value).name().lower()
            return hwnd, name
        except Exception:
            return hwnd, ""

    def get_frontmost_browser(self) -> Optional[str]:
        _, proc_name = self._get_foreground_hwnd_and_proc()
        if proc_name in KNOWN_WIN_BROWSERS:
            return KNOWN_WIN_BROWSERS[proc_name]
        return None

    def _send_keys(self, *vk_codes: int) -> bool:
        if not self._user32:
            return False
        try:
            # Key down in order
            for vk in vk_codes:
                self._user32.keybd_event(vk, 0, 0, 0)
            time.sleep(DEFAULT_KEY_SETTLE_MS / 1000.0)
            # Key up in reverse order
            for vk in reversed(vk_codes):
                self._user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
            return True
        except Exception as exc:
            _LOGGER.warning("[WinBrowserDriver] Key event failed: %s", exc)
            return False

    def close_active_tab(self) -> bool:
        """Send Ctrl+W to frontmost browser."""
        browser = self.get_frontmost_browser()
        if not browser:
            _LOGGER.debug("[WinBrowserDriver] Frontmost window is not a recognized browser.")
            return False
        return self._send_keys(VK_CONTROL, VK_W)

    def new_tab(self, url: Optional[str] = None) -> bool:
        """Send Ctrl+T to frontmost browser, or launch URL natively."""
        if url:
            try:
                os.startfile(url)
                return True
            except Exception as exc:
                _LOGGER.warning("[WinBrowserDriver] Failed to open URL %s: %s", url, exc)
                return False
        browser = self.get_frontmost_browser()
        if not browser:
            _LOGGER.debug("[WinBrowserDriver] Frontmost window is not a recognized browser.")
            return False
        return self._send_keys(VK_CONTROL, VK_T)

    def switch_tab(self, direction: str = "next") -> bool:
        """Send Ctrl+Tab (next) or Ctrl+Shift+Tab (prev)."""
        browser = self.get_frontmost_browser()
        if not browser:
            return False
        if direction.lower() in ("prev", "previous", "back", "left"):
            return self._send_keys(VK_CONTROL, VK_SHIFT, VK_TAB)
        return self._send_keys(VK_CONTROL, VK_TAB)

    def reopen_closed_tab(self) -> bool:
        """Send Ctrl+Shift+T."""
        browser = self.get_frontmost_browser()
        if not browser:
            return False
        return self._send_keys(VK_CONTROL, VK_SHIFT, VK_T)

    def close_window(self) -> bool:
        """Send Alt+F4."""
        browser = self.get_frontmost_browser()
        if not browser:
            return False
        return self._send_keys(VK_MENU, VK_F4)
