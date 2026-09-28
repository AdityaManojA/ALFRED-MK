"""macOS Platform Reader: AppleScript and CLI frontmost inspector."""
from __future__ import annotations

import logging
import os
import subprocess
from typing import Optional

from core.sentry.focus.reader import (
    BasePlatformReader,
    SurfaceIdentity,
    extract_host_from_url,
    hash_host,
)

# ── Named Constants ──────────────────────────────────────────────────────────
CLI_TIMEOUT_S: float = 0.25
KNOWN_MAC_BROWSERS = {
    "com.google.Chrome": "Google Chrome",
    "com.brave.Browser": "Brave Browser",
    "com.microsoft.edgemac": "Microsoft Edge",
    "company.thebrowser.Browser": "Arc",
    "org.mozilla.firefox": "Firefox",
}

_LOGGER = logging.getLogger(__name__)


class MacPlatformReader(BasePlatformReader):
    """Inspects frontmost application on macOS via lsappinfo / osascript."""

    def __init__(self) -> None:
        self._own_pid = os.getpid()

    def get_frontmost_surface(self, from_card: bool = False) -> SurfaceIdentity:
        # 1. Frontmost app bundle ID via lsappinfo
        bundle_id, app_name = self._get_frontmost_app()
        if not bundle_id:
            return SurfaceIdentity(capability="UNKNOWN")

        if "alfred" in bundle_id.lower():
            return SurfaceIdentity(
                app_id=bundle_id,
                is_home_base=True,
                is_self=True,
                spoken_label="ALFRED",
                capability="FULL",
            )

        is_browser = bundle_id in KNOWN_MAC_BROWSERS
        spoken_label = KNOWN_MAC_BROWSERS.get(bundle_id, app_name or bundle_id)

        tab_host_hash = ""
        capability = "APP_ONLY"

        if is_browser and bundle_id in ("com.google.Chrome", "com.brave.Browser", "com.microsoft.edgemac"):
            app_script_name = KNOWN_MAC_BROWSERS[bundle_id]
            url = self._get_browser_url(app_script_name)
            if url:
                host = extract_host_from_url(url)
                if host:
                    tab_host_hash = hash_host(host)
                    capability = "FULL"

        return SurfaceIdentity(
            app_id=bundle_id,
            tab_host_hash=tab_host_hash,
            is_home_base=False,
            is_browser=is_browser,
            is_self=False,
            spoken_label=spoken_label,
            capability=capability,
        )

    def _get_frontmost_app(self) -> tuple[str, str]:
        try:
            cmd = ["osascript", "-e", 'tell application "System Events" to get {bundle identifier, name} of first application process whose frontmost is true']
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=CLI_TIMEOUT_S)
            if res.returncode == 0 and res.stdout.strip():
                parts = [p.strip() for p in res.stdout.strip().split(",")]
                if len(parts) >= 2:
                    return parts[0], parts[1]
                return parts[0], parts[0]
        except Exception as exc:
            _LOGGER.debug("Mac frontmost app query error: %s", exc)
        return "", ""

    def _get_browser_url(self, app_name: str) -> str:
        try:
            cmd = ["osascript", "-e", f'tell application "{app_name}" to get URL of active tab of front window']
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=CLI_TIMEOUT_S)
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception:
            pass
        return ""
