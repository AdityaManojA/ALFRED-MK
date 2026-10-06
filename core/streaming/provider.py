"""
core/streaming/provider.py — Unified Streaming Provider Abstraction.

Defines the contract, data types, and capabilities for streaming providers
(Netflix, Crunchyroll, etc.) across native desktop apps and browsers.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, List, Optional


# ── Named Constants ──────────────────────────────────────────────────────────
PROVIDER_NAV_TIMEOUT_S: float    = 20.0     # page/app navigation settle
PROVIDER_SEARCH_TIMEOUT_S: float = 10.0     # search query response settle
PROVIDER_STATE_POLL_MS: int      = 500      # polling interval for DOM state
PROVIDER_STATE_RETRIES: int      = 3        # retries before declaring state unknown


class SurfaceKind(Enum):
    """Execution environment where the streaming service is hosted."""
    NATIVE_APP = "NATIVE_APP"
    PWA        = "PWA"
    BROWSER    = "BROWSER"


class CapabilityClass(Enum):
    """P0.4 DRM and automation capability classification."""
    FULL        = "FULL"          # Navigate, search, and playback all verified working
    NAV_ONLY    = "NAV_ONLY"      # Search & navigation work; video playback fails DRM/CDM
    LAUNCH_ONLY = "LAUNCH_ONLY"   # Can launch native app/URL; no internal automation
    UNAVAILABLE = "UNAVAILABLE"   # Not present or non-functional on host OS


class Readiness(Enum):
    """Pre-dispatch readiness gate state."""
    NOT_INSTALLED   = "NOT_INSTALLED"
    NOT_LOGGED_IN   = "NOT_LOGGED_IN"
    DRM_UNSUPPORTED = "DRM_UNSUPPORTED"
    READY           = "READY"
    UNAVAILABLE     = "UNAVAILABLE"


class ProviderState(Enum):
    """Observable runtime state of the provider window or tab."""
    LOADING  = "LOADING"
    LOGIN    = "LOGIN"
    PROFILES = "PROFILES"
    HOME     = "HOME"
    SEARCH   = "SEARCH"
    PLAYING  = "PLAYING"
    PAUSED   = "PAUSED"
    ERROR    = "ERROR"


@dataclass(frozen=True)
class Surface:
    """Represents a concrete detected host surface (app or browser)."""
    id: str
    display_name: str
    kind: SurfaceKind
    capability: CapabilityClass
    executable_path: Optional[str] = None
    browser_channel: Optional[str] = None
    extra_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProfileCard:
    """Represents a selectable user profile on the service."""
    id: str
    label: str
    is_locked: bool = False
    avatar_url: Optional[str] = None
    slot_index: Optional[int] = None


@dataclass(frozen=True)
class Title:
    """Represents a search result or playable item."""
    id: str
    name: str
    url: Optional[str] = None
    is_series: bool = False
    season_number: Optional[int] = None
    episode_number: Optional[int] = None
    audio_type: Optional[str] = None  # "sub" | "dub"
    is_premium_locked: bool = False


@dataclass(frozen=True)
class Result:
    """Generic operation outcome payload."""
    ok: bool
    message: str
    data: Any = None


class StreamingProvider(ABC):
    """Abstract interface for all video streaming providers."""
    id: str
    display_name: str

    @abstractmethod
    def discover_surfaces(self) -> List[Surface]:
        """Detect and return only confirmed-present surfaces on this machine."""
        pass

    @abstractmethod
    def readiness(self, surface: Surface) -> Readiness:
        """Evaluate whether surface is ready for user actions."""
        pass

    @abstractmethod
    def open(self, surface: Surface) -> Result:
        """Launch or focus the surface."""
        pass

    @abstractmethod
    def detect_state(self, surface: Surface) -> ProviderState:
        """Interrogate current visible state without blocking Qt thread."""
        pass

    @abstractmethod
    def list_profiles(self, surface: Surface) -> List[ProfileCard]:
        """Return available profiles on screen or in session."""
        pass

    @abstractmethod
    def select_profile(self, surface: Surface, label: str) -> Result:
        """Select a profile by label or index. Halts if profile is PIN-locked."""
        pass

    @abstractmethod
    def search(self, surface: Surface, query: str) -> List[Title]:
        """Query catalogue and return candidate titles."""
        pass

    @abstractmethod
    def play(self, surface: Surface, title: Title) -> Result:
        """Initiate video playback for the specified title."""
        pass
