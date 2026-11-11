"""Behavioural tests for core.scheduler.parser.parse_schedule."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from core.scheduler.parser import parse_schedule

NOW = datetime(2026, 3, 10, 9, 30, 15, 123)


@pytest.mark.parametrize("text", ["", "   ", None])
def test_empty_input_returns_none(text):
    assert parse_schedule(text, NOW) is None


def test_unrecognised_phrase_returns_none():
    assert parse_schedule("remind me to buy milk", NOW) is None


@pytest.mark.parametrize(
    "text, delta",
    [
        ("remind me to stretch in 1 minute", timedelta(minutes=1)),
        ("ping in 45 minutes", timedelta(minutes=45)),
        ("remind me in 2 hours to call mom", timedelta(hours=2)),
        ("IN 1 HOUR remind me", timedelta(hours=1)),
    ],
)
def test_relative_offsets(text, delta):
    result = parse_schedule(text, NOW)
    assert datetime.fromisoformat(result["trigger_time"]) == NOW + delta
    assert result["recurrence"] == "once"


def test_relative_wins_over_clock_time():
    result = parse_schedule("in 5 minutes at 7 pm", NOW)
    assert datetime.fromisoformat(result["trigger_time"]) == NOW + timedelta(minutes=5)


def test_clock_time_later_today_is_same_day_and_zeroes_seconds():
    result = parse_schedule("remind me at 10:15 to check oven", NOW)
    assert datetime.fromisoformat(result["trigger_time"]) == datetime(2026, 3, 10, 10, 15)
    assert result["payload"]["message"] == "check oven"


def test_clock_time_already_past_rolls_to_tomorrow():
    result = parse_schedule("remind me at 8 am to stand", NOW)
    assert datetime.fromisoformat(result["trigger_time"]) == datetime(2026, 3, 11, 8, 0)


def test_exact_now_rolls_to_tomorrow():
    now = datetime(2026, 3, 10, 9, 30)
    result = parse_schedule("at 9:30 do it", now)
    assert datetime.fromisoformat(result["trigger_time"]) == datetime(2026, 3, 11, 9, 30)


@pytest.mark.parametrize(
    "text, hour",
    [("at 12 am x", 0), ("at 12 pm x", 12), ("at 1 pm x", 13), ("at 11 PM x", 23), ("at 17 x", 17)],
)
def test_meridiem_conversion(text, hour):
    result = parse_schedule(text, datetime(2026, 1, 1, 0, 0, 0, 1))
    assert datetime.fromisoformat(result["trigger_time"]).hour == hour


@pytest.mark.parametrize("text", ["at 13 pm x", "at 0 am x", "at 24 x", "at 10:75 x"])
def test_invalid_clock_values_rejected(text):
    assert parse_schedule(text, NOW) is None


def test_every_day_sets_daily_recurrence_and_strips_prefix():
    result = parse_schedule("remind me every day at 8:00 am to take medicine", NOW)
    assert result["recurrence"] == "daily"
    assert result["payload"]["message"] == "take medicine"


def test_message_falls_back_to_source_when_nothing_left():
    result = parse_schedule("remind me at 11 am", NOW)
    assert result["payload"]["message"] == "remind me at 11 am"


def test_tell_me_prefix_is_stripped():
    result = parse_schedule("please tell me to drink water in 3 minutes", NOW)
    assert result["payload"]["message"] == "drink water in 3 minutes"
