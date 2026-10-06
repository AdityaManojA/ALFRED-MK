"""
core/browser/platform/linux.py — Linux X11 / Wayland browser driver.
"""
from __future__ import annotations

import logging
import os
import subprocess
from typing import Optional

from core.browser.platform.base import (
    BaseBrowserPlatformDriver,
    DEFAULT_TIMEOUT_S,
    normalize_tab_query,
    tab_matches_query,
)

# ── Named Constants ──────────────────────────────────────────────────────────
KNOWN_LINUX_BROWSERS: dict[str, str] = {
    "google-chrome": "Chrome",
    "chromium": "Chromium",
    "chromium-browser": "Chromium",
    "firefox": "Firefox",
    "brave-browser": "Brave",
    "microsoft-edge": "Edge",
    "opera": "Opera",
    "vivaldi": "Vivaldi",
}

_LOGGER = logging.getLogger(__name__)


class LinuxBrowserDriver(BaseBrowserPlatformDriver):
    """Linux driver using xdotool / wmctrl / xdg-open."""

    def __init__(self) -> None:
        self._is_wayland = bool(os.environ.get("WAYLAND_DISPLAY"))

    def _get_active_window_info(self) -> tuple[int, str]:
        """Return (window_id, process_or_class_name)."""
        try:
            res = subprocess.run(["xdotool", "getactivewindow"], capture_output=True, text=True, timeout=DEFAULT_TIMEOUT_S)
            if res.returncode != 0:
                return 0, ""
            wid_str = res.stdout.strip()
            wid = int(wid_str)
            # Query class name
            res_cls = subprocess.run(["xprop", "-id", wid_str, "WM_CLASS"], capture_output=True, text=True, timeout=DEFAULT_TIMEOUT_S)
            cls_out = res_cls.stdout.lower() if res_cls.returncode == 0 else ""
            return wid, cls_out
        except Exception:
            return 0, ""

    def get_frontmost_browser(self) -> Optional[str]:
        _, cls_out = self._get_active_window_info()
        for k, v in KNOWN_LINUX_BROWSERS.items():
            if k in cls_out:
                return v
        return None

    def _send_xdotool_key(self, key_combo: str) -> bool:
        wid, _ = self._get_active_window_info()
        cmd = ["xdotool", "key"]
        if wid > 0:
            cmd.extend(["--window", str(wid)])
        cmd.append(key_combo)
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=DEFAULT_TIMEOUT_S)
            return res.returncode == 0
        except Exception:
            try:
                import pyautogui
                keys = [k.strip() for k in key_combo.lower().split("+")]
                pyautogui.hotkey(*keys)
                return True
            except Exception as exc:
                _LOGGER.warning("[LinuxBrowserDriver] Key send failed: %s", exc)
                return False

    def close_active_tab(self) -> bool:
        browser = self.get_frontmost_browser()
        if not browser:
            _LOGGER.debug("[LinuxBrowserDriver] Frontmost window is not a recognized browser.")
            return False
        return self._send_xdotool_key("ctrl+w")

    def close_tab_matching(self, query: str, browser: Optional[str] = None) -> bool:
        """Find and close a tab matching query in specified or frontmost browser on Linux."""
        candidates = normalize_tab_query(query)
        if not candidates:
            return False

        try:
            res = subprocess.run(
                ["wmctrl", "-l"],
                capture_output=True,
                text=True,
                timeout=DEFAULT_TIMEOUT_S,
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    parts = line.split(None, 3)
                    if len(parts) >= 4:
                        wid_hex, _, _, title = parts
                        if tab_matches_query(title, candidates):
                            subprocess.run(
                                ["wmctrl", "-i", "-a", wid_hex],
                                check=False,
                                timeout=DEFAULT_TIMEOUT_S,
                            )
                            return self._send_xdotool_key("ctrl+w")
        except Exception as exc:
            _LOGGER.debug("[LinuxBrowserDriver] wmctrl tab match failed: %s", exc)

        return False

    def new_tab(self, url: Optional[str] = None) -> bool:
        if url:
            try:
                subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except Exception as exc:
                _LOGGER.warning("[LinuxBrowserDriver] xdg-open failed: %s", exc)
                return False
        browser = self.get_frontmost_browser()
        if not browser:
            return False
        return self._send_xdotool_key("ctrl+t")

    def switch_tab(self, direction: str = "next") -> bool:
        browser = self.get_frontmost_browser()
        if not browser:
            return False
        if direction.lower() in ("prev", "previous", "back", "left"):
            return self._send_xdotool_key("ctrl+shift+Tab")
        return self._send_xdotool_key("ctrl+Tab")

    def reopen_closed_tab(self) -> bool:
        browser = self.get_frontmost_browser()
        if not browser:
            return False
        return self._send_xdotool_key("ctrl+shift+t")

    def close_window(self) -> bool:
        browser = self.get_frontmost_browser()
        if not browser:
            return False
        return self._send_xdotool_key("alt+F4")
