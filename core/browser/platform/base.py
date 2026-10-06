"""
core/browser/platform/base.py — Abstract base class for platform-specific browser drivers.
"""
from __future__ import annotations

import abc
import re
from typing import Optional

# ── Named Constants ──────────────────────────────────────────────────────────
DEFAULT_KEY_SETTLE_MS: int = 50
DEFAULT_TIMEOUT_S: float = 3.0


def normalize_tab_query(query: str) -> list[str]:
    """Extract candidate match tokens from a user query or URL for fuzzy matching."""
    raw = query.strip().lower()
    if not raw:
        return []
    candidates = [raw]

    # If it's a URL or contains slashes, extract hostname and clean domain
    try:
        from urllib.parse import urlparse

        parsed = urlparse(raw if "://" in raw else f"http://{raw}")
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        if netloc and netloc not in candidates:
            candidates.append(netloc)
        no_tld_host = re.sub(
            r"\.(com|org|net|io|co|ai|app|edu|gov|in|me|dev|xyz|so)$", "", netloc
        )
        if no_tld_host and no_tld_host not in candidates and len(no_tld_host) >= 2:
            candidates.append(no_tld_host)
    except Exception:
        pass

    # Strip URL protocol and trailing slashes
    no_proto = re.sub(r"^https?://(www\.)?", "", raw).rstrip("/")
    if no_proto and no_proto not in candidates:
        candidates.append(no_proto)

    # Strip top-level domains (e.g. youtube.com -> youtube)
    no_tld = re.sub(
        r"\.(com|org|net|io|co|ai|app|edu|gov|in|me|dev|xyz|so)$", "", no_proto
    )
    if no_tld and no_tld not in candidates and len(no_tld) >= 2:
        candidates.append(no_tld)

    return candidates


def tab_matches_query(tab_name: str, candidates: list[str]) -> bool:
    """Return True if any candidate query token is contained within the tab title/URL."""
    if not tab_name or not candidates:
        return False
    name_lower = tab_name.lower()
    return any(c in name_lower for c in candidates)


class BaseBrowserPlatformDriver(abc.ABC):
    """Abstract driver interface for platform-specific browser manipulation."""

    @abc.abstractmethod
    def get_frontmost_browser(self) -> Optional[str]:
        """Return the lowercase name of the frontmost browser process/bundle if active, else None."""
        raise NotImplementedError

    @abc.abstractmethod
    def close_active_tab(self) -> bool:
        """Close the currently active tab in the frontmost browser."""
        raise NotImplementedError

    @abc.abstractmethod
    def close_tab_matching(self, query: str, browser: Optional[str] = None) -> bool:
        """Find and close a tab matching query/URL in specified or frontmost browser.

        Returns True if a matching tab was found and closed, False otherwise.
        Must NOT close an arbitrary active tab if no matching tab is found.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def new_tab(self, url: Optional[str] = None) -> bool:
        """Open a new tab in the frontmost or default browser with optional URL."""
        raise NotImplementedError

    @abc.abstractmethod
    def switch_tab(self, direction: str = "next") -> bool:
        """Switch to next or previous tab."""
        raise NotImplementedError

    @abc.abstractmethod
    def reopen_closed_tab(self) -> bool:
        """Reopen the most recently closed tab."""
        raise NotImplementedError

    @abc.abstractmethod
    def close_window(self) -> bool:
        """Close the frontmost browser window."""
        raise NotImplementedError
