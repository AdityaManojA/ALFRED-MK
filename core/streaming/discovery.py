"""
core/streaming/discovery.py — Verified Host Surface Discovery.

Discovers only confirmed-present browsers and native desktop apps on the host OS.
Never fabricates uninstalled applications.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from core.streaming.provider import CapabilityClass, Surface, SurfaceKind

_OS = platform.system()

# Windows App Paths registry lookup names
_WIN_BROWSER_PATHS = {
    "chrome":  (r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe", "Google Chrome", "chrome"),
    "msedge":  (r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe", "Microsoft Edge", "msedge"),
    "brave":   (r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\brave.exe", "Brave Browser", "brave"),
    "firefox": (r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\firefox.exe", "Mozilla Firefox", None),
    "opera":   (r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\opera.exe", "Opera", None),
}

_LINUX_BROWSER_BINS = [
    ("chrome",  ["google-chrome", "google-chrome-stable", "chromium-browser", "chromium"], "Google Chrome"),
    ("msedge",  ["microsoft-edge", "microsoft-edge-stable"], "Microsoft Edge"),
    ("brave",   ["brave-browser", "brave"], "Brave Browser"),
    ("firefox", ["firefox"], "Mozilla Firefox"),
]

_MAC_BROWSER_APPS = [
    ("chrome",  "/Applications/Google Chrome.app", "Google Chrome"),
    ("msedge",  "/Applications/Microsoft Edge.app", "Microsoft Edge"),
    ("brave",   "/Applications/Brave Browser.app", "Brave Browser"),
    ("firefox", "/Applications/Firefox.app", "Mozilla Firefox"),
    ("safari",  "/Applications/Safari.app", "Safari"),
]


def discover_installed_browsers() -> List[Surface]:
    """Detect and return only browsers confirmed present on this OS."""
    surfaces: List[Surface] = []

    if _OS == "Windows":
        try:
            import winreg
            for b_id, (reg_path, display_name, channel) in _WIN_BROWSER_PATHS.items():
                for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                    try:
                        k = winreg.OpenKey(hive, reg_path)
                        val, _ = winreg.QueryValueEx(k, None)
                        winreg.CloseKey(k)
                        exe = str(val).strip().strip('"').split('"')[0].strip()
                        if exe and Path(exe).exists():
                            surfaces.append(
                                Surface(
                                    id=b_id,
                                    display_name=display_name,
                                    kind=SurfaceKind.BROWSER,
                                    capability=CapabilityClass.FULL,
                                    executable_path=exe,
                                    browser_channel=channel,
                                )
                            )
                            break
                    except OSError:
                        continue
        except Exception:
            pass

    elif _OS == "Darwin":
        for b_id, app_path, display_name in _MAC_BROWSER_APPS:
            if Path(app_path).exists():
                surfaces.append(
                    Surface(
                        id=b_id,
                        display_name=display_name,
                        kind=SurfaceKind.BROWSER,
                        capability=CapabilityClass.FULL,
                        executable_path=app_path,
                    )
                )

    elif _OS == "Linux":
        for b_id, bins, display_name in _LINUX_BROWSER_BINS:
            for b in bins:
                exe = shutil.which(b)
                if exe:
                    surfaces.append(
                        Surface(
                            id=b_id,
                            display_name=display_name,
                            kind=SurfaceKind.BROWSER,
                            capability=CapabilityClass.FULL,
                            executable_path=exe,
                        )
                    )
                    break

    return surfaces


def discover_netflix_native_app() -> Optional[Surface]:
    """Inspect host OS for the official Netflix desktop app."""
    if _OS == "Windows":
        try:
            # Check AppX package presence via PowerShell
            cmd = ["powershell", "-NoProfile", "-Command", "Get-AppxPackage 4DF9E0F8.Netflix | Select-Object -ExpandProperty PackageFamilyName"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            pkg = res.stdout.strip()
            if pkg and "4DF9E0F8.Netflix" in pkg:
                aumid = f"{pkg}!Netflix.App"
                return Surface(
                    id="netflix_native",
                    display_name="Netflix Windows App",
                    kind=SurfaceKind.NATIVE_APP,
                    capability=CapabilityClass.LAUNCH_ONLY,
                    executable_path=aumid,
                    extra_metadata={"aumid": aumid},
                )
        except Exception:
            pass
    return None


def discover_crunchyroll_native_app() -> Optional[Surface]:
    """Inspect host OS for official Crunchyroll desktop app."""
    # Crunchyroll does not ship an official native Windows Win32/UWP store desktop app
    return None
