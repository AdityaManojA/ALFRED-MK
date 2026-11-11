"""Tests for core.hud.visuals.slots.joker."""
from __future__ import annotations

import math

import pytest

from tests.hud_visuals._helpers import RECT, count_pixels, make_palette, rect_tuple, render

from core.hud.visuals.base import HudSignals
from core.hud.visuals.registry import get_visual_class
from core.hud.visuals.slots import joker


@pytest.mark.parametrize("slot,cls", [
    (0, joker.JokerCardScatterVisual),
    (1, joker.JokerLaughWaveVisual),
    (2, joker.JokerGrinningMaskVisual),
])
def test_registered_for_joker_theme(slot, cls):
    assert get_visual_class("joker", slot) is cls


def test_card_scatter_prepare_and_tick_geometry():
    v = joker.JokerCardScatterVisual()
    v.prepare(make_palette(), RECT)
    assert rect_tuple(v.rect_inner) == (8.0, 22.0, 224.0, 110.0)
    assert v.pen_card.color().name() == "#00ff00"
    assert v.brush_card.color().alpha() == 50
    v.tick(0.1, HudSignals())
    assert v.t == pytest.approx(0.25)
    cx, cy = 120.0, 77.0
    for card in v.cards:
        assert (card.width(), card.height()) == (16.0, 24.0)
        assert abs(card.center().x() - cx) <= 22.0 + 1e-6
        assert abs(card.center().y() - cy) <= 14.0 + 1e-6


def test_card_scatter_phase_wraps():
    v = joker.JokerCardScatterVisual()
    v.prepare(make_palette(), RECT)
    v.tick(100.0, HudSignals())
    assert 0.0 <= v.t < 2 * math.pi


def test_card_scatter_paints_cards_in_accent():
    img = render(joker.JokerCardScatterVisual())
    assert count_pixels(img, "g", y_min=40, y_max=120) > 40


def test_laugh_wave_samples_bounded_and_drawn():
    v = joker.JokerLaughWaveVisual()
    v.prepare(make_palette(), RECT)
    v.tick(0.1, HudSignals())
    assert len(v.wave.samples) == 40
    assert all(-1.0 <= s <= 1.0 for s in v.wave.samples)
    assert any(abs(s) > 0.05 for s in v.wave.samples)
    img = render(v, ticks=1)
    assert count_pixels(img, "g", y_min=22) > 30


@pytest.mark.xfail(strict=True, reason=(
    "BUG: WaveTrace.layout() is only called in prepare(); tick() updates samples but "
    "never re-lays out the points, so the painted laugh trace stays a flat line."))
def test_laugh_wave_drawn_trace_follows_samples():
    v = joker.JokerLaughWaveVisual()
    v.prepare(make_palette(), RECT)
    v.tick(0.1, HudSignals())
    assert len({round(p.y(), 3) for p in v.wave.points}) > 1


def test_grinning_mask_tick_is_noop_and_paints_smile():
    v = joker.JokerGrinningMaskVisual()
    v.prepare(make_palette(), RECT)
    assert rect_tuple(v.rect_inner) == (8.0, 18.0, 224.0, 116.0)
    before = rect_tuple(v.rect_inner)
    v.tick(1.0, HudSignals(cpu_pct=99))
    assert rect_tuple(v.rect_inner) == before
    img = render(v, ticks=0)
    # Smile arc is drawn around the panel centre (120, 76) in primary red.
    assert count_pixels(img, "r", y_min=66, y_max=100, x_min=95, x_max=145) > 10
    assert count_pixels(img, "r", y_min=110) == 0
