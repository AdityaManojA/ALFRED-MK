"""
core/hud/visuals/registry.py — Maps (theme_id, slot_index) -> SlotVisual class.
Falls back to Default Batcave visual set for any unspecified pair.
"""
from __future__ import annotations

from typing import Dict, Tuple, Type
from core.hud.visuals.base import SlotVisual
from core.hud.visuals.slots import (
    BatcaveBlueprintVisual,
    BatcaveRadarVisual,
    BatcaveSpectrumVisual,
    CatwomanAcrobatVisual,
    CatwomanLockpickVisual,
    CatwomanSonarVisual,
    BaneDosageRegulatorVisual,
    BaneMaskSchematicVisual,
    BanePressureChamberVisual,
    BeyondAvatarVisual,
    BeyondICELadderVisual,
    BeyondRetinalVisual,
    FreezeCoolantLoopVisual,
    FreezeCoreLatticeVisual,
    FreezeThermalColumnVisual,
    JokerCardScatterVisual,
    JokerGrinningMaskVisual,
    JokerLaughWaveVisual,
    TwoFaceBisectedVisual,
    TwoFaceSilverDollarVisual,
    TwoFaceSplitMirrorVisual,
    ArkhamEEGVisual,
    ArkhamFloorplanVisual,
    ArkhamVitalsVisual,
    WatchtowerFluxRingVisual,
    WatchtowerHoloManVisual,
    WatchtowerPowerOutputVisual,
    RiddlerCipherVisual,
    RiddlerLogicGatesVisual,
    RiddlerMazeVisual,
)

SLOT_COUNT: int = 3

# Registry map: (theme_id, slot_index) -> SlotVisual class
_REGISTRY: dict[tuple[str, int], type[SlotVisual]] = {
    # 1. Default Batcave
    ("dossier", 0): BatcaveRadarVisual,
    ("dossier", 1): BatcaveSpectrumVisual,
    ("dossier", 2): BatcaveBlueprintVisual,

    # 2. Catwoman
    ("catwoman", 0): CatwomanSonarVisual,
    ("catwoman", 1): CatwomanLockpickVisual,
    ("catwoman", 2): CatwomanAcrobatVisual,

    # 3. Bane Mode
    ("vector", 0): BanePressureChamberVisual,
    ("vector", 1): BaneDosageRegulatorVisual,
    ("vector", 2): BaneMaskSchematicVisual,

    # 4. Batman Beyond
    ("beyond", 0): BeyondRetinalVisual,
    ("beyond", 1): BeyondICELadderVisual,
    ("beyond", 2): BeyondAvatarVisual,

    # 5. Mr. Freeze
    ("mr_freeze", 0): FreezeCoreLatticeVisual,
    ("mr_freeze", 1): FreezeThermalColumnVisual,
    ("mr_freeze", 2): FreezeCoolantLoopVisual,

    # 6. Joker
    ("joker", 0): JokerCardScatterVisual,
    ("joker", 1): JokerLaughWaveVisual,
    ("joker", 2): JokerGrinningMaskVisual,

    # 7. Two-Face
    ("harvey_two_face", 0): TwoFaceSplitMirrorVisual,
    ("harvey_two_face", 1): TwoFaceSilverDollarVisual,
    ("harvey_two_face", 2): TwoFaceBisectedVisual,

    # 8. Arkham Asylum
    ("arkham", 0): ArkhamFloorplanVisual,
    ("arkham", 1): ArkhamEEGVisual,
    ("arkham", 2): ArkhamVitalsVisual,

    # 9. Watchtower Omni
    ("watchtower", 0): WatchtowerFluxRingVisual,
    ("watchtower", 1): WatchtowerPowerOutputVisual,
    ("watchtower", 2): WatchtowerHoloManVisual,

    # 10. Riddler Enigma
    ("riddler", 0): RiddlerCipherVisual,
    ("riddler", 1): RiddlerLogicGatesVisual,
    ("riddler", 2): RiddlerMazeVisual,
}

_FALLBACKS: tuple[type[SlotVisual], type[SlotVisual], type[SlotVisual]] = (
    BatcaveRadarVisual,
    BatcaveSpectrumVisual,
    BatcaveBlueprintVisual,
)


def get_visual_class(theme_id: str, slot: int) -> type[SlotVisual]:
    """Resolve SlotVisual class for given theme and slot index, falling back to Batcave default."""
    slot_idx = max(0, min(SLOT_COUNT - 1, int(slot)))
    clean_theme = str(theme_id or "dossier").lower().strip()
    return _REGISTRY.get((clean_theme, slot_idx), _FALLBACKS[slot_idx])


def instantiate_visual(theme_id: str, slot: int) -> SlotVisual:
    """Instantiate a new visual for the given theme and slot."""
    cls = get_visual_class(theme_id, slot)
    return cls()
