"""Tests for core.hud.visuals.slots.freeze."""
from __future__ import annotations

import math

import pytest

from tests.hud_visuals._helpers import RECT, count_pixels, make_palette, rect_tuple, render

from core.hud.visuals.base import HudSignals
from core.hud.visuals.registry import get_visual_class
from core.hud.visuals.slots import freeze


@pytest.mark.parametrize("slot,cls", [
    (0, freeze.FreezeCoreLatticeVisual),
    (1, freeze.FreezeThermalColumnVisual),
    (2, freeze.FreezeCoolantLoopVisual),
])
def test_registered_for_mr_freeze_theme(slot, cls):
    assert get_visual_class("mr_freeze", slot) is cls


def test_lattice_six_equal_spokes_from_centre():
    v = freeze.FreezeCoreLatticeVisual()
    v.prepare(make_palette(), RECT)
    v.tick(0.2, HudSignals())
    assert v.rot == pytest.approx(0.1)
    r = 110.0 * 0.35
    angles = []
    for s in v.spokes:
        assert (s.x1(), s.y1()) == (120.0, 77.0)
        assert s.length() == pytest.approx(r, rel=0.02)
        angles.append(math.atan2(s.dy(), s.dx()))
    # spokes spaced ~60 degrees apart
    diffs = sorted(((b - a) % (2 * math.pi)) for a, b in zip(angles, angles[1:]))
    assert all(d == pytest.approx(math.pi / 3, abs=0.03) for d in diffs)


def test_lattice_paints_spokes():
    img = render(freeze.FreezeCoreLatticeVisual())
    assert count_pixels(img, "r", y_min=35, y_max=120, x_min=75, x_max=165) > 80


def test_thermal_column_fill_is_three_quarters_and_bottom_aligned():
    v = freeze.FreezeThermalColumnVisual()
    v.prepare(make_palette(), RECT)
    assert rect_tuple(v.col_rect) == pytest.approx((8 + 224 * 0.35, 24.0, 224 * 0.3, 104.0))
    v.tick(0.1, HudSignals())
    assert v.fill_rect.height() == pytest.approx(104.0 * 0.75)
    assert v.fill_rect.bottom() == pytest.approx(v.col_rect.bottom())
    assert v.fill_rect.width() == v.col_rect.width()


def test_thermal_column_paints_filled_region_only_in_lower_part():
    v = freeze.FreezeThermalColumnVisual()
    img = render(v, ticks=1)
    x0, x1 = int(v.col_rect.left()) + 3, int(v.col_rect.right()) - 3
    fill_top = int(v.fill_rect.top())
    filled = count_pixels(img, "r", y_min=fill_top + 3, y_max=int(v.col_rect.bottom()) - 2, x_min=x0, x_max=x1)
    empty = count_pixels(img, "r", y_min=int(v.col_rect.top()) + 3, y_max=fill_top - 2, x_min=x0, x_max=x1)
    assert filled > 1000
    assert empty == 0


def test_coolant_loop_centred_and_painted():
    v = freeze.FreezeCoolantLoopVisual()
    v.prepare(make_palette(), RECT)
    assert rect_tuple(v.loop_rect) == (96.0, 62.0, 48.0, 28.0)
    img = render(v, ticks=0)
    assert count_pixels(img, "r", y_min=58, y_max=95, x_min=92, x_max=148) > 30
    assert count_pixels(img, "r", y_min=100) == 0
