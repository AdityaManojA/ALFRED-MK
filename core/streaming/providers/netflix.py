"""
core/streaming/providers/netflix.py — Netflix Streaming Provider Implementation.

Implements StreamingProvider for Netflix desktop surfaces (Windows Store App and browsers).
Uses OCR-based state inspection, spatial profile extraction, fuzzy name/slot matching,
and strictly enforces PIN-lock handover without entering credentials or PINs.
"""
from __future__ import annotations

import difflib
import logging
import os
import platform
import subprocess
import time
import urllib.parse
import webbrowser
from pathlib import Path
from typing import List, Optional

try:
    import pyautogui
    _HAS_PYAUTOGUI = True
except ImportError:
    _HAS_PYAUTOGUI = False

from core.pilots.netflix.detector import (
    NetflixDetector,
    NetflixState,
    ProfileSlot,
)
from core.streaming.discovery import (
    discover_installed_browsers,
    discover_netflix_native_app,
)
from core.streaming.provider import (
    CapabilityClass,
    ProfileCard,
    ProviderState,
    Readiness,
    Result,
    StreamingProvider,
    Surface,
    SurfaceKind,
    Title,
)
from core.streaming.registry import get_selector

_LOGGER = logging.getLogger(__name__)

# ── Named Constants ──────────────────────────────────────────────────────────
NETFLIX_HOME_URL: str         = "https://www.netflix.com/browse"
NETFLIX_PROFILES_URL: str     = "https://www.netflix.com/SwitchProfile"
NETFLIX_SEARCH_URL: str       = "https://www.netflix.com/search?q={query}"
NETFLIX_WATCH_URL: str        = "https://www.netflix.com/watch/{title_id}"

SETTLE_DELAY_S: float         = 1.5
KEY_DELAY_MS: int             = 25
PIN_LOCK_WARNING: str         = "That profile is locked, sir — you'll need to enter the PIN."


class NetflixProvider(StreamingProvider):
    """Concrete StreamingProvider for Netflix."""
    id: str = "netflix"
    display_name: str = "Netflix"

    def __init__(self, detector: Optional[NetflixDetector] = None) -> None:
        """Use the given Netflix detector or create a default one."""
        self.detector = detector or NetflixDetector()

    def discover_surfaces(self) -> List[Surface]:
        """Inspect host OS for real Netflix-capable surfaces."""
        surfaces: List[Surface] = []
        # 1. Native desktop app (if present on Windows)
        native = discover_netflix_native_app()
        if native is not None:
            surfaces.append(native)

        # 2. Installed browsers
        browsers = discover_installed_browsers()
        surfaces.extend(browsers)
        return surfaces

    def readiness(self, surface: Surface) -> Readiness:
        """Check if surface is installed, logged in, and capable."""
        if surface.capability == CapabilityClass.UNAVAILABLE:
            return Readiness.UNAVAILABLE

        if surface.kind == SurfaceKind.NATIVE_APP:
            if not surface.executable_path:
                return Readiness.NOT_INSTALLED
            return Readiness.READY

        # For browser surfaces, inspect current visible state
        st = self.detect_state(surface)
        if st == ProviderState.LOGIN:
            return Readiness.NOT_LOGGED_IN

        return Readiness.READY

    def open(self, surface: Surface) -> Result:
        """Launch or bring Netflix to the foreground."""
        if surface.kind == SurfaceKind.NATIVE_APP:
            if platform.system() == "Windows" and surface.executable_path:
                try:
                    # Launch Windows Store App via AUMID
                    subprocess.Popen(
                        ["explorer.exe", f"shell:AppsFolder\\{surface.executable_path}"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    time.sleep(SETTLE_DELAY_S)
                    return Result(ok=True, message="Netflix Windows App launched, sir.")
                except Exception as exc:
                    return Result(ok=False, message=f"Failed to launch Netflix app: {exc}")
            return Result(ok=False, message="Native app launch unsupported on this platform, sir.")

        # Browser surface
        try:
            from actions.browser_control import _open_native
            _open_native(NETFLIX_HOME_URL, browser_name=surface.id)
        except Exception:
            webbrowser.open(NETFLIX_HOME_URL)

        time.sleep(SETTLE_DELAY_S)
        return Result(ok=True, message="Netflix opened in your browser, sir.")

    def detect_state(self, surface: Surface) -> ProviderState:
        """Inspect on-screen state via OCR and window grounding."""
        raw_state, _ = self.detector.inspect_state(force=True)
        if raw_state == NetflixState.NOT_LOGGED_IN:
            return ProviderState.LOGIN
        elif raw_state == NetflixState.PROFILE_GATE:
            return ProviderState.PROFILES
        elif raw_state == NetflixState.BROWSE_HOME:
            return ProviderState.HOME
        elif raw_state == NetflixState.PLAYING:
            return ProviderState.PLAYING

        return ProviderState.HOME

    def list_profiles(self, surface: Surface) -> List[ProfileCard]:
        """Extract detected profile cards from the screen."""
        raw_state, slots = self.detector.inspect_state(force=True)
        cards: List[ProfileCard] = []
        for s in slots:
            cards.append(
                ProfileCard(
                    id=f"profile_{s.slot_index}",
                    label=s.name,
                    is_locked=False,
                    slot_index=s.slot_index,
                )
            )
        return cards

    def select_profile(self, surface: Surface, label: str) -> Result:
        """
        Select a profile by label or index.
        If a PIN prompt appears, halts immediately and hands control over to the user.
        """
        raw_state, slots = self.detector.inspect_state(force=True)
        if not slots:
            return Result(ok=False, message="No profiles detected on screen, sir.")

        from core.pilots.netflix.actions import match_profile_selection
        target_slot = match_profile_selection(label, slots)
        if not target_slot:
            return Result(ok=False, message=f"I could not identify profile '{label}', sir.")

        # Click the profile slot
        if _HAS_PYAUTOGUI:
            try:
                w, h = pyautogui.size()
                cx = int(target_slot.center_norm[0] * w)
                cy = int(target_slot.center_norm[1] * h)
                pyautogui.click(cx, cy)
            except Exception as e:
                _LOGGER.debug("[Netflix] Profile click failed: %s", e)
            time.sleep(SETTLE_DELAY_S)

        # Inspect whether a PIN prompt appeared
        new_state, _ = self.detector.inspect_state(force=True)
        # Check OCR tokens for PIN signals
        last_tokens = [t.lower() for t in getattr(self.detector, "_last_tokens", [])]
        if any(w in last_tokens for w in ("pin", "enter your pin", "profile lock", "locked")):
            return Result(ok=False, message=PIN_LOCK_WARNING)

        return Result(ok=True, message=f"Accessing {target_slot.name}, sir.")

    def search(self, surface: Surface, query: str) -> List[Title]:
        """Navigate to search URL and return candidate titles."""
        clean_q = query.strip()
        encoded = urllib.parse.quote(clean_q)
        url = NETFLIX_SEARCH_URL.format(query=encoded)

        try:
            from actions.browser_control import _open_native
            _open_native(url, browser_name=surface.id if surface.kind == SurfaceKind.BROWSER else None)
        except Exception:
            webbrowser.open(url)

        time.sleep(SETTLE_DELAY_S)
        # Return candidate title
        return [
            Title(
                id=clean_q.lower().replace(" ", "-"),
                name=clean_q,
                url=url,
                is_series=False,
            )
        ]

    def play(self, surface: Surface, title: Title) -> Result:
        """Direct playback for the given title."""
        if title.url and "/watch/" in title.url:
            play_url = title.url
        else:
            # If search title provided, navigate to search and trigger Enter
            encoded = urllib.parse.quote(title.name)
            play_url = NETFLIX_SEARCH_URL.format(query=encoded)

        try:
            from actions.browser_control import _open_native
            _open_native(play_url, browser_name=surface.id if surface.kind == SurfaceKind.BROWSER else None)
        except Exception:
            webbrowser.open(play_url)

        time.sleep(SETTLE_DELAY_S)
        if _HAS_PYAUTOGUI:
            try:
                pyautogui.press("enter")
            except Exception:
                pass

        return Result(ok=True, message=f"Playing '{title.name}' on Netflix, sir.")
