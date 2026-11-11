"""Behavioural tests for the clipboard and screen-region monitor targets."""
from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest

from core.sentry.monitor.targets.base import TargetStatus
from core.sentry.monitor.targets.clipboard import ClipboardTarget
from core.sentry.monitor.targets.screen_region import ScreenRegionTarget


# ── ClipboardTarget ──────────────────────────────────────────────────────────

@pytest.fixture
def clipboard(monkeypatch):
    box = {"text": ""}
    monkeypatch.setitem(sys.modules, "pyperclip", types.SimpleNamespace(paste=lambda: box["text"]))
    return box


def test_clipboard_describe_and_interval_floor():
    assert ClipboardTarget(pattern=r"\d+").describe() == r"clipboard pattern '\d+'"
    assert ClipboardTarget().describe() == "clipboard pattern 'any'"
    assert ClipboardTarget(interval_s=0.1).interval_s == 1.0


def test_clipboard_match_alerts_once_per_new_text(clipboard):
    t = ClipboardTarget(pattern=r"ERROR-\d+")
    clipboard["text"] = "log line error-123 happened"
    assert t.poll() == TargetStatus.ALERTED
    assert t.should_alert() == (True, "Sir, clipboard match: 'error-123'.")
    assert t.should_alert() == (False, "")
    # Same text again: not new, so no re-alert.
    assert t.poll() == TargetStatus.RUNNING
    assert t.should_alert() == (False, "")


def test_clipboard_non_matching_and_empty(clipboard):
    t = ClipboardTarget(pattern="secret")
    clipboard["text"] = "hello"
    assert t.poll() == TargetStatus.RUNNING
    clipboard["text"] = ""
    assert t.poll() == TargetStatus.RUNNING
    assert t.should_alert() == (False, "")


def test_clipboard_without_pattern_never_alerts(clipboard):
    t = ClipboardTarget()
    clipboard["text"] = "anything"
    assert t.poll() == TargetStatus.RUNNING
    assert t.should_alert() == (False, "")


def test_clipboard_match_message_truncated_to_40(clipboard):
    t = ClipboardTarget(pattern=r"x+")
    clipboard["text"] = "x" * 100
    t.poll()
    _, msg = t.should_alert()
    assert msg == f"Sir, clipboard match: '{'x' * 40}'."


def test_clipboard_paste_failure_is_running(monkeypatch):
    def boom():
        raise RuntimeError("no clipboard")

    monkeypatch.setitem(sys.modules, "pyperclip", types.SimpleNamespace(paste=boom))
    t = ClipboardTarget(pattern=".")
    assert t.poll() == TargetStatus.RUNNING
    assert t.last_poll_t > 0


# ── ScreenRegionTarget ───────────────────────────────────────────────────────

@pytest.fixture
def screen(monkeypatch):
    frames = []
    calls = []

    def capture_screen(monitor):
        calls.append(monitor)
        value = frames.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value

    monkeypatch.setitem(sys.modules, "actions.screen_processor", types.SimpleNamespace(capture_screen=capture_screen))
    return frames, calls


def test_screen_describe():
    assert ScreenRegionTarget(monitor_id=2, goal="the build bar").describe() == "screen monitor 2 for 'the build bar'"
    assert ScreenRegionTarget(name="Desk").describe() == "screen monitor 1 for 'Desk'"


def test_screen_first_frame_is_baseline_then_change_alerts(screen):
    frames, calls = screen
    frames += [SimpleNamespace(img_bytes=b"A" * 10), SimpleNamespace(img_bytes=b"A" * 10), (b"B" * 10, "meta")]
    t = ScreenRegionTarget(monitor_id=3, name="Render")
    assert t.poll() == TargetStatus.RUNNING
    assert t.poll() == TargetStatus.RUNNING
    assert t.poll() == TargetStatus.ALERTED
    assert t.should_alert() == (True, "Sir, visual change detected for Render.")
    assert calls == [3, 3, 3]


def test_screen_only_first_kilobyte_is_compared(screen):
    frames, _ = screen
    head = b"H" * 1024
    frames += [SimpleNamespace(img_bytes=head + b"1"), SimpleNamespace(img_bytes=head + b"2")]
    t = ScreenRegionTarget()
    t.poll()
    assert t.poll() == TargetStatus.RUNNING


def test_screen_empty_or_error_is_running(screen):
    frames, _ = screen
    frames += [SimpleNamespace(img_bytes=b""), (), RuntimeError("capture failed")]
    t = ScreenRegionTarget()
    for _ in range(3):
        assert t.poll() == TargetStatus.RUNNING
    assert t._last_hash is None
