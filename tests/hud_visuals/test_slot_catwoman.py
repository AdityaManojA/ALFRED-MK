"""Tests for core.hud.visuals.slots.catwoman."""
from __future__ import annotations

import pytest

from tests.hud_visuals._helpers import RECT, count_pixels, line_tuple, make_palette, rect_tuple, render

from core.hud.visuals.base import HudSignals
from core.hud.visuals.registry import get_visual_class
from core.hud.visuals.slots import catwoman


@pytest.mark.parametrize("slot,cls", [
    (0, catwoman.CatwomanSonarVisual),
    (1, catwoman.CatwomanLockpickVisual),
    (2, catwoman.CatwomanAcrobatVisual),
])
def test_registered_for_catwoman_theme(slot, cls):
    assert get_visual_class("catwoman", slot) is cls


def test_sonar_grid_line_count_and_rebuild_is_idempotent():
    v = catwoman.CatwomanSonarVisual()
    v.prepare(make_palette(), RECT)
    # bw=224 -> 12 diagonal lines (0..220 step 20), bh=110 -> 6 horizontal lines
    assert len(v.grid_lines) == 12 + 6
    v.prepare(make_palette(), RECT)
    assert len(v.grid_lines) == 18  # cleared, not appended twice


def test_sonar_scan_advances_with_drift_and_clamps_band():
    calm, drifting = catwoman.CatwomanSonarVisual(), catwoman.CatwomanSonarVisual()
    for v in (calm, drifting):
        v.prepare(make_palette(), RECT)
    calm.tick(0.5, HudSignals(drift=0.0))
    drifting.tick(0.5, HudSignals(drift=0.5))
    assert calm.scan_y == pytest.approx(0.4)
    assert drifting.scan_y == pytest.approx(0.9)
    ly = 22.0 + 0.4 * 110.0
    assert line_tuple(calm.scan_line) == pytest.approx((8.0, ly, 232.0, ly))
    # Band top never goes above the panel top
    edge = catwoman.CatwomanSonarVisual()
    edge.prepare(make_palette(), RECT)
    edge.tick(0.0, HudSignals())
    assert edge.scan_rect.top() == pytest.approx(22.0)


def test_sonar_paints_laser_line():
    img = render(catwoman.CatwomanSonarVisual(), ticks=1, dt=0.5)
    ly = int(22 + 0.4 * 110)
    assert count_pixels(img, "g", y_min=ly - 1, y_max=ly + 2, x_min=10, x_max=230) > 150


def test_lockpick_pins_cycle_and_stay_above_shear():
    v = catwoman.CatwomanLockpickVisual()
    v.prepare(make_palette(), RECT)
    v.tick(0.5, HudSignals())
    # start [0.2, 0.5, 0.8, 0.4] + dt*(0.4 + i*0.2), wrapped to [0, 1)
    assert v.pins == pytest.approx([0.4, 0.8, 0.2, 0.9])
    shear_y = 20.0 + 112.0 * 0.4
    for i, line in enumerate(v.pin_lines):
        x1, y1, x2, y2 = line_tuple(line)
        assert x1 == x2 == pytest.approx(8.0 + (i + 1) * 224.0 / 5.0)
        assert y2 == pytest.approx(shear_y + 4.0)
        assert y1 == pytest.approx(shear_y - (6.0 + v.pins[i] * 18.0))


def test_lockpick_wave_amplitude_scales_with_mic():
    quiet, loud = catwoman.CatwomanLockpickVisual(), catwoman.CatwomanLockpickVisual()
    quiet.tick(0.1, HudSignals(mic_level=0.0))
    loud.tick(0.1, HudSignals(mic_level=1.0))
    assert max(abs(s) for s in quiet.wave.samples) <= 0.2 + 1e-9
    assert max(abs(s) for s in loud.wave.samples) > 0.5


def test_lockpick_paints_pins():
    img = render(catwoman.CatwomanLockpickVisual(), ticks=1)
    assert count_pixels(img, "r", y_min=20, y_max=70) > 20


@pytest.mark.xfail(strict=True, reason=(
    "BUG: acrobat x = left + width*(0.3 + 0.4*sin(phase)) spans [-0.1, 0.7] of the panel, "
    "so the figure's anchor leaves the panel on the left for part of every cycle."))
def test_acrobat_anchor_stays_inside_panel_horizontally():
    v = catwoman.CatwomanAcrobatVisual()
    v.prepare(make_palette(), RECT)
    for _ in range(40):
        v.tick(0.1, HudSignals())
        assert 8.0 <= v.body_lines[0].x1() <= 232.0


def test_acrobat_pose_vertical_arc_and_paints():
    v = catwoman.CatwomanAcrobatVisual()
    v.prepare(make_palette(), RECT)
    assert rect_tuple(v.rect_inner) == (8.0, 18.0, 224.0, 116.0)
    for _ in range(30):
        v.tick(0.1, HudSignals())
        _, y1, _, _ = line_tuple(v.body_lines[0])
        # cy = top + h*(0.5 - 0.3*|cos|) -> between 20% and 50% of the panel height
        assert 18.0 + 116.0 * 0.2 - 1e-6 <= y1 <= 18.0 + 116.0 * 0.5 + 1e-6
        # every limb starts from the hip/torso anchor or a connected joint
        assert line_tuple(v.body_lines[2])[:2] == line_tuple(v.body_lines[0])[2:]
    img = render(v, prepare=False, ticks=0)
    assert count_pixels(img, "r", y_min=20) > 20
