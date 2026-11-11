"""
core/hud_video/backends/__init__.py — Backend interface.

Intentionally a plain class (NOT abc.ABC) so that QObject subclasses can
inherit from both QObject and BackendBase without a metaclass conflict.
PyQt6's pyqtWrapperType and ABCMeta cannot be combined.
"""

from __future__ import annotations

from core.hud_video.resolve import PlayableRef


class BackendBase:
    """Plain interface class for media playback engines.

    Subclasses must override every method; raises NotImplementedError by default.
    Do NOT make this an ABC — QObject subclasses cannot mix ABCMeta + pyqtWrapperType.
    """

    def load(self, ref: PlayableRef) -> None:
        """Load the given playable reference into the backend (abstract)."""
        raise NotImplementedError

    def play(self) -> None:
        """Start or resume playback (abstract)."""
        raise NotImplementedError

    def pause(self) -> None:
        """Pause playback (abstract)."""
        raise NotImplementedError

    def stop(self) -> None:
        """Stop playback and release the current media (abstract)."""
        raise NotImplementedError

    def set_muted(self, muted: bool) -> None:
        """Set the audio mute state (abstract)."""
        raise NotImplementedError

    def set_volume(self, volume: float) -> None:
        """Set the playback volume (abstract)."""
        raise NotImplementedError

    def seek(self, position_s: float) -> None:
        """Seek to the given position in seconds (abstract)."""
        raise NotImplementedError
