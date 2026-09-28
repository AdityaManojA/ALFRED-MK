"""Focus Surface Reader: Fresh frontmost surface inspection every tick.

Structural Privacy Law:
- URL paths, query parameters, and fragments are NEVER read or stored.
- Only the domain/hostname is extracted from the address bar or window title,
  and hashed immediately via sha256(host)[:16].
- ALFRED's own process windows are classified as home base: never drift, never get a label.
- Every native query is bounded by READER_TIMEOUT_MS = 250ms.
"""
from __future__ import annotations

import abc
import hashlib
import logging
import sys
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

# ── Named Constants ──────────────────────────────────────────────────────────
READER_TIMEOUT_MS: int = 250
HASH_TRUNC_CHARS: int = 16

_LOGGER = logging.getLogger(__name__)


def hash_host(host: str) -> str:
    """Return a 16-character sha256 hash of the normalized domain host."""
    if not host:
        return ""
    cleaned = host.strip().lower()
    # Strip port if present
    if ":" in cleaned:
        cleaned = cleaned.split(":")[0]
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:HASH_TRUNC_CHARS]


def extract_host_from_url(url_or_domain: str) -> str:
    """Extract just the domain hostname from a raw URL or domain fragment."""
    if not url_or_domain:
        return ""
    raw = url_or_domain.strip()
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    try:
        parsed = urlparse(raw)
        return parsed.netloc or ""
    except Exception:
        return ""


@dataclass(frozen=True, slots=True)
class SurfaceIdentity:
    """Opaque representation used strictly for engine comparisons."""
    app_id: str = ""                # e.g., 'chrome.exe', 'code.exe', 'com.google.Chrome'
    tab_host_hash: str = ""         # sha256(host)[:16], empty if not browser or not reading tab
    is_home_base: bool = False      # True if ALFRED HUD / own process window
    is_browser: bool = False        # True if known browser process
    is_self: bool = False           # True if ALFRED itself
    spoken_label: str = ""          # transient label (e.g. 'Chrome', 'VS Code'), never stored
    capability: str = "FULL"        # 'FULL' | 'APP_ONLY' | 'UNKNOWN' | 'PERM_DENIED'
    raw_title: str = ""             # transient title for engine matching, never stored in FocusState


class BasePlatformReader(abc.ABC):
    """Abstract base for OS-level foreground window and browser tab inspection."""

    @abc.abstractmethod
    def get_frontmost_surface(self, from_card: bool = False) -> SurfaceIdentity:
        """Query the foreground window and active browser tab afresh."""
        raise NotImplementedError


def get_platform_reader() -> BasePlatformReader:
    """Factory returning the reader for the current operating system."""
    if sys.platform == "win32":
        from core.sentry.focus.platform.win import WinPlatformReader
        return WinPlatformReader()
    elif sys.platform == "darwin":
        from core.sentry.focus.platform.mac import MacPlatformReader
        return MacPlatformReader()
    else:
        from core.sentry.focus.platform.linux import LinuxPlatformReader
        return LinuxPlatformReader()
