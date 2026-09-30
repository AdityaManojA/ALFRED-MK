"""
core/browser/platform/base.py — Abstract base class for platform-specific browser drivers.
"""
from __future__ import annotations

import abc
from typing import Optional

# ── Named Constants ──────────────────────────────────────────────────────────
DEFAULT_KEY_SETTLE_MS: int = 50
DEFAULT_TIMEOUT_S: float = 3.0


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
