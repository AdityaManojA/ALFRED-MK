"""
tests/hud_video/test_surface.py — Headless tests for HudVideoSurface state handling,
theme application, toast/badge behaviour, and the spinner widget.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6.QtMultimediaWidgets")

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication(["test", "-platform", "offscreen"])

from core.hud_video import surface as surface_mod
from core.hud_video.controller import HudVideoController, VideoState
from core.hud_video.surface import (
    SURFACE_SPINNER_INTERVAL_MS,
    SURFACE_TOAST_DURATION_MS,
    HudVideoSurface,
    _SpinnerWidget,
)


@pytest.fixture
def surf():
    ctrl = HudVideoController()
    s = HudVideoSurface(ctrl)
    s.resize(400, 300)
    yield s, ctrl
    s._spinner.stop()
    s.deleteLater()


def test_initial_layout(surf):
    s, _ = surf
    assert s._content_stack.count() == 3
    assert s._content_stack.currentIndex() == 0
    assert s._close_btn.isHidden()
    assert s._controls_strip.isHidden()
    assert s.video_widget() is s._content_stack.widget(1)


@pytest.mark.parametrize("state, index, spinning, strip_hidden", [
    (VideoState.RESOLVING, 0, True, True),
    (VideoState.LOADING, 0, True, True),
    (VideoState.PLAYING, 1, False, False),
    (VideoState.PAUSED, 1, False, False),
    (VideoState.ENDED, 1, False, False),
    (VideoState.ERROR, 2, False, True),
])
def test_state_changes_switch_panels(surf, state, index, spinning, strip_hidden):
    s, ctrl = surf
    ctrl.state_changed.emit(state)
    assert s._content_stack.currentIndex() == index
    assert s._spinner._timer.isActive() is spinning
    assert not s._close_btn.isHidden()
    assert s._controls_strip.isHidden() is strip_hidden


def test_resolving_sets_status_text(surf):
    s, ctrl = surf
    ctrl.state_changed.emit(VideoState.RESOLVING)
    assert s._status_lbl.text() == "RESOLVING…"


def test_paused_shows_overlay_and_playing_hides_it(surf):
    s, ctrl = surf
    ctrl.state_changed.emit(VideoState.PAUSED)
    assert not s._pause_overlay.isHidden()
    ctrl.state_changed.emit(VideoState.PLAYING)
    assert s._pause_overlay.isHidden()


def test_idle_stops_spinner_and_hides_overlay(surf):
    s, ctrl = surf
    ctrl.state_changed.emit(VideoState.LOADING)
    ctrl.state_changed.emit(VideoState.PAUSED)
    ctrl.state_changed.emit(VideoState.IDLE)
    assert not s._spinner._timer.isActive()
    assert s._pause_overlay.isHidden()
    assert s._controls_strip.isHidden()


def test_status_text_uppercased_into_both_labels(surf):
    s, ctrl = surf
    ctrl.status_text_changed.emit("fetching stream")
    assert s._status_lbl.text() == "FETCHING STREAM"
    assert s._error_lbl.text() == "FETCHING STREAM"


def test_close_button_emits_stop_requested(surf):
    s, _ = surf
    fired = []
    s.stop_requested.connect(lambda: fired.append(1))
    s._close_btn.click()
    assert fired == [1]


def test_show_toast_formats_centres_and_starts_timer(surf):
    s, _ = surf
    s.show_toast("volume up")
    assert s._toast_lbl.text() == "◈  VOLUME UP  ◈"
    assert not s._toast_lbl.isHidden()
    assert s._toast_lbl.width() >= 140 and s._toast_lbl.height() >= 34
    assert s._toast_lbl.x() == (s.width() - s._toast_lbl.width()) // 2
    assert s._toast_timer.isActive()
    assert s._toast_timer.interval() == SURFACE_TOAST_DURATION_MS
    s._hide_toast()
    assert s._toast_lbl.isHidden()


def test_show_toast_ignores_empty_text(surf):
    s, _ = surf
    s.show_toast("")
    assert s._toast_lbl.isHidden()
    assert not s._toast_timer.isActive()


def test_toast_requested_signal_shows_toast(surf):
    s, ctrl = surf
    ctrl.toast_requested.emit("muted")
    assert "MUTED" in s._toast_lbl.text()


def test_show_toast_off_gui_thread_is_marshalled(surf, monkeypatch):
    import core.thread_safety as ts
    s, _ = surf
    calls = []
    monkeypatch.setattr(ts, "is_gui_thread", lambda: False)
    monkeypatch.setattr(ts, "run_on_gui_thread", lambda fn, *a: calls.append((fn, a)))
    s.show_toast("hi")
    assert calls == [(s.show_toast, ("hi",))]
    assert s._toast_lbl.text() == ""


def test_apply_theme_updates_colours_and_strip(surf, monkeypatch):
    s, _ = surf
    strip_calls = []
    monkeypatch.setattr(s._controls_strip, "apply_theme", lambda *a: strip_calls.append(a))
    s.apply_theme("#FF0000", "#880000", "#010101", "#777777")
    assert s._spinner._color == QColor("#FF0000")
    assert "#FF0000" in s._title_lbl.styleSheet()
    assert "#880000" in s.styleSheet() and "#010101" in s.styleSheet()
    assert "#777777" in s._close_btn.styleSheet()
    assert strip_calls == [("#FF0000", "#880000", "#010101", "#777777")]


def test_resize_positions_badge_and_overlay(surf):
    s, _ = surf
    s.resize(500, 320)
    s.show()
    _app.processEvents()
    assert s._mute_badge.geometry().getRect() == (500 - 80 - 8, 36, 80, 22)
    assert s._pause_overlay.geometry().getRect() == ((500 - 160) // 2, (320 - 36) // 2, 160, 36)
    s.hide()


def test_hide_mute_badge(surf):
    s, _ = surf
    s._mute_badge.show()
    s._hide_mute_badge()
    assert s._mute_badge.isHidden()


def test_tech_font_fallback(monkeypatch):
    # Force the `from ui import tech_font` path to fail.
    monkeypatch.setitem(sys.modules, "ui", None)
    f = HudVideoSurface._tech_font(9, bold=True)
    assert f.family() == "Courier New" and f.pointSize() == 9 and f.bold()


def test_spinner_tick_wraps_and_paints():
    sp = _SpinnerWidget()
    assert sp.size() == QSize(56, 56)
    assert sp._timer.interval() == SURFACE_SPINNER_INTERVAL_MS
    for _ in range(61):
        sp._tick()
    assert sp._angle == pytest.approx(6.0)  # 61 * 6 = 366 -> wraps to 6
    sp.set_color(QColor("#00FF00"))
    img = QImage(56, 56, QImage.Format.Format_ARGB32)
    img.fill(0)
    sp.render(img)
    # the arc is drawn in the chosen colour somewhere on the widget
    greens = sum(1 for x in range(56) for y in range(56)
                 if QColor(img.pixel(x, y)).green() > 200 and QColor(img.pixel(x, y)).red() < 60)
    assert greens > 0
    sp.start()
    assert sp._timer.isActive()
    sp.stop()
    assert not sp._timer.isActive()
    sp.deleteLater()
