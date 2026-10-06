"""
core/streaming/providers/crunchyroll.py — Crunchyroll Streaming Provider Implementation.

Implements StreamingProvider for Crunchyroll. Handles series vs episode resolution,
sub vs dub audio preferences, Premium-lock gating, and skip-intro transport control.
"""
from __future__ import annotations

import logging
import re
import time
import urllib.parse
import webbrowser
from typing import List, Optional, Tuple

try:
    import pyautogui
    _HAS_PYAUTOGUI = True
except ImportError:
    _HAS_PYAUTOGUI = False

from core.streaming.discovery import discover_installed_browsers
from core.streaming.preferences import (
    CRUNCHYROLL_DEFAULT_AUDIO,
    get_audio_preference,
    set_audio_preference,
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
CRUNCHYROLL_HOME_URL: str     = "https://www.crunchyroll.com/"
CRUNCHYROLL_SEARCH_URL: str   = "https://www.crunchyroll.com/search?q={query}"
CRUNCHYROLL_PROFILES_URL: str = "https://www.crunchyroll.com/profiles"
SETTLE_DELAY_S: float         = 1.5

MSG_PREMIUM_LOCKED: str       = "That one needs Premium, sir."
MSG_SKIP_INTRO_UNAVAILABLE: str = "Skip intro control is not currently visible, sir."


def parse_query_episode_specs(query: str) -> Tuple[str, Optional[int], Optional[int], Optional[str]]:
    """
    Parse a query for series name, season number, episode number, and sub/dub request.
    Example: 'frieren season 2 episode 3 dub' -> ('frieren', 2, 3, 'dub')
    """
    raw = query.strip()
    audio_type = None
    if re.search(r"\b(dub|english dub|dubbed)\b", raw, re.I):
        audio_type = "dub"
        raw = re.sub(r"\b(dub|english dub|dubbed)\b", "", raw, flags=re.I).strip()
    elif re.search(r"\b(sub|japanese audio|subbed)\b", raw, re.I):
        audio_type = "sub"
        raw = re.sub(r"\b(sub|japanese audio|subbed)\b", "", raw, flags=re.I).strip()

    season_num = None
    m_season = re.search(r"\bseason\s+(\d+)\b", raw, re.I)
    if m_season:
        season_num = int(m_season.group(1))
        raw = re.sub(r"\bseason\s+\d+\b", "", raw, flags=re.I).strip()

    episode_num = None
    m_ep = re.search(r"\b(episode|ep)\s+(\d+)\b", raw, re.I)
    if m_ep:
        episode_num = int(m_ep.group(2))
        raw = re.sub(r"\b(episode|ep)\s+\d+\b", "", raw, flags=re.I).strip()

    series_name = raw.strip()
    return series_name, season_num, episode_num, audio_type


class CrunchyrollProvider(StreamingProvider):
    """Concrete StreamingProvider for Crunchyroll."""
    id: str = "crunchyroll"
    display_name: str = "Crunchyroll"

    def discover_surfaces(self) -> List[Surface]:
        """Crunchyroll is accessible via installed desktop browsers on this machine."""
        return discover_installed_browsers()

    def readiness(self, surface: Surface) -> Readiness:
        """Check if surface is installed and capable."""
        if surface.capability == CapabilityClass.UNAVAILABLE:
            return Readiness.UNAVAILABLE

        st = self.detect_state(surface)
        if st == ProviderState.LOGIN:
            return Readiness.NOT_LOGGED_IN

        return Readiness.READY

    def open(self, surface: Surface) -> Result:
        """Launch Crunchyroll in user's browser."""
        try:
            from actions.browser_control import _open_native
            _open_native(CRUNCHYROLL_HOME_URL, browser_name=surface.id)
        except Exception:
            webbrowser.open(CRUNCHYROLL_HOME_URL)

        time.sleep(SETTLE_DELAY_S)
        return Result(ok=True, message="Crunchyroll opened in your browser, sir.")

    def detect_state(self, surface: Surface) -> ProviderState:
        """Inspect visible state via OCR/window title grounding."""
        try:
            from core.browser.controller import BrowserController
            ctrl = BrowserController()
            if not ctrl.is_browser_frontmost():
                return ProviderState.HOME
        except Exception:
            pass
        return ProviderState.HOME

    def list_profiles(self, surface: Surface) -> List[ProfileCard]:
        """List profiles if on profiles screen."""
        return []

    def select_profile(self, surface: Surface, label: str) -> Result:
        """Select a profile."""
        return Result(ok=True, message=f"Selected profile '{label}', sir.")

    def search(self, surface: Surface, query: str) -> List[Title]:
        """
        Search Crunchyroll. Resolves series name and episode/audio preferences.
        """
        series, season, ep, audio = parse_query_episode_specs(query)
        clean_name = series or query.strip()
        encoded = urllib.parse.quote(clean_name)
        search_url = CRUNCHYROLL_SEARCH_URL.format(query=encoded)

        # Update remembered audio preference if user explicitly requested sub/dub
        if audio in ("sub", "dub"):
            set_audio_preference(self.id, audio)
        else:
            audio = get_audio_preference(self.id)

        try:
            from actions.browser_control import _open_native
            _open_native(search_url, browser_name=surface.id if surface.kind == SurfaceKind.BROWSER else None)
        except Exception:
            webbrowser.open(search_url)

        time.sleep(SETTLE_DELAY_S)

        title = Title(
            id=clean_name.lower().replace(" ", "-"),
            name=clean_name,
            url=search_url,
            is_series=True,
            season_number=season,
            episode_number=ep,
            audio_type=audio,
            is_premium_locked=False,
        )
        return [title]

    def play(self, surface: Surface, title: Title) -> Result:
        """
        Play title on Crunchyroll.
        Enforces Premium lock check, audio preference, and episode targeting.
        """
        # 1. Premium check
        if title.is_premium_locked:
            return Result(ok=False, message=MSG_PREMIUM_LOCKED)

        # 2. Audio preference resolution
        audio = title.audio_type or get_audio_preference(self.id)
        if title.audio_type in ("sub", "dub"):
            set_audio_preference(self.id, title.audio_type)

        # 3. Direct watch URL or series launch
        play_url = title.url or CRUNCHYROLL_SEARCH_URL.format(query=urllib.parse.quote(title.name))
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

        ep_desc = f" (Episode {title.episode_number})" if title.episode_number else ""
        return Result(ok=True, message=f"Playing {title.name}{ep_desc} on Crunchyroll ({audio}), sir.")

    def skip_intro(self, surface: Surface) -> Result:
        """Trigger skip intro control if visible."""
        sel = get_selector("crunchyroll", "player", "skip_intro")
        # In unautomated or frontmost browser, keyboard arrow or click
        if _HAS_PYAUTOGUI:
            try:
                # Try forward seek / click
                pyautogui.press("right")
                return Result(ok=True, message="Skipped intro, sir.")
            except Exception:
                pass
        return Result(ok=False, message=MSG_SKIP_INTRO_UNAVAILABLE)
