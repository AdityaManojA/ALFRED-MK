"""Tests for core.hud.visuals.slots.watchtower."""
from __future__ import annotations

import math

import pytest

from tests.hud_visuals._helpers import RECT, count_pixels, make_palette, rect_tuple, render

from core.hud.visuals.base import HudSignals
from core.hud.visuals.registry import get_visual_class
from core.hud.visuals.slots import watchtower


@pytest.mark.parametrize("slot,cls", [
    (0, watchtower.WatchtowerFluxRingVisual),
    (1, watchtower.WatchtowerPowerOutputVisual),
    (2, watchtower.WatchtowerHoloManVisual),
])
def test_registered_for_watchtower_theme(slot, cls):
    assert get_visual_class("watchtower", slot) is cls


def test_flux_ring_rotation_wraps():
    v = watchtower.WatchtowerFluxRingVisual()
    v.tick(1.0, HudSignals())
    assert v.rot == pytest.approx(1.5)
    v.tick(100.0, HudSignals())
    assert 0.0 <= v.rot < 2 * math.pi


def test_flux_ring_paints_outer_primary_and_inner_accent_rings():
    v = watchtower.WatchtowerFluxRingVisual()
    v.prepare(make_palette(), RECT)
    assert v.pen_reticle.style().name == "DashLine"
    img = render(v, ticks=0)
    cx, cy, r = 120, 77, 110.0 * 0.38
    outer_x = int(cx + r)
    inner_x = int(cx + r * 0.65)
    assert count_pixels(img, "r", y_min=cy - 6, y_max=cy + 7, x_min=outer_x - 2, x_max=outer_x + 3) > 3
    assert count_pixels(img, "g", y_min=cy - 15, y_max=cy + 16, x_min=inner_x - 2, x_max=inner_x + 3) > 3
    assert count_pixels(img, "r", y_min=cy - 3, y_max=cy + 4, x_min=cx - 3, x_max=cx + 4) == 0


def test_power_output_draws_arc_above_centre():
    v = watchtower.WatchtowerPowerOutputVisual()
    v.prepare(make_palette(), RECT)
    assert rect_tuple(v.rect_inner) == (8.0, 20.0, 224.0, 112.0)
    img = render(v, ticks=0)
    # arc spans 30..150 degrees -> upper half of the 60x40 ellipse around (120, 76)
    assert count_pixels(img, "r", y_min=52, y_max=70, x_min=88, x_max=152) > 20
    assert count_pixels(img, "r", y_min=80, y_max=100, x_min=88, x_max=152) == 0


def test_holo_man_frame_and_noop_tick():
    v = watchtower.WatchtowerHoloManVisual()
    v.prepare(make_palette(), RECT)
    before = rect_tuple(v.rect_inner)
    v.tick(5.0, HudSignals(cpu_pct=100))
    assert rect_tuple(v.rect_inner) == before == (8.0, 18.0, 224.0, 116.0)
    img = render(v, ticks=0)
    assert count_pixels(img, "r", y_min=132, y_max=136, x_min=20, x_max=220) > 150
