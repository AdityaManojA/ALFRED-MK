"""
core/hud_video/__init__.py — Public exports for the HUD video subsystem.
"""

from .controller import HudVideoController, VideoState
from .resolve import PlayableRef, ResolveError
from .intent import detect, is_transport_command, VIDEO_LOCUS_PHRASES

__all__ = [
    "HudVideoController",
    "VideoState",
    "PlayableRef",
    "ResolveError",
    "detect",
    "is_transport_command",
    "VIDEO_LOCUS_PHRASES",
]
