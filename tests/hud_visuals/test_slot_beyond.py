"""Tests for core.hud.visuals.slots.beyond."""
from __future__ import annotations

import pytest

from tests.hud_visuals._helpers import RECT, count_pixels, make_palette, rect_tuple, render

from core.hud.visuals.base import HudSignals
from core.hud.visuals.registry import get_visual_class
from core.hud.visuals.slots import beyond


@pytest.mark.parametrize("slot,cls", [
    (0, beyond.BeyondRetinalVisual),
    (1, beyond.BeyondICELadderVisual),
    (2, beyond.BeyondAvatarVisual),
])
def test_registered_for_beyond_theme(slot, cls):
    assert get_visual_class("beyond", slot) is cls


def test_retinal_prepare_reuses_rect_objects():
    v = beyond.BeyondRetinalVisual()
    inner, hdr = v.rect_inner, v.rect_hdr
    v.prepare(make_palette(), RECT)
    assert v.rect_inner is inner and v.rect_hdr is hdr
    assert rect_tuple(inner) == (8.0, 22.0, 224.0, 110.0)
    assert rect_tuple(hdr) == (8.0, 4.0, 224.0, 14.0)
    assert v.pen_mesh.color().alpha() == 45


def test_retinal_lock_orbits_centre_within_bounds():
    v = beyond.BeyondRetinalVisual()
    v.prepare(make_palette(), RECT)
    for _ in range(40):
        v.tick(0.07, HudSignals())
        assert abs(v.lock_x - 120.0) <= 20.0 + 1e-6
        assert abs(v.lock_y - 77.0) <= 12.0 + 1e-6


def test_retinal_paints_bracket_at_lock_point():
    v = beyond.BeyondRetinalVisual()
    img = render(v, ticks=2)
    lx, ly = int(v.lock_x), int(v.lock_y)
    assert count_pixels(img, "g", y_min=ly - 8, y_max=ly + 9, x_min=lx - 8, x_max=lx + 9) > 15
    assert count_pixels(img, "g", y_min=22, x_max=lx - 20) == 0


def test_ice_ladder_values_scale_with_bandwidth():
    lo, hi = beyond.BeyondICELadderVisual(), beyond.BeyondICELadderVisual()
    lo.tick(1.0, HudSignals(net_kbps=0))
    hi.tick(1.0, HudSignals(net_kbps=350))
    assert all(0.0 <= x <= 0.3 + 1e-9 for x in lo.bars.values)
    assert sum(hi.bars.values) > sum(lo.bars.values) * 2


def test_ice_ladder_layout_eight_bars_inside_panel():
    v = beyond.BeyondICELadderVisual()
    v.prepare(make_palette(), RECT)
    rects = v.bars.rects
    assert len(rects) == 8
    assert rects[0].left() == pytest.approx(16.0)
    assert rects[-1].right() == pytest.approx(16.0 + 224.0 - 16.0)
    img = render(v)
    assert count_pixels(img, "r", y_min=100) > 8


def test_avatar_limb_modules_layout():
    v = beyond.BeyondAvatarVisual()
    v.prepare(make_palette(), RECT)
    cx, cy = 120.0, 76.0
    head, torso, larm, rarm, legs = (rect_tuple(r) for r in v.limbs)
    assert head == (cx - 6, cy - 22, 12, 10)
    assert torso == (cx - 10, cy - 10, 20, 16)
    assert larm[0] < torso[0] < rarm[0]
    assert legs[1] > torso[1]
    img = render(v, ticks=0)
    assert count_pixels(img, "r", y_min=50, y_max=105, x_min=95, x_max=145) > 50
