"""Tests for core.hud.visuals.slots.bane."""
from __future__ import annotations

import pytest

from tests.hud_visuals._helpers import RECT, count_pixels, line_tuple, make_palette, rect_tuple, render

from core.hud.visuals.base import HudSignals
from core.hud.visuals.registry import get_visual_class
from core.hud.visuals.slots import bane


@pytest.mark.parametrize("slot,cls", [
    (0, bane.BanePressureChamberVisual),
    (1, bane.BaneDosageRegulatorVisual),
    (2, bane.BaneMaskSchematicVisual),
])
def test_registered_for_vector_theme(slot, cls):
    assert get_visual_class("vector", slot) is cls


def test_pressure_chamber_speed_scales_with_cpu():
    idle, busy = bane.BanePressureChamberVisual(), bane.BanePressureChamberVisual()
    idle.tick(0.1, HudSignals(cpu_pct=0))
    busy.tick(0.1, HudSignals(cpu_pct=50))
    assert idle.t == pytest.approx(0.3)
    assert busy.t == pytest.approx(0.5)


def test_pressure_chamber_samples_have_systolic_peak_at_centre():
    v = bane.BanePressureChamberVisual()
    v.t = 0.0
    v.tick(0.25, HudSignals())  # t=0.75 -> sin(1.5) ~ 1 -> strong systolic spike
    s = v.wave.samples
    assert len(s) == 48
    assert all(abs(x) <= 1.6 + 1e-9 for x in s)
    # Gaussian systolic spike is centred around index 24 and dominates the edges.
    assert abs(s[24]) > abs(s[0])
    assert abs(s[24]) > 0.8


def test_pressure_chamber_paints_border_and_trace():
    v = bane.BanePressureChamberVisual()
    v.prepare(make_palette(), RECT)
    assert rect_tuple(v.rect_inner) == (8.0, 22.0, 224.0, 110.0)
    assert v.pen_border.color().alpha() == 50
    img = render(v)
    assert count_pixels(img, "r", y_min=60, y_max=95) > 100  # centre trace in primary


def test_dosage_regulator_bars_track_cpu_and_mem():
    v = bane.BaneDosageRegulatorVisual()
    v.tick(1.0, HudSignals(cpu_pct=50, mem_pct=95))
    assert v.bars.values == pytest.approx([0.6, 1.0])


def test_dosage_regulator_layout_two_centred_columns():
    v = bane.BaneDosageRegulatorVisual()
    v.prepare(make_palette(), RECT)
    r0, r1 = v.bars.rects
    # columns live inside the central half of the inner panel
    assert r0.left() == pytest.approx(8.0 + 224.0 * 0.25)
    assert r1.right() == pytest.approx(8.0 + 224.0 * 0.75)
    assert r1.left() - r0.right() == pytest.approx(16.0)


@pytest.mark.xfail(strict=True, reason=(
    "BUG: BarArray.layout() is only called in prepare(); tick() updates values but the "
    "column rects are never recomputed, so the painted columns stay at their 1px minimum."))
def test_dosage_regulator_column_height_follows_load():
    v = bane.BaneDosageRegulatorVisual()
    v.prepare(make_palette(), RECT)
    v.tick(1.0, HudSignals(cpu_pct=90, mem_pct=90))
    assert v.bars.rects[0].height() > 10.0


def test_mask_schematic_tubes_symmetric_about_centre():
    v = bane.BaneMaskSchematicVisual()
    v.prepare(make_palette(), RECT)
    cx = 120.0
    l0, l1 = line_tuple(v.tubes[0]), line_tuple(v.tubes[1])
    assert cx - l0[0] == pytest.approx(l1[0] - cx)
    assert l0[1] == l1[1]
    assert line_tuple(v.tubes[5])[0] == pytest.approx(cx)  # vertical centre tube


def test_mask_schematic_pulse_wraps_and_paints():
    v = bane.BaneMaskSchematicVisual()
    v.tick(10.0, HudSignals())
    assert 0.0 <= v.pulse < 6.2832
    img = render(bane.BaneMaskSchematicVisual(), ticks=0)
    assert count_pixels(img, "r", y_min=50, y_max=100, x_min=90, x_max=150) > 40
