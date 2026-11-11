"""Behavioural tests for core.scheduler.engine.SchedulerEngine."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from core.scheduler import engine as engine_mod
from core.scheduler.automation import AutomationResult
from core.scheduler.engine import IDLE_TICK_S, NEAR_TICK_S, SchedulerEngine
from core.scheduler.ledger import Ledger

T0 = datetime(2026, 5, 1, 12, 0, 0)


@pytest.fixture
def env(tmp_path):
    spoken, events = [], []
    eng = SchedulerEngine(speak=spoken.append, notify=events.append, ledger=Ledger(tmp_path / "s.json"))
    return eng, spoken, events


def _at(offset_s: float) -> str:
    return (T0 + timedelta(seconds=offset_s)).isoformat()


def test_add_normalises_recurrence_and_persists(env):
    eng, _, events = env
    task = eng.add("n", "reminder", {"message": "m"}, _at(60), recurrence="weekly")
    assert task["recurrence"] == "once" and task["status"] == "pending"
    assert eng.list_tasks() == [task]
    assert events == [task]
    assert eng.add("d", "reminder", {}, _at(60), recurrence="daily")["recurrence"] == "daily"


def test_cancel_acknowledge_delete_unknown_ids(env):
    eng, _, events = env
    assert eng.cancel("nope") is False
    assert eng.acknowledge("nope") is False
    assert eng.delete("nope") is False
    assert events == []


def test_delete_removes_and_notifies(env):
    eng, _, events = env
    task = eng.add("n", "reminder", {}, _at(60))
    assert eng.delete(task["id"]) is True
    assert eng.list_tasks() == []
    assert events[-1] == {"event": "deleted", "id": task["id"]}


def test_future_reminder_not_fired(env):
    eng, spoken, _ = env
    eng.add("n", "reminder", {"message": "later"}, _at(30))
    eng.tick(T0)
    assert spoken == [] and eng.list_tasks()[0]["status"] == "pending"


def test_due_speak_task_fires_once(env):
    eng, spoken, _ = env
    eng.add("n", "speak", {"message": "hydrate"}, _at(0))
    eng.tick(T0)
    eng.tick(T0 + timedelta(seconds=5))
    assert spoken == ["Reminder, sir: hydrate"]
    assert eng.list_tasks()[0]["status"] == "done"


def test_daily_task_reschedules_and_resets_flags(env):
    eng, spoken, _ = env
    task = eng.add("n", "reminder", {"message": "pill"}, _at(-5), recurrence="daily")
    eng.acknowledge(task["id"])
    eng.tick(T0)
    saved = eng.list_tasks()[0]
    assert saved["status"] == "pending" and saved["acknowledged"] is False
    assert datetime.fromisoformat(saved["trigger_time"]) == T0 + timedelta(days=1, seconds=-5)
    assert spoken == ["Reminder, sir: pill"]


def test_invalid_trigger_time_marks_failed(env):
    eng, spoken, events = env
    eng.add("n", "reminder", {}, "not-a-date")
    eng.tick(T0)
    saved = eng.list_tasks()[0]
    assert saved["status"] == "failed" and saved["error"] == "Invalid trigger time."
    assert spoken == [] and events[-1]["status"] == "failed"


def test_unknown_action_fails(env):
    eng, _, _ = env
    eng.add("n", "teleport", {}, _at(0))
    eng.tick(T0)
    saved = eng.list_tasks()[0]
    assert saved["status"] == "failed" and saved["error"] == "Unknown task action."


def test_macro_warning_window_and_execution(env, monkeypatch):
    eng, spoken, _ = env
    calls = []
    monkeypatch.setattr(engine_mod, "run_macro", lambda p: calls.append(p) or AutomationResult(True, "ok"))
    eng.add("m", "macro", {"target_app": "x", "paste_text": "y"}, _at(20))
    eng.tick(T0)  # 20s out: no warning yet
    assert spoken == []
    eng.tick(T0 + timedelta(seconds=12))  # 8s out: warn once
    eng.tick(T0 + timedelta(seconds=15))
    assert len(spoken) == 1 and "10 seconds" in spoken[0]
    assert calls == []
    eng.tick(T0 + timedelta(seconds=20))
    assert calls == [{"target_app": "x", "paste_text": "y"}]
    assert eng.list_tasks()[0]["status"] == "done"


def test_failed_macro_records_error_and_speaks(env, monkeypatch):
    eng, spoken, _ = env
    monkeypatch.setattr(engine_mod, "run_macro", lambda p: AutomationResult(False, "no focus"))
    eng.add("m", "macro", {}, _at(0), recurrence="daily")
    eng.tick(T0)
    saved = eng.list_tasks()[0]
    assert saved["status"] == "failed" and saved["error"] == "no focus"
    assert spoken[-1] == "Scheduled automation aborted: no focus"


def test_paused_engine_does_nothing(env):
    eng, spoken, _ = env
    eng.add("n", "reminder", {"message": "x"}, _at(-1))
    eng.set_paused(True)
    assert eng.paused is True
    eng.tick(T0)
    assert spoken == [] and eng.list_tasks()[0]["status"] == "pending"
    eng.set_paused(0)
    eng.tick(T0)
    assert spoken


def test_cancelled_task_is_skipped(env):
    eng, spoken, _ = env
    task = eng.add("n", "reminder", {}, _at(-1))
    assert eng.cancel(task["id"]) is True
    eng.tick(T0)
    assert spoken == [] and eng.list_tasks()[0]["status"] == "cancelled"


def test_trigger_now_resets_pending_and_warned(env):
    eng, _, _ = env
    task = eng.add("n", "reminder", {}, _at(3600))
    eng.cancel(task["id"])
    assert eng.trigger_now(task["id"]) is True
    saved = eng.list_tasks()[0]
    assert saved["status"] == "pending" and saved["warned"] is True
    assert abs((datetime.fromisoformat(saved["trigger_time"]) - datetime.now()).total_seconds()) < 5


def test_delay_fast_when_task_within_a_minute(env):
    eng, _, _ = env
    assert eng._delay() == IDLE_TICK_S
    eng.add("far", "reminder", {}, (datetime.now() + timedelta(hours=1)).isoformat())
    eng.add("bad", "reminder", {}, "garbage")
    assert eng._delay() == IDLE_TICK_S
    eng.add("near", "reminder", {}, (datetime.now() + timedelta(seconds=30)).isoformat())
    assert eng._delay() == NEAR_TICK_S


def test_start_is_idempotent_and_stop_ends_loop(env, monkeypatch):
    eng, _, _ = env
    monkeypatch.setattr(eng, "_delay", lambda: 0.01)
    eng.start()
    first = eng._thread
    eng.start()
    assert eng._thread is first and first.is_alive()
    eng.stop()
    first.join(timeout=2)
    assert not first.is_alive()
