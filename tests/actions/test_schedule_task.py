"""Behavioural tests for actions.schedule_task (scheduler engine faked via the registry)."""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import actions.schedule_task as st
from actions.schedule_task import schedule_task
from core.registry import lookup, register, unregister


class FakeEngine:
    def __init__(self):
        self.added = []

    def add(self, name, action_type, payload, trigger_time, recurrence):
        self.added.append(
            {"name": name, "action_type": action_type, "payload": payload,
             "trigger_time": trigger_time, "recurrence": recurrence}
        )
        return {"id": f"task-{len(self.added)}", "trigger_time": trigger_time}


@pytest.fixture
def engine():
    previous = lookup("scheduler_engine")
    eng = FakeEngine()
    register("scheduler_engine", eng)
    yield eng
    if previous is None:
        unregister("scheduler_engine")
    else:
        register("scheduler_engine", previous)


def test_unparseable_schedule(engine):
    out = schedule_task({"text": "sometime soon"})
    assert out.startswith("I need a time such as")
    assert engine.added == []


def test_reminder_in_minutes(engine):
    out = schedule_task({"text": "remind me to stretch in 10 minutes"})
    assert out["scheduled"] is True and out["id"] == "task-1"
    assert out["action_type"] == "reminder"
    added = engine.added[0]
    assert added["name"] == "voice reminder"
    assert added["recurrence"] == "once"
    assert "stretch" in added["payload"]["message"]
    trigger = datetime.fromisoformat(added["trigger_time"])
    delta = (trigger - datetime.now()).total_seconds()
    assert 9 * 60 < delta <= 10 * 60


def test_daily_recurrence(engine):
    schedule_task({"schedule": "every day at 8:00 AM"})
    assert engine.added[0]["recurrence"] == "daily"
    assert datetime.fromisoformat(engine.added[0]["trigger_time"]).hour == 8


def test_macro_requires_target_and_text(engine):
    out = schedule_task({"schedule": "in 5 minutes", "action_type": "macro", "target_app": "Notepad"})
    assert out.startswith("A scheduled macro needs a target application")
    assert engine.added == []


def test_macro_payload(engine):
    out = schedule_task({
        "schedule": "in 5 minutes", "target_tab": "Colab", "paste_text": " run() ",
        "hit_run": False,
    })
    assert out["action_type"] == "macro"
    added = engine.added[0]
    assert added["name"] == "scheduled macro"
    assert added["payload"] == {
        "target_app": "Colab", "target_tab": "Colab", "paste_text": "run()", "hit_run": False,
    }


def test_engine_created_and_registered_when_missing():
    previous = lookup("scheduler_engine")
    unregister("scheduler_engine")
    fake_cls = MagicMock()
    player = SimpleNamespace(request_say=lambda text: None)
    try:
        with patch.object(st, "SchedulerEngine", fake_cls):
            engine = st._engine(player)
        assert engine is fake_cls.return_value
        assert fake_cls.call_args.kwargs["speak"] is player.request_say
        engine.start.assert_called_once()
        assert lookup("scheduler_engine") is engine
    finally:
        unregister("scheduler_engine")
        if previous is not None:
            register("scheduler_engine", previous)
