"""Tests for core.hud.visuals.slots.arkham."""
from __future__ import annotations

import pytest

from tests.hud_visuals._helpers import RECT, count_pixels, line_tuple, make_palette, rect_tuple, render

from core.hud.visuals.base import HudSignals
from core.hud.visuals.registry import get_visual_class
from core.hud.visuals.slots import arkham


@pytest.mark.parametrize("slot,cls", [
    (0, arkham.ArkhamFloorplanVisual),
    (1, arkham.ArkhamEEGVisual),
    (2, arkham.ArkhamVitalsVisual),
])
def test_registered_for_arkham_theme(slot, cls):
    assert get_visual_class("arkham", slot) is cls


def test_floorplan_lays_out_2x3_cell_grid():
    v = arkham.ArkhamFloorplanVisual()
    v.prepare(make_palette(), RECT)
    cw, ch = 224.0 / 3.0 - 4.0, 110.0 / 2.0 - 4.0
    assert rect_tuple(v.cells[0]) == pytest.approx((8.0, 22.0, cw, ch))
    assert rect_tuple(v.cells[5]) == pytest.approx((8.0 + 2 * (cw + 4.0), 22.0 + ch + 4.0, cw, ch))
    # cells do not overlap horizontally
    assert v.cells[0].right() < v.cells[1].left()


def test_floorplan_sweep_moves_and_wraps():
    v = arkham.ArkhamFloorplanVisual()
    v.prepare(make_palette(), RECT)
    v.tick(1.0, HudSignals())
    assert v.sweep_x == pytest.approx(0.4)
    assert line_tuple(v.sweep_line) == pytest.approx((8.0 + 0.4 * 224.0, 22.0, 8.0 + 0.4 * 224.0, 132.0))
    v.tick(2.0, HudSignals())
    assert v.sweep_x == pytest.approx(0.2)


def test_floorplan_paints_walls_and_sweep():
    img = render(arkham.ArkhamFloorplanVisual(), ticks=1, dt=1.0)
    assert count_pixels(img, "r", y_min=22) > 100  # cell walls
    sweep_x = int(8 + 0.4 * 224)
    assert count_pixels(img, "g", y_min=30, y_max=130, x_min=sweep_x - 2, x_max=sweep_x + 3) > 50


def test_eeg_agitation_speeds_up_phase():
    calm, agitated = arkham.ArkhamEEGVisual(), arkham.ArkhamEEGVisual()
    calm.tick(0.1, HudSignals(alert_level=0))
    agitated.tick(0.1, HudSignals(alert_level=2))
    assert calm.t == pytest.approx(0.4)
    assert agitated.t == pytest.approx(1.0)


def test_eeg_samples_bounded_and_drawn():
    v = arkham.ArkhamEEGVisual()
    v.prepare(make_palette(), RECT)
    v.tick(0.1, HudSignals())
    assert len(v.wave.samples) == 48
    assert all(abs(s) <= 1.0 + 1e-9 for s in v.wave.samples)
    img = render(v, ticks=1)
    assert count_pixels(img, "r", y_min=22) > 50


@pytest.mark.xfail(strict=True, reason=(
    "BUG: WaveTrace.layout() is only called in prepare(); tick() updates samples but "
    "never re-lays out the points, so the painted EEG trace stays a flat line."))
def test_eeg_drawn_trace_follows_samples():
    v = arkham.ArkhamEEGVisual()
    v.prepare(make_palette(), RECT)
    v.tick(0.1, HudSignals())
    assert len({round(p.y(), 3) for p in v.wave.points}) > 1


def test_vitals_pulse_ring_grows_with_phase():
    v = arkham.ArkhamVitalsVisual()
    v.tick(0.25, HudSignals())
    assert v.pulse == pytest.approx(0.5)
    v.tick(0.5, HudSignals())
    assert v.pulse == pytest.approx(0.5)  # wraps at 1.0
    small = render(arkham.ArkhamVitalsVisual(), ticks=0)
    big = arkham.ArkhamVitalsVisual()
    img_big = render(big, ticks=1, dt=0.45)  # pulse 0.9 -> r ~ 22
    # The larger ring reaches further from centre (120, 76) than the r=6 ring.
    assert count_pixels(small, "r", y_min=18, x_min=137) == 0
    assert count_pixels(img_big, "r", y_min=18, x_min=137) > 0
