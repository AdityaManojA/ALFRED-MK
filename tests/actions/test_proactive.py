"""Behavioural tests for actions.proactive.ProactiveEngine."""
from datetime import datetime
from unittest.mock import patch

import pytest

import actions.proactive as pro
from actions.proactive import ProactiveEngine


class _FixedDatetime(datetime):
    fixed = datetime(2030, 3, 4, 9, 30)

    @classmethod
    def now(cls, tz=None):
        return cls.fixed


@pytest.fixture
def fixed_time(monkeypatch):
    monkeypatch.setattr(pro, "datetime", _FixedDatetime)
    monkeypatch.setattr(_FixedDatetime, "fixed", datetime(2030, 3, 4, 9, 30))
    return _FixedDatetime


@pytest.fixture(autouse=True)
def _memory_formatter():
    with patch("memory.memory_manager.format_memory_for_prompt", return_value="MEMORY BLOCK") as f:
        yield f


def test_should_trigger_requires_silence_and_cooldown():
    eng = ProactiveEngine(min_silence_secs=100, check_cooldown=50)
    with patch.object(pro.time, "monotonic", return_value=1000.0):
        assert eng.should_trigger(last_user_speech=950.0) is False  # only 50 s silent
        assert eng.should_trigger(last_user_speech=900.0) is True
        eng.mark_triggered()
    with patch.object(pro.time, "monotonic", return_value=1030.0):
        assert eng.should_trigger(last_user_speech=0.0) is False   # cooldown active
    with patch.object(pro.time, "monotonic", return_value=1050.0):
        assert eng.should_trigger(last_user_speech=0.0) is True


def test_mark_triggered_advances_rotation():
    eng = ProactiveEngine()
    eng.mark_triggered()
    eng.mark_triggered()
    assert eng._rotation == 2


@pytest.mark.parametrize(
    "hour, period",
    [(6, "morning"), (11, "morning"), (12, "afternoon"), (18, "evening"), (23, "late night"), (2, "late night")],
)
def test_build_prompt_period_of_day(fixed_time, hour, period):
    fixed_time.fixed = datetime(2030, 3, 4, hour, 0)
    prompt = ProactiveEngine().build_prompt({})
    assert f"({period})" in prompt
    assert prompt.startswith("[PROACTIVE_CHECK]")


def test_build_prompt_rotates_focus(fixed_time):
    eng = ProactiveEngine()
    focuses = []
    for _ in range(4):
        focuses.append(eng.build_prompt({}))
        eng.mark_triggered()
    assert "active projects" in focuses[0]
    assert "wellbeing" in focuses[1]
    assert "genuinely interesting" in focuses[2]
    assert "active projects" in focuses[3]  # wraps around


def test_build_prompt_includes_memory_monitors_and_recent_turns(fixed_time, _memory_formatter):
    monitors = ["a", "b", "c", "d", "e"]
    turns = [f"turn{i}" for i in range(8)]
    prompt = ProactiveEngine().build_prompt({"k": "v"}, monitors=monitors, recent_turns=turns)
    _memory_formatter.assert_called_once_with({"k": "v"})
    assert "MEMORY BLOCK" in prompt
    assert "tracks these topics: a, b, c, d." in prompt
    assert "turn1" not in prompt and "turn2" in prompt and "turn7" in prompt


def test_build_prompt_placeholder_when_memory_empty(fixed_time, _memory_formatter):
    _memory_formatter.return_value = ""
    prompt = ProactiveEngine().build_prompt({})
    assert "(no stored user data)" in prompt
    assert "tracks these topics" not in prompt
    assert "Recent conversation" not in prompt
