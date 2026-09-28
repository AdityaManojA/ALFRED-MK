"""Windows Platform Reader: Win32 + UI Automation frontmost inspector."""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import os
import re
from typing import Optional

import psutil

from core.sentry.focus.reader import (
    BasePlatformReader,
    SurfaceIdentity,
    extract_host_from_url,
    hash_host,
)

# ── Named Constants ──────────────────────────────────────────────────────────
KNOWN_BROWSERS = {
    "chrome.exe": "Chrome",
    "msedge.exe": "Edge",
    "brave.exe": "Brave",
    "firefox.exe": "Firefox",
    "opera.exe": "Opera",
    "vivaldi.exe": "Vivaldi",
    "arc.exe": "Arc",
}

_LOGGER = logging.getLogger(__name__)
user32 = ctypes.windll.user32


class WinPlatformReader(BasePlatformReader):
    """Inspects frontmost window on Windows via Win32 API and UI Automation."""

    def __init__(self) -> None:
        self._own_pid = os.getpid()

    def get_frontmost_surface(self, from_card: bool = False) -> SurfaceIdentity:
        """Query foreground HWND and active tab fresh every tick."""
        hwnd = user32.GetForegroundWindow()
        if not hwnd or hwnd == 0:
            return SurfaceIdentity(capability="UNKNOWN")

        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        proc_pid = pid.value

        # Home base check: if owned by our own process, it is ALFRED HUD
        if proc_pid == self._own_pid:
            return SurfaceIdentity(
                app_id="alfred",
                is_home_base=True,
                is_self=True,
                spoken_label="ALFRED",
                capability="FULL",
            )

        # Get executable name
        app_name = "unknown"
        try:
            proc = psutil.Process(proc_pid)
            app_name = proc.name().lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        # Read window title
        title = self._get_window_title(hwnd)
        is_browser = app_name in KNOWN_BROWSERS
        spoken_label = KNOWN_BROWSERS.get(app_name, app_name.replace(".exe", "").capitalize())

        tab_host_hash = ""
        capability = "APP_ONLY"

        if is_browser:
            host = self._extract_browser_host(hwnd, app_name, title)
            if host:
                tab_host_hash = hash_host(host)
                capability = "FULL"

        return SurfaceIdentity(
            app_id=app_name,
            tab_host_hash=tab_host_hash,
            is_home_base=False,
            is_browser=is_browser,
            is_self=False,
            spoken_label=spoken_label,
            capability=capability,
            raw_title=title,
        )

    def _get_window_title(self, hwnd: int) -> str:
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            return buf.value
        return ""

    def _extract_browser_host(self, hwnd: int, app_name: str, title: str) -> str:
        """Extract domain host using address bar reading or title heuristics."""
        # 1. Try title heuristic first (fastest, zero allocation)
        # e.g., 'GitHub - Where software is built - Google Chrome'
        # e.g., 'https://github.com/foo - Google Chrome'
        url_match = re.search(r"https?://([a-zA-Z0-9_\-\.]+)", title)
        if url_match:
            return url_match.group(1)

        # Domain title heuristic: check if title mentions known domains
        domain_match = re.search(r"\b([a-zA-Z0-9\-]+\.(?:com|org|io|dev|net|ai|edu|gov))\b", title, re.I)
        if domain_match:
            return domain_match.group(1)

        # 2. Try UI Automation address bar read if available
        host = self._read_uia_address_bar(hwnd)
        if host:
            return host

        # Fallback to general domain from title if recognisable site
        low_title = title.lower()
        if "youtube" in low_title:
            return "youtube.com"
        elif "github" in low_title:
            return "github.com"
        elif "stackoverflow" in low_title:
            return "stackoverflow.com"
        elif "reddit" in low_title:
            return "reddit.com"
        elif "twitter" in low_title or " x " in low_title:
            return "x.com"

        return ""

    def _read_uia_address_bar(self, hwnd: int) -> str:
        """Quick attempt to read Chrome/Edge address bar via UI Automation."""
        try:
            import uiautomation as auto
            ctrl = auto.ControlFromHandle(hwnd)
            if ctrl and ctrl.Exists(0, 0):
                # Search specifically for the address Edit control
                edit = ctrl.EditControl(searchDepth=6)
                if edit and edit.Exists(0, 0):
                    val = edit.GetValuePattern().Value
                    if val:
                        return extract_host_from_url(val)
        except Exception:
            pass
        return ""
