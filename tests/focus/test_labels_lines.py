"""Behavioural tests for core.sentry.focus.labels and core.sentry.focus.lines."""
from __future__ import annotations

import pytest

from core.sentry.focus import labels, lines
from core.sentry.focus.labels import resolve_distraction_label
from core.sentry.focus.lines import (
    DRILL_SERGEANT,
    FIRST_CALLOUT,
    NAMELESS,
    TIER1,
    TIER2,
    TIER3,
    get_drift_line,
)
from core.sentry.focus.reader import SurfaceIdentity


# ── labels ────────────────────────────────────────────────────────────────────

def test_naming_disabled_returns_empty(monkeypatch):
    monkeypatch.setattr(labels, "NAME_DISTRACTIONS", False)
    assert resolve_distraction_label(SurfaceIdentity(app_id="game.exe")) == ""


@pytest.mark.parametrize("flags", [{"is_home_base": True}, {"is_self": True}])
def test_home_base_never_labelled(flags):
    assert resolve_distraction_label(SurfaceIdentity(app_id="alfred.exe", spoken_label="YouTube", **flags)) == ""


@pytest.mark.parametrize(
    "spoken, expected",
    [("youtube", "YouTube"), ("www.reddit.com", "Reddit"), ("Spotify", "Spotify"), ("x", "X")],
)
def test_spoken_label_normalised_via_host_map(spoken, expected):
    assert resolve_distraction_label(SurfaceIdentity(spoken_label=spoken, app_id="chrome.exe")) == expected


def test_unknown_spoken_label_falls_through_to_app():
    assert resolve_distraction_label(SurfaceIdentity(spoken_label="Unknown", app_id="Steam.EXE")) == "Steam"


def test_browser_title_host_lookup():
    s = SurfaceIdentity(app_id="chrome.exe", is_browser=True, raw_title="Funny cats - YouTube - Google Chrome")
    assert resolve_distraction_label(s) == "YouTube"


def test_browser_title_bare_domain():
    s = SurfaceIdentity(app_id="chrome.exe", is_browser=True, raw_title="Docs | Example.DEV")
    assert resolve_distraction_label(s) == "example.dev"


def test_browser_title_letter_x_does_not_imply_x_dot_com():
    # Regression: "x" used to match any title containing the letter x (e.g. "Firefox").
    s = SurfaceIdentity(app_id="firefox.exe", is_browser=True, raw_title="Python docs - Mozilla Firefox")
    assert resolve_distraction_label(s) == "Firefox"


def test_browser_title_standalone_x_still_matches():
    s = SurfaceIdentity(app_id="chrome.exe", is_browser=True, raw_title="Home / X")
    assert resolve_distraction_label(s) == "X"


def test_non_browser_title_ignored_uses_app_id():
    s = SurfaceIdentity(app_id="slack.exe", is_browser=False, raw_title="youtube.com")
    assert resolve_distraction_label(s) == "Slack"


def test_no_information_returns_empty():
    assert resolve_distraction_label(SurfaceIdentity(app_id="unknown")) == ""
    assert resolve_distraction_label(SurfaceIdentity()) == ""


# ── lines ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def first_choice(monkeypatch):
    monkeypatch.setattr(lines.random, "choice", lambda seq: seq[0])


@pytest.mark.parametrize("pool", [FIRST_CALLOUT, TIER1, TIER2, TIER3, DRILL_SERGEANT, NAMELESS])
def test_pools_have_four_lines(pool):
    assert len(pool) == 4


@pytest.mark.parametrize("pool", [FIRST_CALLOUT, TIER1, TIER2, TIER3, DRILL_SERGEANT])
def test_named_pools_contain_label_placeholder(pool):
    assert all("{label}" in line for line in pool)


def test_blank_label_uses_nameless_pool():
    for _ in range(10):
        assert get_drift_line(3, label="   ", intent="write", is_first=True, drill_sergeant=True) in NAMELESS


def test_drill_sergeant_takes_precedence(first_choice):
    assert get_drift_line(1, label="Reddit", intent="x", is_first=True, drill_sergeant=True) == DRILL_SERGEANT[0].format(label="Reddit")


def test_first_callout_includes_intent(first_choice):
    line = get_drift_line(1, label=" YouTube ", intent=" write thesis ", is_first=True)
    assert line == FIRST_CALLOUT[0].format(label="YouTube", intent="write thesis")


def test_first_callout_requires_intent(first_choice):
    assert get_drift_line(1, label="YouTube", intent="", is_first=True) == TIER1[0].format(label="YouTube")


@pytest.mark.parametrize("tier, pool", [(0, TIER1), (1, TIER1), (2, TIER2), (3, TIER3), (9, TIER3)])
def test_tier_selection(first_choice, tier, pool):
    assert get_drift_line(tier, label="Twitch") == pool[0].format(label="Twitch")
