"""Behavioural tests for actions.weather_report (webbrowser is mocked)."""
from unittest.mock import MagicMock, patch

import pytest

import actions.weather_report as wr
from actions.weather_report import weather_action


@pytest.mark.parametrize("city", [None, "", "   ", 42])
def test_missing_city(city):
    player = MagicMock()
    with patch.object(wr.webbrowser, "open") as op:
        out = weather_action({"city": city}, player=player)
    assert out == "Sir, the city is missing for the weather report."
    op.assert_not_called()
    player.write_log.assert_called_once_with(f"ALFRED: {out}")


def test_opens_google_search_and_records_memory():
    memory = MagicMock()
    with patch.object(wr.webbrowser, "open", return_value=True) as op:
        out = weather_action({"city": "  New Delhi ", "time": "tomorrow"}, session_memory=memory)
    op.assert_called_once_with("https://www.google.com/search?q=weather+in+New+Delhi+tomorrow")
    assert out == "Showing the weather for New Delhi, tomorrow, sir."
    memory.set_last_search.assert_called_once_with(query="weather in New Delhi tomorrow", response=out)


def test_time_defaults_to_today_when_none():
    with patch.object(wr.webbrowser, "open", return_value=True) as op:
        out = weather_action({"city": "Paris", "time": None})
    assert out.endswith("Paris, today, sir.")
    assert op.call_args.args[0].endswith("weather+in+Paris+today")


def test_browser_failure_is_reported():
    with patch.object(wr.webbrowser, "open", return_value=False):
        out = weather_action({"city": "Oslo"})
    assert out == "Sir, I couldn't open the browser for the weather report: webbrowser.open returned False"


def test_memory_and_player_errors_are_swallowed():
    memory = MagicMock()
    memory.set_last_search.side_effect = RuntimeError("db locked")
    player = MagicMock()
    player.write_log.side_effect = RuntimeError("ui closed")
    with patch.object(wr.webbrowser, "open", return_value=True):
        out = weather_action({"city": "Rome"}, player=player, session_memory=memory)
    assert out == "Showing the weather for Rome, today, sir."
