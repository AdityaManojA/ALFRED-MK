"""Tests for core.hud.visuals.primitives — geometry/math of the shared HUD primitives."""
from __future__ import annotations

import math

import pytest
from PyQt6.QtGui import QColor, QImage, QPainter, QPen
from PyQt6.QtCore import Qt

from tests.hud_visuals._helpers import count_pixels, line_tuple, rect_tuple

from core.hud.visuals import primitives
from core.hud.visuals.primitives import BarArray, RadarSweep, WaveTrace, Wireframe3D


# ── Wireframe3D ──────────────────────────────────────────────────────────────
def test_wireframe_identity_projection_is_scale_and_translate():
    wf = Wireframe3D([(10.0, 0.0, 0.0), (0.0, -20.0, 0.0)], [(0, 1)])
    wf.update_geometry(100.0, 50.0, 2.0, yaw=0.0, pitch=0.0, roll=0.0)
    p0, p1 = wf.transformed_points
    assert (p0.x(), p0.y()) == pytest.approx((120.0, 50.0))
    assert (p1.x(), p1.y()) == pytest.approx((100.0, 10.0))
    assert line_tuple(wf.edge_lines[0]) == pytest.approx((120.0, 50.0, 100.0, 10.0))
    assert (wf.cx, wf.cy, wf.scale) == (100.0, 50.0, 2.0)


def test_wireframe_yaw_half_turn_mirrors_x():
    wf = Wireframe3D([(10.0, 0.0, 0.0)], [])
    wf.update_geometry(0.0, 0.0, 1.0, yaw=math.pi, pitch=0.0)
    p = wf.transformed_points[0]
    assert p.x() == pytest.approx(-10.0, abs=0.2)
    assert p.y() == pytest.approx(0.0, abs=0.2)


def test_wireframe_roll_quarter_turn_rotates_into_y():
    wf = Wireframe3D([(10.0, 0.0, 0.0)], [])
    wf.update_geometry(0.0, 0.0, 1.0, yaw=0.0, pitch=0.0, roll=math.pi / 2)
    p = wf.transformed_points[0]
    assert p.x() == pytest.approx(0.0, abs=0.2)
    assert p.y() == pytest.approx(10.0, abs=0.2)


def test_wireframe_perspective_depth_shrinks_far_points():
    near = Wireframe3D([(10.0, 0.0, -100.0)], [])
    far = Wireframe3D([(10.0, 0.0, 100.0)], [])
    for wf in (near, far):
        wf.update_geometry(0.0, 0.0, 1.0, 0.0, 0.0)
    # pz = 1 + z*0.002 -> 0.8 for near (bigger), 1.2 for far (smaller)
    assert near.transformed_points[0].x() == pytest.approx(10.0 / 0.8)
    assert far.transformed_points[0].x() == pytest.approx(10.0 / 1.2)


def test_wireframe_reuses_point_objects():
    wf = Wireframe3D([(1.0, 1.0, 0.0)], [(0, 0)])
    pt, line = wf.transformed_points[0], wf.edge_lines[0]
    wf.update_geometry(5.0, 5.0, 1.0, 0.3, 0.2)
    assert wf.transformed_points[0] is pt and wf.edge_lines[0] is line


def test_wireframe_draw_paints_edges():
    wf = Wireframe3D([(-30.0, 0.0, 0.0), (30.0, 0.0, 0.0)], [(0, 1)])
    wf.update_geometry(50.0, 25.0, 1.0, 0.0, 0.0)
    img = QImage(100, 50, QImage.Format.Format_RGBA8888)
    img.fill(Qt.GlobalColor.black)
    p = QPainter(img)
    wf.draw(p, QPen(QColor("#FF0000"), 2.0))
    p.end()
    assert count_pixels(img, "r", y_min=23, y_max=28, x_min=20, x_max=80) >= 50
    assert count_pixels(img, "r", y_max=15) == 0


# ── RadarSweep ───────────────────────────────────────────────────────────────
def test_radar_tick_advances_and_wraps_angle():
    r = RadarSweep(max_blips=2)
    r.tick(1.0, speed_rad_per_s=1.0)
    assert r.angle == pytest.approx(1.0)
    r.tick(10.0, speed_rad_per_s=1.0)
    assert 0.0 <= r.angle < 2 * math.pi
    assert r.angle == pytest.approx((11.0) % (2 * math.pi))


def test_radar_blip_trigger_and_fade_clamps_at_zero():
    r = RadarSweep(max_blips=3)
    r.trigger_blip(1, 4.0, 5.0, size=6.0, alpha=1.0)
    assert (r.blip_x[1], r.blip_y[1], r.blip_size[1], r.blip_alpha[1]) == (4.0, 5.0, 6.0, 1.0)
    r.tick(0.5)
    assert r.blip_alpha[1] == pytest.approx(0.6)
    r.tick(5.0)
    assert r.blip_alpha[1] == 0.0
    assert r.blip_alpha[0] == 0.0  # untouched blips stay dark


@pytest.mark.parametrize("idx", [-1, 3, 100])
def test_radar_out_of_range_blip_is_ignored(idx):
    r = RadarSweep(max_blips=3)
    r.trigger_blip(idx, 1.0, 1.0)
    assert r.blip_alpha == [0.0, 0.0, 0.0]


def test_radar_sweep_line_endpoint_on_circle():
    r = RadarSweep()
    r.angle = 0.0
    r.update_sweep_line(10.0, 20.0, 5.0)
    assert line_tuple(r.sweep_line) == pytest.approx((10.0, 20.0, 15.0, 20.0))
    r.angle = math.pi / 2
    r.update_sweep_line(10.0, 20.0, 5.0)
    assert line_tuple(r.sweep_line) == pytest.approx((10.0, 20.0, 10.0, 25.0), abs=0.05)


# ── BarArray ─────────────────────────────────────────────────────────────────
def test_bar_values_clamped_and_follow_target():
    b = BarArray(count=3)
    b.tick(1.0, [2.0, -1.0, 0.5])  # dt*14 >= 1 -> snaps to target
    assert b.values == pytest.approx([1.0, 0.0, 0.5])
    assert b.peaks == pytest.approx([1.0, 0.0, 0.5])


def test_bar_partial_follow_with_small_dt():
    b = BarArray(count=1)
    b.tick(0.05, [1.0])  # factor 0.7
    assert b.values[0] == pytest.approx(0.7)


def test_bar_peak_holds_then_decays():
    b = BarArray(count=1, peak_decay_per_s=1.0)
    b.tick(1.0, [0.8])
    b.tick(1.0, [0.1])
    assert b.values[0] == pytest.approx(0.1)
    # Peak decays linearly by rate*dt but not below 0
    assert b.peaks[0] == pytest.approx(0.0)
    b2 = BarArray(count=1, peak_decay_per_s=0.5)
    b2.tick(1.0, [0.8])
    b2.tick(0.1, [0.0])
    assert b2.peaks[0] == pytest.approx(0.75)


def test_bar_tick_tolerates_short_input():
    b = BarArray(count=4)
    b.tick(1.0, (1.0,))
    assert b.values == pytest.approx([1.0, 0.0, 0.0, 0.0])


def test_bar_layout_geometry():
    b = BarArray(count=2)
    b.values = [0.5, 0.0]
    b.peaks = [1.0, 0.25]
    b.layout(0.0, 0.0, 22.0, 100.0, gap=2.0)
    assert rect_tuple(b.rects[0]) == pytest.approx((0.0, 50.0, 10.0, 50.0))
    # zero height bar still gets a 1px minimum
    assert rect_tuple(b.rects[1]) == pytest.approx((12.0, 100.0, 10.0, 1.0))
    assert line_tuple(b.peak_lines[0]) == pytest.approx((0.0, 0.0, 10.0, 0.0))
    assert line_tuple(b.peak_lines[1]) == pytest.approx((12.0, 75.0, 22.0, 75.0))


def test_bar_layout_minimum_width_one():
    b = BarArray(count=10)
    b.layout(0.0, 0.0, 5.0, 10.0, gap=2.0)
    assert b.rects[0].width() == 1.0


# ── WaveTrace ────────────────────────────────────────────────────────────────
def test_wave_update_samples_truncates_and_keeps_tail():
    w = WaveTrace(sample_count=4)
    w.update_samples([1, 2, 3, 4, 5, 6])
    assert w.samples == [1.0, 2.0, 3.0, 4.0]
    w.update_samples([9])
    assert w.samples == [9.0, 2.0, 3.0, 4.0]


def test_wave_layout_points_and_lines():
    w = WaveTrace(sample_count=3)
    w.update_samples([0.0, 1.0, -1.0])
    w.layout(10.0, 50.0, 20.0, 5.0)
    pts = [(p.x(), p.y()) for p in w.points]
    assert pts == pytest.approx([(10.0, 50.0), (20.0, 55.0), (30.0, 45.0)])
    assert len(w.lines) == 2
    assert line_tuple(w.lines[1]) == pytest.approx((20.0, 55.0, 30.0, 45.0))


def test_wave_single_sample_does_not_divide_by_zero():
    w = WaveTrace(sample_count=1)
    w.layout(3.0, 4.0, 100.0, 1.0)
    assert (w.points[0].x(), w.points[0].y()) == (3.0, 4.0)
    assert w.lines == []
