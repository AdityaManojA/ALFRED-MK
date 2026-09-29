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
        raise NotImplementedError

    def play(self) -> None:
        raise NotImplementedError

    def pause(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def set_muted(self, muted: bool) -> None:
        raise NotImplementedError

    def set_volume(self, volume: float) -> None:
        raise NotImplementedError
