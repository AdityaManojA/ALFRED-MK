"""
tests/ui/test_customize_overlay.py — Behavioural tests for the persona /
voice / chromatics customisation overlay (ui/overlays/customize_overlay.py).

All persistence (memory.config_manager), the Jarvis TTS capability probe, the
secret-store-backed service counter, icon discovery and TTS playback are mocked.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import math
import sys
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QImage, QPixmap
from PyQt6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from ui.overlays import customize_overlay
from ui.overlays.customize_overlay import CustomizeOverlay, HueWheel
from core.ui.themes import ThemeRegistry


class _FakeCap:
    def __init__(self, usable: bool, status: str):
        self._usable = usable
        self._status = status

    def is_usable(self, allow_cpu=False):
        return self._usable

    def display_status(self):
        return self._status


_ICONS = [
    {"path": "/icons/alpha.png", "name": "Alpha", "filename": "alpha.png"},
    {"path": "/icons/beta.png", "name": "Beta", "filename": "beta.png"},
]


@pytest.fixture
def env():
    """Patch every external dependency the overlay touches."""
    state = {"cap": _FakeCap(False, "NO GPU"), "saved_engine": []}
    patches = [
        patch.object(customize_overlay, "get_available_app_icons", return_value=list(_ICONS)),
        patch.object(customize_overlay, "_scaled_icon_pixmap", return_value=QPixmap()),
        patch("memory.config_manager.get_voice_engine", return_value="default"),
        patch("memory.config_manager.save_voice_engine",
              side_effect=lambda e: state["saved_engine"].append(e)),
        patch("memory.config_manager.get_jarvis_allow_cpu", return_value=False),
        patch("core.tts.capability.check_jarvis_capability",
              side_effect=lambda allow_cpu=False, use_cache=False: state["cap"]),
        patch("core.apis.registry.get_configured_backends_count", return_value=(2, 4)),
    ]
    for p in patches:
        p.start()
    try:
        yield state
    finally:
        for p in reversed(patches):
            p.stop()


def _make(**kw):
    kw.setdefault("ui_color", "#00f0ff")
    return CustomizeOverlay(**kw)


# ── HueWheel ─────────────────────────────────────────────────────────────────

def test_huewheel_set_color_roundtrip_pure_hues():
    w = HueWheel("#ff0000")
    assert w.color() == "#ff0000"
    w.set_color("#00ff00")
    assert w.color() == "#00ff00"
    w.set_color("#0000ff")
    assert w.color() == "#0000ff"


def test_huewheel_ignores_invalid_and_achromatic_colors():
    w = HueWheel("#00ff00")
    before = w.color()
    w.set_color("not-a-colour")
    w.set_color("")
    w.set_color(None)
    w.set_color("#808080")  # grey has hue -1 → ignored
    assert w.color() == before


def test_huewheel_hue_from_pos_uses_math_axis():
    w = HueWheel()
    cx, cy = 74.0, 74.0  # QRectF(0,0,148,148).center()
    assert w._hue_from_pos(QPointF(cx + 50, cy)) == pytest.approx(0.0)
    # Screen-up is +90° in math axes → quarter turn.
    assert w._hue_from_pos(QPointF(cx, cy - 50)) == pytest.approx(0.25)
    assert w._hue_from_pos(QPointF(cx - 50, cy)) == pytest.approx(0.5)
    assert w._hue_from_pos(QPointF(cx, cy + 50)) == pytest.approx(0.75)


def test_huewheel_ring_rect_inset():
    w = HueWheel()
    r = w._ring_rect()
    inset = HueWheel._RING / 2 + 3
    assert r.x() == pytest.approx(inset)
    assert r.width() == pytest.approx(148 - 2 * inset)


def _mouse(etype, pos):
    from PyQt6.QtGui import QMouseEvent
    return QMouseEvent(etype, pos, pos, Qt.MouseButton.LeftButton,
                       Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)


def test_huewheel_drag_emits_picked_then_committed():
    from PyQt6.QtCore import QEvent
    w = HueWheel("#ff0000")
    picked, committed = [], []
    w.hue_picked.connect(picked.append)
    w.hue_committed.connect(committed.append)

    w.mousePressEvent(_mouse(QEvent.Type.MouseButtonPress, QPointF(74, 24)))   # up → 0.25 (chartreuse)
    w.mouseMoveEvent(_mouse(QEvent.Type.MouseMove, QPointF(24, 74)))           # left → 0.5 (cyan)
    w.mouseReleaseEvent(_mouse(QEvent.Type.MouseButtonRelease, QPointF(24, 74)))
    # A move after release must not emit.
    w.mouseMoveEvent(_mouse(QEvent.Type.MouseMove, QPointF(124, 74)))
    w.mouseReleaseEvent(_mouse(QEvent.Type.MouseButtonRelease, QPointF(124, 74)))

    assert picked == [QColor.fromHsvF(0.25, 1, 1).name(), "#00ffff"]
    assert committed == ["#00ffff"]


def test_huewheel_renders_into_image():
    w = HueWheel("#ff0000")
    img = QImage(148, 148, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    w.render(img)
    # The hue ring (top, 12 o'clock) is fully saturated; the centre is not painted
    # with a hue (no preview fill is drawn).
    r = w._ring_rect()
    ring_px = img.pixelColor(int(r.center().x()), int(r.top()))
    centre_px = img.pixelColor(int(r.center().x()), int(r.center().y()))
    assert ring_px.hsvSaturation() > 200
    assert centre_px.hsvSaturation() < 50


# ── CustomizeOverlay ─────────────────────────────────────────────────────────

def test_initial_state_from_constructor_args(env):
    ov = _make(assistant_name="Jarvis", user_name="Sir", voice="Puck")
    assert ov._name_input.text() == "Jarvis"
    assert ov._user_input.text() == "Sir"
    assert ov._sel_voice == "Puck"
    assert ov._voice_btns["Puck"].isChecked()
    assert not ov._voice_btns["Charon"].isChecked()
    assert ov._sel_color == "#00f0ff"
    assert ov._hex_input.text() == "#00f0ff"
    # first discovered icon is selected when none passed in
    assert ov._current_icon == "/icons/alpha.png"
    assert set(ov._icon_cards) == {"/icons/alpha.png", "/icons/beta.png"}
    assert "(2/4)" in ov._services_api_btn.text()


def test_unknown_voice_falls_back_to_default(env):
    from memory.config_manager import DEFAULT_VOICE
    ov = _make(voice="NotARealVoice")
    assert ov._sel_voice == DEFAULT_VOICE
    assert ov._voice_btns[DEFAULT_VOICE].isChecked()


def test_invalid_voice_engine_coerced_to_default(env):
    ov = _make(voice_engine="WEIRD")
    assert ov._sel_voice_engine == "default"
    assert ov._engine_btns["default"].isChecked()
    assert "Standard Voice" in ov._lbl_engine_status.text()
    assert "NO GPU" in ov._lbl_engine_status.text()


def test_voice_pick_updates_checked_state(env):
    ov = _make()
    ov._voice_btns["Kore"].click()
    assert ov._sel_voice == "Kore"
    assert [n for n, b in ov._voice_btns.items() if b.isChecked()] == ["Kore"]


def test_engine_pick_jarvis_blocked_when_unusable(env):
    env["cap"] = _FakeCap(False, "CUDA MISSING")
    ov = _make()
    ov._on_engine_pick("jarvis")
    assert ov._sel_voice_engine == "default"
    assert ov._lbl_engine_status.text() == "⚠ JARVIS BLOCKED: CUDA MISSING"
    assert "#ffaa00" in ov._lbl_engine_status.styleSheet()


def test_engine_pick_jarvis_accepted_when_usable(env):
    env["cap"] = _FakeCap(True, "READY")
    ov = _make()
    ov._on_engine_pick("jarvis")
    assert ov._sel_voice_engine == "jarvis"
    assert ov._engine_btns["jarvis"].isChecked()
    assert not ov._engine_btns["default"].isChecked()
    assert ov._lbl_engine_status.text() == "● ACTIVE: Jarvis Voice (READY)"
    assert "#00f0ff" in ov._lbl_engine_status.styleSheet()


def test_hex_edit_valid_updates_color_and_previews(env):
    ov = _make()
    previews = []
    ov.on_preview = previews.append
    ov._on_hex_edited("  #A8FF3E ")
    assert ov._sel_color == "#a8ff3e"
    assert previews == ["#a8ff3e"]
    assert ov._wheel.color() == QColor.fromHsvF(QColor("#a8ff3e").hsvHueF(), 1, 1).name()


@pytest.mark.parametrize("text", ["#12345", "a8ff3e1", "#zzzzzz", ""])
def test_hex_edit_invalid_is_ignored(env, text):
    ov = _make()
    previews = []
    ov.on_preview = previews.append
    ov._on_hex_edited(text)
    assert ov._sel_color == "#00f0ff"
    assert previews == []


def test_theme_button_click_selects_theme_and_highlights(env):
    ov = _make()
    themes = ThemeRegistry.instance().list_themes()
    target = themes[1]
    previews = []
    ov.on_preview = previews.append
    ov._theme_btns[target.display_name].click()
    assert ov._sel_color == target.hex.lower()
    assert previews == [target.hex.lower()]
    active_ss = ov._theme_btns[target.display_name].styleSheet()
    assert f"1.5px solid {target.hex}" in active_ss
    other = themes[0]
    if other.hex.lower() != target.hex.lower():
        assert "1.5px" not in ov._theme_btns[other.display_name].styleSheet()


def test_wheel_pick_updates_hex_without_preview_and_commit_previews(env):
    ov = _make()
    previews = []
    ov.on_preview = previews.append
    ov._on_wheel_pick("#ff0000")
    assert ov._hex_input.text() == "#ff0000"
    assert ov._sel_color == "#ff0000"
    assert previews == []
    ov._on_wheel_commit("#00FF00")
    assert ov._sel_color == "#00ff00"
    assert previews == ["#00ff00"]


def test_icon_pick_highlights_card_and_notifies(env):
    ov = _make()
    changes = []
    ov.on_icon_change = changes.append
    ov._icon_cards["/icons/beta.png"].click()
    assert ov._current_icon == "/icons/beta.png"
    assert changes == ["/icons/beta.png"]
    assert "1.5px solid" in ov._icon_cards["/icons/beta.png"].styleSheet()
    assert "1.5px solid" not in ov._icon_cards["/icons/alpha.png"].styleSheet()


def test_icon_pick_callback_error_is_swallowed(env, capsys):
    ov = _make()
    ov.on_icon_change = MagicMock(side_effect=RuntimeError("tray gone"))
    ov._on_icon_picked("/icons/beta.png")
    assert ov._current_icon == "/icons/beta.png"
    assert "tray gone" in capsys.readouterr().out


def test_save_emits_values_persists_engine_and_applies_icon(env):
    ov = _make(current_icon="/icons/beta.png")
    got = []
    ov.saved.connect(lambda *a: got.append(a))
    icons = []
    ov.on_icon_change = icons.append
    ov._name_input.setText("   ")
    ov._user_input.setText("  Master Wayne ")
    ov._on_voice_pick("Fenrir")
    ov._save()
    assert got == [("Alfred", "Master Wayne", "#00f0ff", "Fenrir")]
    assert env["saved_engine"] == ["default"]
    assert icons == ["/icons/beta.png"]
    assert ov.isHidden()


def test_cancel_reverts_preview_and_icon(env):
    ov = _make(current_icon="/icons/alpha.png")
    previews, icons = [], []
    ov.on_preview = previews.append
    ov.on_icon_change = icons.append
    ov._set_color("#ff0000", preview=False)
    ov._current_icon = "/icons/beta.png"
    ov._cancel()
    assert previews == ["#00f0ff"]
    assert icons == ["/icons/alpha.png"]
    assert env["saved_engine"] == []


def test_cancel_without_changes_does_not_call_callbacks(env):
    ov = _make(current_icon="/icons/alpha.png")
    ov.on_preview = MagicMock()
    ov.on_icon_change = MagicMock()
    ov._cancel()
    ov.on_preview.assert_not_called()
    ov.on_icon_change.assert_not_called()


def test_reset_values_refreshes_controls(env):
    ov = _make(assistant_name="X", voice="Puck")
    ov.reset_values("", "Bruce", "#FF0037", "Aoede", "/icons/beta.png", voice_engine="DEFAULT")
    assert ov._name_input.text() == "Alfred"
    assert ov._user_input.text() == "Bruce"
    assert ov._initial_color == "#ff0037"
    assert ov._hex_input.text() == "#ff0037"
    assert ov._sel_voice == "Aoede"
    assert ov._initial_icon == "/icons/beta.png"
    assert ov._sel_voice_engine == "default"


def test_reset_values_unknown_voice_uses_first_and_engine_from_config(env):
    ov = _make()
    with patch("memory.config_manager.get_voice_engine", return_value="jarvis"):
        ov.reset_values("A", "", "", "Bogus", "")
    assert ov._sel_voice == next(iter(ov._voice_btns))
    assert ov._sel_voice_engine == "jarvis"
    assert ov._initial_color == customize_overlay.DEFAULT_UI_COLOR.strip().lower()


def test_services_button_falls_back_on_error(env):
    ov = _make()
    with patch("core.apis.registry.get_configured_backends_count", side_effect=RuntimeError):
        ov._refresh_services_btn()
    assert ov._services_api_btn.text() == "Spotify, Gmail and Workspace"


def test_api_and_neural_buttons_emit_signals(env):
    ov = _make()
    api, neural = [], []
    ov.setup_api_requested.connect(lambda: api.append(1))
    ov.setup_neural_requested.connect(lambda: neural.append(1))
    ov._services_api_btn.click()
    from PyQt6.QtWidgets import QPushButton
    nb = [b for b in ov.findChildren(QPushButton) if "Model providers" in b.text()][0]
    nb.click()
    assert api == [1] and neural == [1]


def test_preview_voice_uses_custom_handler(env):
    ov = _make()
    handler = MagicMock()
    ov.on_preview_voice = handler
    with patch.object(customize_overlay.threading, "Thread") as thr:
        ov._preview_voice()
    handler.assert_called_once_with("default")
    thr.assert_not_called()


def test_preview_voice_falls_back_to_tts_engine(env):
    ov = _make()
    ov.on_preview_voice = MagicMock(side_effect=RuntimeError("bad"))
    fake_engine = MagicMock()

    class _Sync:
        def __init__(self, target=None, daemon=None, **_):
            self.t = target

        def start(self):
            self.t()

    with patch.object(customize_overlay.threading, "Thread", _Sync), \
         patch("core.tts.get_engine", return_value=fake_engine) as ge:
        ov._preview_voice()
    ge.assert_called_once_with("default")
    fake_engine.speak.assert_called_once()
    assert "nominal" in fake_engine.speak.call_args[0][0]
