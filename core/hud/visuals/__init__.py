"""
core/hud/visuals/__init__.py
"""
from core.hud.visuals.base import HudSignals, SlotVisual, fast_cos, fast_sin
from core.hud.visuals.central import CentralSkin, get_central_skin
from core.hud.visuals.primitives import (
    BarArray,
    RadarSweep,
    WaveTrace,
    Wireframe3D,
)
from core.hud.visuals.registry import (
    SLOT_COUNT,
    get_visual_class,
    instantiate_visual,
)

__all__ = [
    "HudSignals",
    "SlotVisual",
    "fast_cos",
    "fast_sin",
    "CentralSkin",
    "get_central_skin",
    "BarArray",
    "RadarSweep",
    "WaveTrace",
    "Wireframe3D",
    "SLOT_COUNT",
    "get_visual_class",
    "instantiate_visual",
]
