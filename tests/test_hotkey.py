"""Behavioural tests for core.hotkey (push-to-talk chord detection).

The Win32 GetAsyncKeyState hook and the clock are faked; no real keyboard is read.
"""
from __future__ import annotations

import ctypes
from types import SimpleNamespace

import pytest

from core import hotkey
from core.hotkey import DEFAULT_CHORD, PushToTalk, chord_label, qt_sequence


def test_chord_label_and_qt_sequence():
    assert chord_label() == "Ctrl+Space"
    assert chord_label(("shift", "f9")) == "Shift+F9"
    assert chord_label(("alt", "pagedown")) == "Alt+Pagedown"  # unknown keys title-cased
    assert qt_sequence(("ctrl", "insert")) == "Ctrl+Ins"
    assert qt_sequence() == chord_label(DEFAULT_CHORD)


def test_set_held_fires_only_on_change():
    events = []
    ptt = PushToTalk(events.append, chord=("f8",))
    assert ptt.held is False and ptt.scope == "window" and ptt.label == "F8"
    ptt.set_held(True)
    ptt.set_held(1)
    ptt.set_held(False)
    ptt.set_held(0)
    assert events == [True, False]


def test_listener_exception_does_not_break_state():
    def boom(_held):
        raise RuntimeError("listener bug")

    ptt = PushToTalk(boom)
    ptt.set_held(True)
    assert ptt.held is True


def test_stop_without_start_releases_held():
    events = []
    ptt = PushToTalk(events.append)
    ptt.set_held(True)
    ptt.stop()
    assert events == [True, False] and ptt.held is False


def test_start_off_windows_is_window_scope(monkeypatch):
    monkeypatch.setattr(hotkey, "_OS", "Linux")
    ptt = PushToTalk(lambda h: None)
    assert ptt.start() == "window"
    assert ptt._thread is None


def test_can_poll_requires_known_keys(monkeypatch):
    monkeypatch.setattr(ctypes, "windll", SimpleNamespace(user32=SimpleNamespace(GetAsyncKeyState=lambda c: 0)), raising=False)
    assert PushToTalk(lambda h: None, chord=("ctrl", "space"))._can_poll() is True
    assert PushToTalk(lambda h: None, chord=("ctrl", "q"))._can_poll() is False


def test_can_poll_false_without_windll(monkeypatch):
    monkeypatch.setattr(ctypes, "windll", SimpleNamespace(), raising=False)
    assert PushToTalk(lambda h: None)._can_poll() is False


def test_windows_without_hook_falls_back_to_window(monkeypatch):
    monkeypatch.setattr(hotkey, "_OS", "Windows")
    monkeypatch.setattr(PushToTalk, "_can_poll", lambda self: False)
    assert PushToTalk(lambda h: None).start() == "window"


def _drive_poll_loop(monkeypatch, frames, chord=("ctrl", "space")):
    """Run _poll_loop synchronously. frames: list of sets of pressed VK codes, or an Exception."""
    state = {"i": 0, "t": 100.0}
    queried = []

    def get_async_key_state(code):
        frame = frames[state["i"]]
        if isinstance(frame, BaseException):
            raise frame
        queried.append(code)
        return 0x8000 if code in frame else 0

    monkeypatch.setattr(ctypes, "windll", SimpleNamespace(user32=SimpleNamespace(GetAsyncKeyState=get_async_key_state)), raising=False)
    monkeypatch.setattr(hotkey, "time", SimpleNamespace(monotonic=lambda: state["t"]))

    events = []
    ptt = PushToTalk(events.append, chord=chord)
    ptt._scope = "global"

    def fake_wait(period):
        assert period == pytest.approx(1.0 / hotkey._POLL_HZ)
        state["i"] += 1
        state["t"] += 0.05
        if state["i"] >= len(frames):
            ptt._stop.set()
        return ptt._stop.is_set()

    monkeypatch.setattr(ptt._stop, "wait", fake_wait)
    ptt._poll_loop()
    return ptt, events, queried


CTRL, SPACE = hotkey._VK["ctrl"], hotkey._VK["space"]


def test_poll_loop_debounces_then_reports_press_and_release(monkeypatch):
    both = {CTRL, SPACE}
    ptt, events, _ = _drive_poll_loop(monkeypatch, [both, both, both, set(), RuntimeError("teardown")])
    # t=100 down starts timer, t=100.05 below 60 ms debounce, t=100.10 held, then release.
    assert events == [True, False]
    assert ptt.scope == "window"  # loop exit falls back to windowed scope


def test_poll_loop_brief_tap_is_ignored(monkeypatch):
    both = {CTRL, SPACE}
    _, events, _ = _drive_poll_loop(monkeypatch, [both, both, set(), set()])
    assert events == []


def test_poll_loop_requires_whole_chord(monkeypatch):
    _, events, queried = _drive_poll_loop(monkeypatch, [{CTRL}, {CTRL}, {CTRL}, {CTRL}])
    assert events == []
    assert SPACE in queried


def test_poll_loop_exit_releases_held_key(monkeypatch):
    both = {CTRL, SPACE}
    ptt, events, _ = _drive_poll_loop(monkeypatch, [both, both, both, both])
    assert events == [True, False] and ptt.held is False


def test_start_on_windows_runs_global_thread(monkeypatch):
    monkeypatch.setattr(hotkey, "_OS", "Windows")
    monkeypatch.setattr(PushToTalk, "_can_poll", lambda self: True)
    ran = []
    monkeypatch.setattr(PushToTalk, "_poll_loop", lambda self: ran.append(True) or self._stop.wait(5))
    ptt = PushToTalk(lambda h: None)
    assert ptt.start() == "global"
    thread = ptt._thread
    ptt.stop()
    assert ran == [True] and not thread.is_alive() and ptt._thread is None
