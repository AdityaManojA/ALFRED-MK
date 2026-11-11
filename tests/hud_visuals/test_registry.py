"""Tests for core.hud.visuals.registry — (theme_id, slot) -> SlotVisual resolution."""
from __future__ import annotations

import pytest

from tests.hud_visuals import _helpers  # noqa: F401  (ensures QGuiApplication + offscreen)

from core.hud.visuals import registry
from core.hud.visuals.base import SlotVisual
from core.hud.visuals.slots import (
    ArkhamEEGVisual,
    BatcaveBlueprintVisual,
    BatcaveRadarVisual,
    BatcaveSpectrumVisual,
    JokerGrinningMaskVisual,
    RiddlerCipherVisual,
    WatchtowerHoloManVisual,
)

THEMES = ("dossier", "catwoman", "vector", "beyond", "mr_freeze", "joker",
          "harvey_two_face", "arkham", "watchtower", "riddler")


def test_slot_count_constant():
    assert registry.SLOT_COUNT == 3


def test_registry_has_full_grid_of_unique_classes():
    keys = set(registry._REGISTRY)
    assert keys == {(t, s) for t in THEMES for s in range(3)}
    # Every theme/slot gets its own dedicated class — no accidental duplicates.
    assert len(set(registry._REGISTRY.values())) == len(registry._REGISTRY)
    for cls in registry._REGISTRY.values():
        assert issubclass(cls, SlotVisual)


@pytest.mark.parametrize("theme,slot,expected", [
    ("joker", 2, JokerGrinningMaskVisual),
    ("arkham", 1, ArkhamEEGVisual),
    ("riddler", 0, RiddlerCipherVisual),
    ("watchtower", 2, WatchtowerHoloManVisual),
])
def test_exact_lookup(theme, slot, expected):
    assert registry.get_visual_class(theme, slot) is expected


def test_theme_id_is_normalised():
    assert registry.get_visual_class("  JOKER ", 2) is JokerGrinningMaskVisual


@pytest.mark.parametrize("theme", ["", None, "no_such_theme"])
def test_unknown_or_empty_theme_falls_back_to_batcave(theme):
    assert registry.get_visual_class(theme, 0) is BatcaveRadarVisual
    assert registry.get_visual_class(theme, 1) is BatcaveSpectrumVisual
    assert registry.get_visual_class(theme, 2) is BatcaveBlueprintVisual


def test_slot_index_is_clamped_and_coerced():
    assert registry.get_visual_class("arkham", -5) is registry._REGISTRY[("arkham", 0)]
    assert registry.get_visual_class("arkham", 99) is registry._REGISTRY[("arkham", 2)]
    assert registry.get_visual_class("arkham", "1") is ArkhamEEGVisual
    assert registry.get_visual_class("arkham", 1.9) is ArkhamEEGVisual  # int() truncation


def test_non_numeric_slot_raises():
    with pytest.raises(ValueError):
        registry.get_visual_class("arkham", "x")


def test_instantiate_visual_returns_fresh_instances():
    a = registry.instantiate_visual("joker", 2)
    b = registry.instantiate_visual("joker", 2)
    assert isinstance(a, JokerGrinningMaskVisual)
    assert a is not b
    assert a.disabled is False and a.lod_low is False
