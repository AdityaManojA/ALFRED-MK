"""
tests/plugins/test_calendar_sync.py — Tests for plugins/calendar_sync.py (local calendar plugin).

The JSON store is redirected to tmp_path; the user's ~/.alfred is never touched.
"""
from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import MagicMock

import pytest

import plugins.calendar_sync as cal
from core import plugin_loader


@pytest.fixture
def store(tmp_path, monkeypatch):
    path = tmp_path / "alfred" / "calendar.json"
    monkeypatch.setattr(cal, "_STORE", path)
    return path


def _today():
    return datetime.now().strftime("%Y-%m-%d")


def test_plugin_metadata_validates():
    rec = plugin_loader._validate(cal, "calendar_sync.py")
    assert rec.valid, rec.error
    assert rec.name == "calendar_sync"
    assert rec.behavior == "BLOCKING"
    assert rec.scheduling == "WHEN_IDLE"
    assert rec.parameters["required"] == ["action"]


@pytest.mark.xfail(
    reason="PLUGIN_SETTINGS uses a 'settings' list with 'id' keys, but core.plugin_loader "
           "only accepts schemas with a 'fields' list, so these settings are silently dropped.",
    strict=True,
)
def test_plugin_settings_are_recognised_by_loader():
    assert plugin_loader._validate(cal, "calendar_sync.py").settings is not None


def test_load_events_missing_or_corrupt(store):
    assert cal._load_events() == []
    store.parent.mkdir(parents=True)
    store.write_text("{broken", encoding="utf-8")
    assert cal._load_events() == []


def test_save_and_load_roundtrip(store):
    cal._save_events([{"title": "x"}])
    assert store.exists()
    assert cal._load_events() == [{"title": "x"}]


def test_add_requires_title(store):
    assert "require an event title" in cal.run({"action": "add"})
    assert not store.exists()


def test_add_persists_sorted_event_with_defaults(store):
    player = MagicMock()
    cal.run({"action": "add", "title": "Late", "date": "2030-01-02", "time": "15:00"})
    out = cal.run({"action": "ADD ", "title": " Early ", "date": "2030-01-02",
                   "duration_minutes": "45"}, player=player)
    assert out == "Sir, I have scheduled 'Early' for 2030-01-02 at 10:00."
    events = json.loads(store.read_text(encoding="utf-8"))
    assert [e["title"] for e in events] == ["Early", "Late"]
    assert events[0]["time"] == "10:00"
    assert events[0]["duration"] == 45
    assert events[0]["id"].startswith("evt_")
    player.write_log.assert_called_once()
    assert "(45 mins)" in player.write_log.call_args.args[0]


def test_next_returns_soonest_future_event(store):
    cal._save_events([
        {"title": "Past", "date": "2000-01-01", "time": "09:00"},
        {"title": "Later", "date": "2099-06-02", "time": "09:00"},
        {"title": "Sooner", "date": "2099-06-01", "time": "13:30"},
        {"title": "Broken", "date": "nope", "time": "x"},
    ])
    out = cal.run({"action": "next"})
    assert out == "Your next appointment is 'Sooner' on Monday, June 01 at 01:30 PM."


def test_next_with_no_upcoming(store):
    cal._save_events([{"title": "Past", "date": "2000-01-01", "time": "09:00"}])
    assert "no upcoming meetings" in cal.run({"action": "next"})


def test_list_open_day_wording(store):
    assert cal.run({"action": "list"}).endswith("completely open today. No meetings scheduled.")
    assert "open for 2031-05-05" in cal.run({"action": "list", "date": "2031-05-05"})


def test_list_agenda_for_date(store):
    cal._save_events([
        {"title": "Standup", "date": "2031-05-05", "time": "09:00", "duration": 15},
        {"title": "Review", "date": "2031-05-05", "time": "14:00"},
        {"title": "Other day", "date": "2031-05-06", "time": "09:00"},
    ])
    player = MagicMock()
    out = cal.run({"action": "list", "date": "2031-05-05"}, player=player)
    assert out.startswith("Sir, you have 2 events scheduled:")
    assert "• At 09:00: Standup (15 mins)" in out
    assert "• At 14:00: Review (30 mins)" in out
    assert "Other day" not in out
    assert player.write_log.call_count == 3


def test_list_singular_event_defaults_to_today(store):
    cal._save_events([{"title": "Solo", "date": _today(), "time": "08:00"}])
    assert cal.run({}).startswith("Sir, you have 1 event scheduled:")
