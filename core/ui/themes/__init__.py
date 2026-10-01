"""
ALFRED-MK-VIII Thematic UI Skins.
Provides structured theme schema, in-memory registry, unified apply path,
and ThemeChrome contextual string accessors.
"""
from __future__ import annotations

from core.ui.themes.schema import (
    ChromeDefinition,
    IdentityDefinition,
    PaletteDefinition,
    SpeechFlavour,
    SubjectValueMode,
    ThemeDefinition,
    ThreatLevels,
)
from core.ui.themes.registry import ThemeRegistry
from core.ui.themes.catalog import (
    ALL_THEMES,
    DEFAULT_BATCAVE,
    BANE_MODE,
    BATMAN_BEYOND,
    JOKER,
    RIDDLER,
    MR_FREEZE,
    TWO_FACE,
    CATWOMAN,
    ARKHAM,
    WATCHTOWER,
)
from core.ui.themes.apply import ThemeChrome, apply_theme


def get_theme(id_or_hex: str) -> ThemeDefinition:
    """Convenience getter for ThemeRegistry.instance().get(id_or_hex)."""
    return ThemeRegistry.instance().get(id_or_hex)


def list_themes() -> list[ThemeDefinition]:
    """Convenience getter for ThemeRegistry.instance().list_themes()."""
    return ThemeRegistry.instance().list_themes()


__all__ = [
    "SubjectValueMode",
    "PaletteDefinition",
    "ThreatLevels",
    "IdentityDefinition",
    "ChromeDefinition",
    "SpeechFlavour",
    "ThemeDefinition",
    "ThemeRegistry",
    "ALL_THEMES",
    "DEFAULT_BATCAVE",
    "BANE_MODE",
    "BATMAN_BEYOND",
    "JOKER",
    "RIDDLER",
    "MR_FREEZE",
    "TWO_FACE",
    "CATWOMAN",
    "ARKHAM",
    "WATCHTOWER",
    "ThemeChrome",
    "apply_theme",
    "get_theme",
    "list_themes",
]
