"""Behavioural tests for core.scheduler.automation (focus gate + macro injection)."""
from __future__ import annotations

import subprocess
import sys
import types
from types import SimpleNamespace

import pytest

from core.scheduler import automation
from core.scheduler.automation import AutomationResult, focus_target, run_macro


class _Recorder:
    def __init__(self, results):
        self.calls = []
        self._results = list(results)

    def __call__(self, args, **kwargs):
        self.calls.append(list(args))
        result = self._results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


def test_focus_target_rejects_blank_keyword(monkeypatch):
    called = []
    monkeypatch.setattr(automation, "_focus_windows", lambda k: called.append(k) or True)
    monkeypatch.setattr(automation.platform, "system", lambda: "Windows")
    assert focus_target("   ") is False
    assert focus_target(None) is False
    assert called == []


@pytest.mark.parametrize(
    "system, target", [("Windows", "_focus_windows"), ("Darwin", "_focus_macos"), ("Linux", "_focus_linux")]
)
def test_focus_target_dispatches_by_platform_and_strips(monkeypatch, system, target):
    seen = {}
    for name in ("_focus_windows", "_focus_macos", "_focus_linux"):
        monkeypatch.setattr(automation, name, lambda k, n=name: seen.setdefault(n, k) is not None)
    monkeypatch.setattr(automation.platform, "system", lambda: system)
    assert focus_target("  Notepad ") is True
    assert seen == {target: "Notepad"}


def test_focus_macos_builds_osascript(monkeypatch):
    rec = _Recorder([SimpleNamespace(returncode=0)])
    monkeypatch.setattr(automation.subprocess, "run", rec)
    assert automation._focus_macos("Safari") is True
    assert rec.calls[0][:2] == ["osascript", "-e"]
    assert "contains 'Safari' to true" in rec.calls[0][2]


def test_focus_macos_failure_paths(monkeypatch):
    monkeypatch.setattr(automation.subprocess, "run", _Recorder([SimpleNamespace(returncode=1)]))
    assert automation._focus_macos("x") is False
    monkeypatch.setattr(automation.subprocess, "run", _Recorder([OSError("no osascript")]))
    assert automation._focus_macos("x") is False


def test_focus_linux_activates_first_window(monkeypatch):
    rec = _Recorder([SimpleNamespace(stdout="\n  123 \n456\n", returncode=0), SimpleNamespace(returncode=0)])
    monkeypatch.setattr(automation.subprocess, "run", rec)
    assert automation._focus_linux("term") is True
    assert rec.calls == [["xdotool", "search", "--name", "term"], ["xdotool", "windowactivate", "--sync", "123"]]


def test_focus_linux_no_match_skips_activate(monkeypatch):
    rec = _Recorder([SimpleNamespace(stdout="\n\n", returncode=1)])
    monkeypatch.setattr(automation.subprocess, "run", rec)
    assert automation._focus_linux("term") is False
    assert len(rec.calls) == 1


def test_focus_linux_timeout_returns_false(monkeypatch):
    monkeypatch.setattr(automation.subprocess, "run", _Recorder([subprocess.TimeoutExpired("xdotool", 3)]))
    assert automation._focus_linux("term") is False


def _fake_window(title, minimized=False):
    win = SimpleNamespace(title=title, isMinimized=minimized, restored=False, activated=False)
    win.restore = lambda: setattr(win, "restored", True)
    win.activate = lambda: setattr(win, "activated", True)
    return win


def test_focus_windows_matches_case_insensitively_and_restores(monkeypatch):
    other, target = _fake_window("Calculator"), _fake_window("My NOTEPAD doc", minimized=True)
    monkeypatch.setitem(sys.modules, "pygetwindow", types.SimpleNamespace(getAllWindows=lambda: [other, _fake_window(None), target]))
    assert automation._focus_windows("notepad") is True
    assert target.restored and target.activated and not other.activated


def test_focus_windows_no_match(monkeypatch):
    monkeypatch.setitem(sys.modules, "pygetwindow", types.SimpleNamespace(getAllWindows=lambda: [_fake_window("Calc")]))
    assert automation._focus_windows("notepad") is False


@pytest.fixture
def fake_input(monkeypatch):
    log = []
    monkeypatch.setitem(sys.modules, "pyperclip", types.SimpleNamespace(copy=lambda t: log.append(("copy", t))))
    monkeypatch.setitem(
        sys.modules,
        "pyautogui",
        types.SimpleNamespace(hotkey=lambda *k: log.append(("hotkey", k)), press=lambda k: log.append(("press", k))),
    )
    monkeypatch.setattr(automation.time, "sleep", lambda s: log.append(("sleep", s)))
    monkeypatch.setattr(automation.platform, "system", lambda: "Linux")
    monkeypatch.setattr(automation, "focus_target", lambda t: log.append(("focus", t)) or True)
    return log


def test_run_macro_requires_target_and_text(fake_input):
    assert run_macro({"paste_text": "hi"}) == AutomationResult(False, "A target application or tab keyword is required.")
    assert run_macro({"target_app": "x"}) == AutomationResult(False, "Macro has no text to paste.")
    assert fake_input == []


def test_run_macro_full_sequence_prefers_tab(fake_input):
    result = run_macro({"target_tab": "ChatGPT", "target_app": "chrome", "paste_text": "hello"})
    assert result == AutomationResult(True, "Pasted into ChatGPT.")
    assert fake_input == [("focus", "ChatGPT"), ("copy", "hello"), ("hotkey", ("ctrl", "v")), ("sleep", 0.2), ("press", "enter")]


def test_run_macro_mac_uses_command_and_hit_run_false(fake_input, monkeypatch):
    monkeypatch.setattr(automation.platform, "system", lambda: "Darwin")
    assert run_macro({"target_app": "x", "paste_text": "t", "hit_run": False}).ok
    assert ("hotkey", ("command", "v")) in fake_input
    assert not any(e[0] == "press" for e in fake_input)


def test_run_macro_focus_failure_aborts_before_paste(fake_input, monkeypatch):
    monkeypatch.setattr(automation, "focus_target", lambda t: False)
    result = run_macro({"target_app": "ghost", "paste_text": "t"})
    assert result == AutomationResult(False, "Could not focus target 'ghost'.")
    assert fake_input == []


def test_run_macro_injection_error_reported(fake_input, monkeypatch):
    def boom(_t):
        raise RuntimeError("clipboard locked")

    monkeypatch.setitem(sys.modules, "pyperclip", types.SimpleNamespace(copy=boom))
    result = run_macro({"target_app": "x", "paste_text": "t"})
    assert not result.ok and "clipboard locked" in result.detail
