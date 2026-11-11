"""Tests for core.hud.visuals.slots.riddler."""
from __future__ import annotations

import math

import pytest

from tests.hud_visuals._helpers import RECT, count_pixels, line_tuple, make_palette, rect_tuple, render

from core.hud.visuals.base import HudSignals
from core.hud.visuals.registry import get_visual_class
from core.hud.visuals.slots import riddler


@pytest.mark.parametrize("slot,cls", [
    (0, riddler.RiddlerCipherVisual),
    (1, riddler.RiddlerLogicGatesVisual),
    (2, riddler.RiddlerMazeVisual),
])
def test_registered_for_riddler_theme(slot, cls):
    assert get_visual_class("riddler", slot) is cls


def test_cipher_speed_scales_with_cpu_and_wraps():
    idle, busy = riddler.RiddlerCipherVisual(), riddler.RiddlerCipherVisual()
    idle.tick(0.1, HudSignals(cpu_pct=0))
    busy.tick(0.1, HudSignals(cpu_pct=50))
    assert idle.t == pytest.approx(0.15)
    assert busy.t == pytest.approx(0.25)
    busy.tick(1000.0, HudSignals())
    assert 0.0 <= busy.t < 2 * math.pi


def test_cipher_glyph_set_and_frame_paint():
    v = riddler.RiddlerCipherVisual()
    assert len(v.glyphs) == 8 and v.glyphs[0] == "?"
    v.prepare(make_palette(), RECT)
    assert rect_tuple(v.rect_inner) == (8.0, 22.0, 224.0, 110.0)
    assert v.pen_dim.color().alpha() == 50
    img = render(v, ticks=1)
    # Dim (alpha 50) primary frame around the glyph matrix: faint red, never full-strength.
    assert count_pixels(img, "r", y_min=30, y_max=125, x_min=6, x_max=11, threshold=35) > 80
    assert count_pixels(img, "r", y_min=30, y_max=125, x_min=6, x_max=11, threshold=100) == 0


def test_logic_gates_tree_connects_into_output():
    v = riddler.RiddlerLogicGatesVisual()
    v.prepare(make_palette(), RECT)
    cx, cy = 120.0, 76.0
    l = [line_tuple(x) for x in v.lines]
    # two inputs converge on the gate centre, which feeds the output line to the right edge
    assert l[2][2:] == (cx, cy) and l[3][2:] == (cx, cy)
    assert l[4] == (cx, cy, cx + 18, cy)
    assert l[5] == (cx + 18, cy, 8.0 + 224.0 - 8, cy)
    v.tick(0.5, HudSignals())
    assert v.t == pytest.approx(2.0)
    img = render(v, ticks=0)
    assert count_pixels(img, "r", y_min=int(cy) - 1, y_max=int(cy) + 2, x_min=int(cx) + 2, x_max=220) > 80


def test_maze_dot_orbits_centre():
    v = riddler.RiddlerMazeVisual()
    v.prepare(make_palette(), RECT)
    for _ in range(25):
        v.tick(0.1, HudSignals())
        assert abs(v.dot_pos.x() - 120.0) <= 16.0 + 1e-6
        assert abs(v.dot_pos.y() - 76.0) <= 8.0 + 1e-6


def test_maze_outer_wall_has_exit_gap_on_right():
    v = riddler.RiddlerMazeVisual()
    v.prepare(make_palette(), RECT)
    right_top, right_bottom = line_tuple(v.maze_lines[3]), line_tuple(v.maze_lines[4])
    assert right_top[3] < right_bottom[1]  # gap between the two right-wall segments
    img = render(v, ticks=1)
    assert count_pixels(img, "r", y_min=55, y_max=95, x_min=90, x_max=150) > 60
    assert count_pixels(img, "g", y_min=60, y_max=95, x_min=100, x_max=140) > 3  # the blip
