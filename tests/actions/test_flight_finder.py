"""Behavioural tests for actions.flight_finder (browser, Gemini and editor are mocked)."""
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import actions.flight_finder as ff
from actions.flight_finder import flight_finder
from core import gemini


# ── _parse_date ──────────────────────────────────────────────────────────────

def test_parse_date_iso_passthrough():
    assert ff._parse_date(" 2030-05-17 ") == "2030-05-17"


@pytest.mark.parametrize("raw", ["17/05/2030", "17.05.2030", "17-05-2030"])
def test_parse_date_day_first_formats(raw):
    assert ff._parse_date(raw) == "2030-05-17"


def test_parse_date_month_first_when_day_first_invalid():
    assert ff._parse_date("05/31/2030") == "2030-05-31"


def test_parse_date_relative_words():
    today = datetime.now()
    assert ff._parse_date("Today") == today.strftime("%Y-%m-%d")
    assert ff._parse_date("tomorrow morning") == (today + timedelta(days=1)).strftime("%Y-%m-%d")


def test_parse_date_uses_gemini_result():
    with patch.object(gemini, "text", return_value="2031-01-02") as text:
        assert ff._parse_date("le deux janvier") == "2031-01-02"
    text.assert_called_once()


def test_parse_date_month_name_fallback_when_gemini_fails():
    with patch.object(gemini, "text", side_effect=RuntimeError("offline")):
        out = ff._parse_date("december 5")
    year, month, day = out.split("-")
    assert (month, day) == ("12", "05")
    assert int(year) in (datetime.now().year, datetime.now().year + 1)


def test_parse_date_last_resort_is_today():
    with patch.object(gemini, "text", return_value="no idea"):
        assert ff._parse_date("someday") == datetime.now().strftime("%Y-%m-%d")


# ── URL / formatting ─────────────────────────────────────────────────────────

def test_build_url_one_way_and_cabin_code():
    url = ff._build_google_flights_url("IST", "LHR", "2030-01-01", None, 2, "Business")
    assert url.startswith("https://www.google.com/travel/flights?q=Flights+from+IST+to+LHR+on+2030-01-01&")
    assert "&cabin=3" in url and "&adults=2" in url
    assert "returning" not in url


def test_build_url_round_trip_and_unknown_cabin():
    url = ff._build_google_flights_url("A", "B", "d1", "d2", 1, "luxury")
    assert "returning+d2" in url
    assert "&cabin=1" in url


def test_format_spoken_empty():
    out = ff._format_spoken([], "A", "B", "d")
    assert out.startswith("I couldn't find any flights from A to B on d")


def test_format_spoken_lists_options_and_picks_cheapest():
    flights = [
        {"airline": "Pricey", "departure": "08:00", "arrival": "10:00",
         "duration": "2h", "stops": 0, "price": "$1,200", "currency": "USD"},
        {"airline": "Budget", "departure": "09:00", "arrival": "13:00",
         "stops": 2, "price": "$300", "currency": "USD"},
        {"airline": "NoPrice", "stops": 1},
    ]
    out = ff._format_spoken(flights, "A", "B", "d")
    assert "Option 1: Pricey, departing 08:00, arriving 10:00, 2h, non-stop, $1,200 USD." in out
    assert "Option 2: Budget, departing 09:00, arriving 13:00, 2 stops, $300 USD." in out
    assert "Option 3: NoPrice, departing --:--, arriving --:--, 1 stop, price unavailable." in out
    assert out.endswith("The cheapest option is Budget at $300 USD.")


def test_format_text_report_includes_return_and_flights():
    report = ff._format_text_report(
        [{"airline": "X", "stops": 0, "price": "10", "currency": "EUR"}],
        "A", "B", "d1", "d2", "http://u",
    )
    assert "Route     : A → B" in report
    assert "Return    : d2" in report
    assert "Stops     : Non-stop" in report
    assert "Price     : 10 EUR" in report
    assert "Duration  : N/A" in report


def test_format_text_report_no_flights():
    assert "No flights found." in ff._format_text_report([], "A", "B", "d", None, "u")


def test_parse_flights_with_gemini_strips_fences():
    resp = SimpleNamespace(text='```json\n[{"airline": "X"}]\n```')
    with patch.object(gemini, "call", return_value=resp):
        assert ff._parse_flights_with_gemini("raw", "A", "B", "d") == [{"airline": "X"}]


def test_parse_flights_with_gemini_non_list_and_errors():
    with patch.object(gemini, "call", return_value=SimpleNamespace(text='{"a": 1}')):
        assert ff._parse_flights_with_gemini("raw", "A", "B", "d") == []
    with patch.object(gemini, "call", return_value=None):  # .text on None -> handled
        assert ff._parse_flights_with_gemini("raw", "A", "B", "d") == []


def test_save_to_desktop_writes_file_and_opens_editor(tmp_path, monkeypatch):
    monkeypatch.setattr(ff.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(ff, "is_windows", lambda: False)
    monkeypatch.setattr(ff, "is_mac", lambda: False)
    with patch.object(ff.subprocess, "Popen") as popen:
        path = ff._save_to_desktop("report", "New York", "LA")
    files = list((tmp_path / "Desktop").iterdir())
    assert len(files) == 1 and str(files[0]) == path
    saved = files[0]
    assert saved.read_text(encoding="utf-8") == "report"
    assert saved.name.startswith("flights_New_York_LA_")
    assert popen.call_args.args[0][0] == "xdg-open"


# ── flight_finder handler ────────────────────────────────────────────────────

def test_handler_validations():
    assert flight_finder({"origin": "A"}) == "Please provide both origin and destination, sir."
    assert flight_finder({"origin": "A", "destination": "B"}) == "Please provide a departure date, sir."


def test_handler_empty_page():
    with patch.object(ff, "_search_flights_browser", return_value=("", "u")):
        out = flight_finder({"origin": "A", "destination": "B", "date": "2030-01-01"})
    assert out.startswith("Could not retrieve flight data")


def test_handler_happy_path_normalises_inputs_and_saves():
    flights = [{"airline": "X", "price": "100", "currency": "USD", "stops": 0}]
    speak = MagicMock()
    with patch.object(ff, "_search_flights_browser", return_value=("page", "u")) as search, \
         patch.object(ff, "_parse_flights_with_gemini", return_value=flights), \
         patch.object(ff, "_save_to_desktop", return_value="/tmp/f.txt") as save:
        out = flight_finder(
            {"origin": "A", "destination": "B", "date": "2030-01-01",
             "return_date": "2030-01-09", "passengers": 0, "cabin": "spaceship", "save": True},
            speak=speak,
        )
    search.assert_called_once_with("A", "B", "2030-01-01", "2030-01-09", 1, "economy")
    save.assert_called_once()
    assert out.endswith("Results saved to Desktop: /tmp/f.txt")
    assert speak.call_count == 3


def test_handler_wraps_exceptions():
    with patch.object(ff, "_search_flights_browser", side_effect=RuntimeError("browser died")):
        out = flight_finder({"origin": "A", "destination": "B", "date": "2030-01-01"})
    assert out == "Flight search failed, sir: browser died"
