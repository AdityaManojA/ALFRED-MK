"""
tests/ui/test_plugin_settings_overlay.py — Behavioural tests for the generic
plugin settings form overlay (ui/overlays/plugin_settings_overlay.py).
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
import threading
from unittest.mock import patch

import pytest
from PyQt6.QtWidgets import QApplication, QComboBox, QLabel, QLineEdit, QPushButton

app = QApplication.instance() or QApplication(sys.argv)

from ui.overlays import plugin_settings_overlay
from ui.overlays.plugin_settings_overlay import PluginSettingsOverlay


def _section(**overrides):
    sec = {
        "namespace": "weather",
        "title": "Weather Plugin",
        "fields": [
            {"key": "city", "type": "text", "label": "City", "placeholder": "e.g. Gotham"},
            {"key": "api_key", "type": "password", "label": "API Key"},
            {"key": "units", "type": "choice", "options": ["metric", "imperial"], "default": "metric"},
            {"key": "enabled", "type": "toggle", "default": False},
        ],
        "values": {"city": "Gotham", "units": "imperial", "enabled": True},
    }
    sec.update(overrides)
    return sec


@pytest.fixture
def saved_configs():
    """Capture save_plugin_config calls instead of touching the real config file."""
    calls = []
    with patch("memory.config_manager.save_plugin_config",
               side_effect=lambda ns, vals: calls.append((ns, dict(vals)))):
        yield calls


def _buttons(widget, text_fragment):
    return [b for b in widget.findChildren(QPushButton) if text_fragment in b.text()]


def test_empty_sections_shows_placeholder_and_no_save_button():
    ov = PluginSettingsOverlay([])
    texts = [lbl.text() for lbl in ov.findChildren(QLabel)]
    assert any("No configurable plugins are installed" in t for t in texts)
    assert _buttons(ov, "SAVE CHANGES") == []
    assert len(_buttons(ov, "SETUP API")) == 1
    assert ov._widgets == {}


def test_none_sections_treated_as_empty():
    ov = PluginSettingsOverlay(None)
    assert ov._sections == []
    assert _buttons(ov, "SAVE CHANGES") == []


def test_builds_widget_per_field_with_correct_types_and_values():
    ov = PluginSettingsOverlay([_section()])
    city = ov._widgets[("weather", "city")]
    api_key = ov._widgets[("weather", "api_key")]
    units = ov._widgets[("weather", "units")]
    enabled = ov._widgets[("weather", "enabled")]

    assert isinstance(city, QLineEdit) and city.text() == "Gotham"
    assert city.placeholderText() == "e.g. Gotham"
    assert city.echoMode() == QLineEdit.EchoMode.Normal
    assert isinstance(api_key, QLineEdit)
    assert api_key.echoMode() == QLineEdit.EchoMode.Password
    assert api_key.text() == ""  # no stored value and no default
    assert isinstance(units, QComboBox) and units.currentText() == "imperial"
    assert isinstance(enabled, QPushButton) and enabled.isCheckable() and enabled.isChecked()
    assert enabled.text() == "ACTIVE"
    assert ov._types[("weather", "units")] == "choice"
    assert len(_buttons(ov, "SAVE CHANGES")) == 1


def test_invalid_fields_skipped_and_defaults_used():
    sec = _section(
        fields=[
            "not-a-dict",
            {"label": "missing key"},
            {"key": "port", "default": 8080},          # no type -> text
            {"key": "mode", "type": "CHOICE", "options": ["a", "b"], "default": "b"},
        ],
        values=None,
    )
    ov = PluginSettingsOverlay([sec])
    assert set(ov._widgets) == {("weather", "port"), ("weather", "mode")}
    assert ov._widgets[("weather", "port")].text() == "8080"
    assert ov._types[("weather", "port")] == "text"
    assert ov._types[("weather", "mode")] == "choice"  # type is lower-cased
    assert ov._widgets[("weather", "mode")].currentText() == "b"


def test_namespace_falls_back_to_plugin_then_default():
    ov = PluginSettingsOverlay([
        {"plugin": "alpha", "fields": [{"key": "x"}]},
        {"fields": [{"key": "y"}]},
    ])
    assert ("alpha", "x") in ov._widgets
    assert ("plugin", "y") in ov._widgets
    assert "alpha" in ov._status_labels and "plugin" in ov._status_labels


def test_toggle_restyles_text_on_click():
    ov = PluginSettingsOverlay([_section()])
    tog = ov._widgets[("weather", "enabled")]
    assert tog.text() == "ACTIVE"
    tog.click()
    assert not tog.isChecked()
    assert tog.text() == "OFF"
    tog.click()
    assert tog.text() == "ACTIVE"


def test_gather_returns_typed_values_for_namespace_only():
    ov = PluginSettingsOverlay([
        _section(),
        {"namespace": "other", "fields": [{"key": "z"}], "values": {"z": "zz"}},
    ])
    ov._widgets[("weather", "city")].setText("  Metropolis  ")
    ov._widgets[("weather", "units")].setCurrentText("metric")
    ov._widgets[("weather", "enabled")].setChecked(False)

    out = ov._gather("weather")
    assert out == {"city": "Metropolis", "api_key": "", "units": "metric", "enabled": False}
    assert ov._gather("other") == {"z": "zz"}
    assert ov._gather("missing") == {}


def test_save_all_persists_each_namespace_and_marks_saved(saved_configs):
    ov = PluginSettingsOverlay([
        _section(),
        {"plugin": "beta", "fields": [{"key": "k"}], "values": {"k": "v"}},
    ])
    ov._save_all()
    assert [ns for ns, _ in saved_configs] == ["weather", "beta"]
    assert saved_configs[0][1]["city"] == "Gotham"
    assert saved_configs[1][1] == {"k": "v"}
    assert ov._status_labels["weather"].text() == "Saved ✓"
    assert ov._status_labels["beta"].text() == "Saved ✓"


def test_save_button_click_triggers_save(saved_configs):
    ov = PluginSettingsOverlay([_section()])
    _buttons(ov, "SAVE CHANGES")[0].click()
    assert saved_configs and saved_configs[0][0] == "weather"


def test_setup_api_button_emits_signal():
    ov = PluginSettingsOverlay([])
    got = []
    ov.setup_api_requested.connect(lambda: got.append(True))
    _buttons(ov, "SETUP API")[0].click()
    assert got == [True]


def test_action_button_only_created_for_callable_run():
    ov_none = PluginSettingsOverlay([_section(action={"label": "PING", "run": "not callable"})])
    assert _buttons(ov_none, "PING") == []
    ov = PluginSettingsOverlay([_section(action={"label": "PING", "run": lambda v: True})])
    assert len(_buttons(ov, "PING")) == 1


class _SyncThread:
    """Stand-in for threading.Thread that runs the target inline."""

    def __init__(self, target=None, daemon=None, **_kw):
        self._target = target

    def start(self):
        self._target()


@pytest.mark.parametrize(
    "result, expected_ok, expected_msg",
    [
        ((True, "Connected"), True, "Connected"),
        ((False, "Bad key"), False, "Bad key"),
        (True, True, "True"),
        (0, False, "0"),
    ],
)
def test_run_action_saves_then_reports_result(saved_configs, result, expected_ok, expected_msg):
    seen_values = []

    def run(values):
        seen_values.append(values)
        return result

    ov = PluginSettingsOverlay([_section(action={"run": run})])
    emitted = []
    ov._test_done.connect(lambda ns, ok, msg: emitted.append((ns, ok, msg)))
    with patch.object(plugin_settings_overlay.threading, "Thread", _SyncThread):
        ov._run_action("weather")

    assert saved_configs[0][0] == "weather"  # persisted before testing
    assert seen_values[0]["city"] == "Gotham"
    assert emitted == [("weather", expected_ok, expected_msg)]
    lbl = ov._status_labels["weather"]
    assert lbl.text() == expected_msg
    if expected_ok:
        assert "#ff6b6b" not in lbl.styleSheet()
    else:
        assert "#ff6b6b" in lbl.styleSheet()


def test_run_action_exception_reported_as_failure(saved_configs):
    def run(values):
        raise RuntimeError("boom")

    ov = PluginSettingsOverlay([_section(action={"run": run})])
    with patch.object(plugin_settings_overlay.threading, "Thread", _SyncThread):
        ov._run_action("weather")
    assert ov._status_labels["weather"].text() == "boom"
    assert "#ff6b6b" in ov._status_labels["weather"].styleSheet()


def test_run_action_real_thread_delivers_result(saved_configs):
    done = threading.Event()

    def run(values):
        done.set()
        return (True, "pong")

    ov = PluginSettingsOverlay([_section(action={"run": run})])
    ov._run_action("weather")
    assert done.wait(5)
    # Signal is queued across threads; pump the event loop until delivered.
    for _ in range(200):
        app.processEvents()
        if ov._status_labels["weather"].text() == "pong":
            break
        threading.Event().wait(0.01)
    assert ov._status_labels["weather"].text() == "pong"


def test_run_action_noop_for_unknown_or_missing_action(saved_configs):
    ov = PluginSettingsOverlay([_section()])
    ov._run_action("unknown")
    ov._run_action("weather")  # section has no action
    assert saved_configs == []
    assert ov._status_labels["weather"].text() == ""


def test_on_test_done_ignores_unknown_namespace():
    ov = PluginSettingsOverlay([_section()])
    ov._on_test_done("nope", True, "x")
    assert ov._status_labels["weather"].text() == ""
