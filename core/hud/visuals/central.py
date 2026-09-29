"""
core/hud/visuals/central.py — Theme-aware Central Visualizer Reskinning.
Controls color ramp, ring geometry, segment count, and pulse curve of the reactor globe
without altering the viseme/lip-sync audio drive.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple
from PyQt6.QtGui import QColor

from core.ui.themes.schema import PaletteDefinition


@dataclass(frozen=True)
class CentralSkin:
    """Themed geometry and color styling parameters for the reactor globe."""
    ring_count: int = 7
    meridian_count: int = 12
    orbit_tilt_deg: float = 35.0
    orbit_nodes: tuple[str, ...] = ("24", "25", "34", "09")
    core_lens_ratio: float = 0.34
    hex_emitter_ratio: float = 0.65
    wave_harmonics: int = 2
    pulse_intensity: float = 1.0


# ── Themed Central Skins ──────────────────────────────────────────────────────
_SKINS: dict[str, CentralSkin] = {
    # Batcave: Standard 7-ring WAKU CRT globe with 4 numbered satellites
    "dossier": CentralSkin(
        ring_count=7, meridian_count=12, orbit_tilt_deg=35.0,
        orbit_nodes=("24", "25", "34", "09"), core_lens_ratio=0.34,
    ),
    # Catwoman: Sleek violet/cyan rapid sweep rings
    "catwoman": CentralSkin(
        ring_count=5, meridian_count=10, orbit_tilt_deg=45.0,
        orbit_nodes=("E1", "E2", "E3", "E4"), core_lens_ratio=0.30,
    ),
    # Bane: Heavy dense green venom churn
    "vector": CentralSkin(
        ring_count=9, meridian_count=16, orbit_tilt_deg=20.0,
        orbit_nodes=("V1", "V2", "V3", "V4"), core_lens_ratio=0.40,
    ),
    # Batman Beyond: Magenta/cyan cyberpunk glitch ring profile
    "beyond": CentralSkin(
        ring_count=6, meridian_count=8, orbit_tilt_deg=50.0,
        orbit_nodes=("39", "40", "41", "42"), core_lens_ratio=0.36,
    ),
    # Mr. Freeze: Pale-cyan crystalline facets
    "mr_freeze": CentralSkin(
        ring_count=6, meridian_count=6, orbit_tilt_deg=30.0,
        orbit_nodes=("0K", "1K", "2K", "3K"), core_lens_ratio=0.32,
    ),
    # Joker: Asymmetric erratic wobble
    "joker": CentralSkin(
        ring_count=8, meridian_count=13, orbit_tilt_deg=65.0,
        orbit_nodes=("HA", "HA", "HA", "HA"), core_lens_ratio=0.38,
    ),
    # Two-Face: Dual split hemisphere
    "harvey_two_face": CentralSkin(
        ring_count=8, meridian_count=12, orbit_tilt_deg=0.0,
        orbit_nodes=("50", "50", "50", "50"), core_lens_ratio=0.35,
    ),
    # Arkham Asylum: Sickly amber/green institutional pulse
    "arkham": CentralSkin(
        ring_count=5, meridian_count=8, orbit_tilt_deg=25.0,
        orbit_nodes=("B1", "B2", "B3", "B4"), core_lens_ratio=0.33,
    ),
    # Watchtower: Clean orbital array satellite ring
    "watchtower": CentralSkin(
        ring_count=8, meridian_count=14, orbit_tilt_deg=40.0,
        orbit_nodes=("JL", "01", "02", "03"), core_lens_ratio=0.34,
    ),
    # Riddler: Enigma question glyph ring
    "riddler": CentralSkin(
        ring_count=7, meridian_count=10, orbit_tilt_deg=30.0,
        orbit_nodes=("??", "??", "??", "??"), core_lens_ratio=0.35,
    ),
}

_DEFAULT_SKIN = _SKINS["dossier"]


def get_central_skin(theme_id: str) -> CentralSkin:
    """Retrieve CentralSkin for active theme ID."""
    clean_id = str(theme_id or "dossier").lower().strip()
    return _SKINS.get(clean_id, _DEFAULT_SKIN)
