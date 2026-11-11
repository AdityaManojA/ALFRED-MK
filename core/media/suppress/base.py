"""Private interface for platform media control."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Suppressor(ABC):
    """Abstract platform backend that pauses/resumes external media players."""

    @abstractmethod
    def enumerate_players(self) -> list[Any]:
        """Return opaque handles; callers must never inspect or log them."""

    @abstractmethod
    def pause(self, handle: Any) -> bool:
        """Pause or, only as a fallback, mute the opaque external player."""

    @abstractmethod
    def resume(self, handle: Any) -> bool:
        """Resume only a player ALFRED previously paused."""

    @abstractmethod
    def is_playing(self, handle: Any) -> bool:
        """Return current playback state without exposing player metadata."""


class NullSuppressor(Suppressor):
    """No-op backend: finds no players and reports every operation as failed."""

    def enumerate_players(self) -> list[Any]:
        """Return no players."""
        return []

    def pause(self, handle: Any) -> bool:
        """Do nothing; return False."""
        return False

    def resume(self, handle: Any) -> bool:
        """Do nothing; return False."""
        return False

    def is_playing(self, handle: Any) -> bool:
        """Return False."""
        return False
