"""Tests for core.hud.visuals.slots.two_face."""
from __future__ import annotations

import math

import pytest

from tests.hud_visuals._helpers import RECT, count_pixels, line_tuple, make_palette, rect_tuple, render

from core.hud.visuals.base import HudSignals
from core.hud.visuals.registry import get_visual_class
from core.hud.visuals.slots import two_face


@pytest.mark.parametrize("slot,cls", [
    (0, two_face.TwoFaceSplitMirrorVisual),
    (1, two_face.TwoFaceSilverDollarVisual),
    (2, two_face.TwoFaceBisectedVisual),
])
def test_registered_for_harvey_two_face_theme(slot, cls):
    assert get_visual_class("harvey_two_face", slot) is cls


def test_split_mirror_divider_bisects_panel():
    v = two_face.TwoFaceSplitMirrorVisual()
    v.prepare(make_palette(), RECT)
    assert line_tuple(v.mid_line) == (120.0, 22.0, 120.0, 132.0)
    assert v.pen_dirty.color().name() == "#00ff00"
    before = line_tuple(v.mid_line)
    v.tick(1.0, HudSignals(alert_level=3))
    assert line_tuple(v.mid_line) == before
    img = render(v, ticks=0)
    assert count_pixels(img, "r", y_min=25, y_max=130, x_min=118, x_max=123) > 90
    assert count_pixels(img, "r", y_min=25, x_max=110) == 0


def test_silver_dollar_rotation_and_edge_on_width():
    v = two_face.TwoFaceSilverDollarVisual()
    v.tick(0.5, HudSignals())
    assert v.rot == pytest.approx(1.5)
    v.tick(10.0, HudSignals())
    assert 0.0 <= v.rot < 2 * math.pi

    face_on = two_face.TwoFaceSilverDollarVisual()
    img_face = render(face_on, ticks=0)  # rot=0 -> full 32px wide coin
    edge_on = two_face.TwoFaceSilverDollarVisual()
    edge_on.prepare(make_palette(), RECT)
    edge_on.rot = math.pi / 2  # |cos| ~ 0 -> coin collapses to a sliver
    img_edge = render(edge_on, ticks=0, prepare=False)
    wide = count_pixels(img_face, "r", y_min=55, y_max=95, x_min=100, x_max=140)
    thin = count_pixels(img_edge, "r", y_min=55, y_max=95, x_min=100, x_max=140)
    assert wide > thin


def test_bisected_figure_draws_frame():
    v = two_face.TwoFaceBisectedVisual()
    v.prepare(make_palette(), RECT)
    assert rect_tuple(v.rect_inner) == (8.0, 18.0, 224.0, 116.0)
    img = render(v, ticks=0)
    # frame edges present, interior empty
    assert count_pixels(img, "r", y_min=30, y_max=120, x_min=6, x_max=11) > 80
    assert count_pixels(img, "r", y_min=30, y_max=120, x_min=30, x_max=210) == 0
