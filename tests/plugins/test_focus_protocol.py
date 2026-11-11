"""
tests/plugins/test_focus_protocol.py — Tests for plugins/focus_protocol.py (Pomodoro/focus plugin).

The state file is redirected to tmp_path and time.time is controlled where needed.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import plugins.focus_protocol as focus
from core import plugin_loader


@pytest.fixture
def state_file(tmp_path, monkeypatch):
    path = tmp_path / "alfred" / "focus_state.json"
    monkeypatch.setattr(focus, "_STATE_FILE", path)
    return path


@pytest.fixture
def clock(monkeypatch):
    now = {"t": 1_000_000.0}
    monkeypatch.setattr(focus, "time", SimpleNamespace(time=lambda: now["t"]))
    return now


def _state(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_plugin_metadata_validates():
    rec = plugin_loader._validate(focus, "focus_protocol.py")
    assert rec.valid, rec.error
    assert rec.name == "focus_protocol"
    assert set(rec.parameters["properties"]) == {"action", "duration_minutes", "task"}


def test_read_state_defaults(state_file):
    assert focus._read_state() == {"active": False}
    state_file.parent.mkdir(parents=True)
    state_file.write_text("not json", encoding="utf-8")
    assert focus._read_state() == {"active": False}


def test_start_writes_state(state_file, clock):
    player = MagicMock()
    out = focus.run({"action": "start", "duration_minutes": 50, "task": " Docs "}, player=player)
    st = _state(state_file)
    assert st == {"active": True, "task": "Docs", "started_at": 1_000_000.0,
                  "ends_at": 1_000_000.0 + 3000, "duration_minutes": 50}
    assert out.startswith("Sir, focus protocol initiated for 50 minutes on 'Docs'.")
    assert "Active: 'Docs' (50m" in player.write_log.call_args.args[0]


def test_start_defaults(state_file, clock):
    focus.run({})
    st = _state(state_file)
    assert st["task"] == "General Focus"
    assert st["duration_minutes"] == 25


def test_status_reports_remaining_minutes(state_file, clock):
    focus.run({"action": "start", "duration_minutes": 25, "task": "Code"})
    clock["t"] += 23 * 60 + 30
    assert focus.run({"action": "status"}) == "Sir, you have approximately 1 minute remaining on 'Code'."
    clock["t"] -= 10 * 60
    assert "approximately 11 minutes remaining" in focus.run({"action": "status"})


def test_status_after_expiry_deactivates(state_file, clock):
    focus.run({"action": "start", "duration_minutes": 5})
    clock["t"] += 5 * 60 + 1
    assert "has concluded" in focus.run({"action": "status"})
    assert _state(state_file)["active"] is False
    assert "no active focus session" in focus.run({"action": "status"})


@pytest.mark.parametrize("verb", ["stop", "end", "cancel"])
def test_stop_variants(state_file, clock, verb):
    assert focus.run({"action": verb}) == "Sir, no focus protocol was active."
    focus.run({"action": "start"})
    player = MagicMock()
    out = focus.run({"action": verb}, player=player)
    assert out.startswith("Focus protocol deactivated.")
    assert _state(state_file)["active"] is False
    player.write_log.assert_called_once_with("ALFRED: [Focus Protocol] Session concluded.")


def test_unknown_action(state_file):
    assert focus.run({"action": "dance"}) == "Focus protocol standby."
    assert not state_file.exists()
