"""Tests for core.hud.visuals.slots.batcave (default 'dossier' theme visuals)."""
from __future__ import annotations

import math

import pytest

from tests.hud_visuals._helpers import RECT, count_pixels, make_palette, rect_tuple, render

from core.hud.visuals.base import HudSignals
from core.hud.visuals.registry import get_visual_class
from core.hud.visuals.slots import batcave


@pytest.mark.parametrize("slot,cls", [
    (0, batcave.BatcaveRadarVisual),
    (1, batcave.BatcaveSpectrumVisual),
    (2, batcave.BatcaveBlueprintVisual),
])
def test_registered_for_dossier_and_as_fallback(slot, cls):
    assert get_visual_class("dossier", slot) is cls
    assert get_visual_class("unknown-theme", slot) is cls


# ── Radar ────────────────────────────────────────────────────────────────────
def test_radar_prepare_geometry():
    v = batcave.BatcaveRadarVisual()
    v.prepare(make_palette(), RECT)
    assert (v.cx, v.cy) == (120.0, 77.0)
    assert v.radius == pytest.approx(110.0 * 0.42)
    assert v.crosshair_h.length() == pytest.approx(2 * v.radius)
    assert v.crosshair_v.length() == pytest.approx(2 * v.radius)
    assert len(v.blip_points) == v.radar.max_blips == 8


def test_radar_sweep_speed_rises_with_alert_level():
    calm, alarmed = batcave.BatcaveRadarVisual(), batcave.BatcaveRadarVisual()
    for v in (calm, alarmed):
        v.prepare(make_palette(), RECT)
    calm.tick(0.1, HudSignals(alert_level=0))
    alarmed.tick(0.1, HudSignals(alert_level=2))
    assert calm.radar.angle == pytest.approx(0.2)
    assert alarmed.radar.angle == pytest.approx(0.5)
    assert calm.reticle_angle1 == pytest.approx(0.05)
    assert calm.reticle_angle2 == pytest.approx(2 * math.pi - 0.07)


def test_radar_blip_distance_and_size_follow_cpu():
    v = batcave.BatcaveRadarVisual()
    v.prepare(make_palette(), RECT)
    v.tick(0.1, HudSignals(cpu_pct=60.0))
    expected_r = v.radius * 0.7 * (0.3 + 60.0 / 150.0)
    p = v.blip_points[0]
    assert math.hypot(p.x() - v.cx, p.y() - v.cy) == pytest.approx(expected_r, rel=0.02)
    assert v.radar.blip_size[0] == pytest.approx(6.0)
    assert v.radar.blip_alpha[0] == 1.0


def test_radar_reticle_ticks_sit_on_outer_ring():
    v = batcave.BatcaveRadarVisual()
    v.prepare(make_palette(), RECT)
    v.tick(0.1, HudSignals())
    for line in v.reticle_lines1:
        d_outer = math.hypot(line.x2() - v.cx, line.y2() - v.cy)
        assert d_outer == pytest.approx(v.radius, rel=0.02)
        assert line.length() == pytest.approx(4.0, abs=0.3)


def test_radar_paints_blip_in_accent():
    v = batcave.BatcaveRadarVisual()
    img = render(v, ticks=1, signals=HudSignals(cpu_pct=60.0))
    bx, by = int(v.blip_points[0].x()), int(v.blip_points[0].y())
    assert count_pixels(img, "g", y_min=by - 5, y_max=by + 6, x_min=bx - 5, x_max=bx + 6) > 10


# ── Spectrum ─────────────────────────────────────────────────────────────────
def test_time_step_is_deterministic():
    assert batcave.time_step(0) == 0.0
    assert batcave.time_step(1) == pytest.approx(1.7)
    assert batcave.time_step(2) == pytest.approx(0.3)  # 34 % 31 = 3
    assert [batcave.time_step(i) for i in range(16)] == [batcave.time_step(i) for i in range(16)]


def test_spectrum_silence_vs_loud_levels():
    quiet, loud = batcave.BatcaveSpectrumVisual(), batcave.BatcaveSpectrumVisual()
    quiet.tick(1.0, HudSignals())
    loud.tick(1.0, HudSignals(mic_level=0.2, sys_audio_level=1.0))  # uses the max of both
    assert max(quiet.sim_values) <= 0.05 + 1e-9
    assert all(v <= 1.0 for v in loud.sim_values)
    # envelope factor is >= 0.3, so level 1.0 * 0.3 * 1.5 - 0.05 jitter keeps every band > 0.4
    assert min(loud.bars.values) > 0.4
    assert sum(loud.bars.values) > 10 * sum(quiet.bars.values)
    assert all(0.0 <= v <= 0.05 + 1e-9 for v in quiet.bars.values)


def test_spectrum_prepare_lays_out_16_bars_in_panel():
    v = batcave.BatcaveSpectrumVisual()
    v.prepare(make_palette(), RECT)
    assert rect_tuple(v.rect_inner) == (8.0, 20.0, 224.0, 112.0)
    assert v.bars.rects[0].left() == pytest.approx(12.0)
    assert v.bars.rects[15].right() == pytest.approx(12.0 + 216.0, abs=0.01)
    assert v.pen_peak.color().name() == "#0000ff"  # acc2 drives the peak caps


def test_spectrum_peak_colour_falls_back_to_acc():
    v = batcave.BatcaveSpectrumVisual()
    v.prepare(make_palette(acc2=""), RECT)
    assert v.pen_peak.color().name() == "#00ff00"


@pytest.mark.xfail(strict=True, reason=(
    "BUG: BarArray.layout() is only called in prepare(); tick() updates values but the bar "
    "rects are never recomputed, so the painted spectrum never rises above 1px."))
def test_spectrum_bar_heights_follow_audio():
    v = batcave.BatcaveSpectrumVisual()
    v.prepare(make_palette(), RECT)
    v.tick(1.0, HudSignals(mic_level=1.0))
    assert v.bars.rects[0].height() > 10.0


# ── Blueprint ────────────────────────────────────────────────────────────────
def test_batwing_mesh_edges_reference_valid_vertices():
    n = len(batcave.BATWING_VERTICES)
    for a, b in batcave.BATWING_EDGES:
        assert 0 <= a < n and 0 <= b < n and a != b
    # Mesh is left/right mirror-symmetric in x
    xs = sorted(round(x, 3) for x, _, _ in batcave.BATWING_VERTICES)
    assert xs == sorted(-x for x in xs)


def test_blueprint_yaw_speed_depends_on_cpu_and_wraps():
    v = batcave.BatcaveBlueprintVisual()
    v.prepare(make_palette(), RECT)
    v.tick(1.0, HudSignals(cpu_pct=20.0))
    assert v.yaw == pytest.approx(1.0)
    assert (v.model.cx, v.model.cy, v.model.scale) == (120.0, 76.0, 0.85)
    v.tick(100.0, HudSignals())
    assert 0.0 <= v.yaw < 2 * math.pi


def test_blueprint_paints_wireframe_around_centre():
    v = batcave.BatcaveBlueprintVisual()
    img = render(v, ticks=2)
    assert count_pixels(img, "r", y_min=35, y_max=115, x_min=60, x_max=180) > 80
