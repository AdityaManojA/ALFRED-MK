"""Linux Platform Reader: X11 and Wayland foreground inspector."""
from __future__ import annotations

import logging
import os
import re
import subprocess
from typing import Optional

from core.sentry.focus.reader import (
    BasePlatformReader,
    SurfaceIdentity,
    hash_host,
)

# ── Named Constants ──────────────────────────────────────────────────────────
CLI_TIMEOUT_S: float = 0.25
KNOWN_LINUX_BROWSERS = {
    "google-chrome": "Chrome",
    "chromium": "Chromium",
    "firefox": "Firefox",
    "brave-browser": "Brave",
    "microsoft-edge": "Edge",
}

_LOGGER = logging.getLogger(__name__)


class LinuxPlatformReader(BasePlatformReader):
    """Inspects frontmost window on Linux via X11 (xdotool/xprop) or Wayland IPC."""

    def __init__(self) -> None:
        self._is_wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
        self._own_pid = os.getpid()

    def get_frontmost_surface(self, from_card: bool = False) -> SurfaceIdentity:
        if self._is_wayland:
            return self._get_wayland_surface()
        return self._get_x11_surface()

    def _get_x11_surface(self) -> SurfaceIdentity:
        try:
            # 1. Get active window ID
            res = subprocess.run(["xdotool", "getactivewindow"], capture_output=True, text=True, timeout=CLI_TIMEOUT_S)
            if res.returncode != 0:
                return SurfaceIdentity(capability="UNKNOWN")
            win_id = res.stdout.strip()

            # 2. Get window PID
            pid_res = subprocess.run(["xdotool", "getwindowpid", win_id], capture_output=True, text=True, timeout=CLI_TIMEOUT_S)
            pid = int(pid_res.stdout.strip()) if pid_res.returncode == 0 and pid_res.stdout.strip().isdigit() else -1

            if pid == self._own_pid:
                return SurfaceIdentity(
                    app_id="alfred",
                    is_home_base=True,
                    is_self=True,
                    spoken_label="ALFRED",
                    capability="FULL",
                )

            # 3. Get window title & WM_CLASS
            name_res = subprocess.run(["xdotool", "getwindowname", win_id], capture_output=True, text=True, timeout=CLI_TIMEOUT_S)
            title = name_res.stdout.strip() if name_res.returncode == 0 else ""

            prop_res = subprocess.run(["xprop", "-id", win_id, "WM_CLASS"], capture_output=True, text=True, timeout=CLI_TIMEOUT_S)
            app_id = "unknown"
            if prop_res.returncode == 0 and "=" in prop_res.stdout:
                # e.g. WM_CLASS(STRING) = "google-chrome", "Google-chrome"
                parts = re.findall(r'"([^"]+)"', prop_res.stdout)
                if parts:
                    app_id = parts[0].lower()

            is_browser = any(b in app_id for b in KNOWN_LINUX_BROWSERS)
            spoken_label = KNOWN_LINUX_BROWSERS.get(app_id, app_id.capitalize())

            tab_host_hash = ""
            capability = "APP_ONLY"
            if is_browser and title:
                # Extract domain heuristic from title
                match = re.search(r"\b([a-zA-Z0-9\-]+\.(?:com|org|io|dev|net|ai|edu|gov))\b", title, re.I)
                if match:
                    tab_host_hash = hash_host(match.group(1))
                    capability = "FULL"

            return SurfaceIdentity(
                app_id=app_id,
                tab_host_hash=tab_host_hash,
                is_home_base=False,
                is_browser=is_browser,
                is_self=False,
                spoken_label=spoken_label,
                capability=capability,
                raw_title=title,
            )
        except Exception as exc:
            _LOGGER.debug("Linux X11 query error: %s", exc)
            return SurfaceIdentity(capability="UNKNOWN")

    def _get_wayland_surface(self) -> SurfaceIdentity:
        # Wayland compositor query (swaymsg or hyprctl fallback)
        try:
            res = subprocess.run(["hyprctl", "activewindow", "-j"], capture_output=True, text=True, timeout=CLI_TIMEOUT_S)
            if res.returncode == 0:
                import json
                data = json.loads(res.stdout)
                app_id = data.get("class", "").lower()
                pid = data.get("pid", -1)
                title = data.get("title", "")

                if pid == self._own_pid:
                    return SurfaceIdentity(app_id="alfred", is_home_base=True, is_self=True, capability="FULL")

                is_browser = any(b in app_id for b in KNOWN_LINUX_BROWSERS)
                tab_host_hash = ""
                if is_browser and title:
                    match = re.search(r"\b([a-zA-Z0-9\-]+\.(?:com|org|io|dev|net|ai|edu|gov))\b", title, re.I)
                    if match:
                        tab_host_hash = hash_host(match.group(1))

                return SurfaceIdentity(
                    app_id=app_id,
                    tab_host_hash=tab_host_hash,
                    is_home_base=False,
                    is_browser=is_browser,
                    is_self=False,
                    spoken_label=app_id.capitalize(),
                    capability="FULL" if tab_host_hash else "APP_ONLY",
                    raw_title=title,
                )
        except Exception:
            pass

        return SurfaceIdentity(capability="APP_ONLY")
