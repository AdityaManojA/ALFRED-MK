"""Behavioural tests for core.sentry.answer_window.AnswerWindow."""
from __future__ import annotations

import asyncio

import pytest

from core import registry
from core.sentry.answer_window import DEFAULT_PROMPT, AnswerWindow


@pytest.fixture(autouse=True)
def _clean_registry():
    registry.unregister("active_answer_window")
    yield
    registry.unregister("active_answer_window")


def _window(answer=None):
    log = []
    win = AnswerWindow()

    def speak(text):
        log.append(("speak", text))
        # Registry should expose the window while it is open.
        log.append(("registered", registry.lookup("active_answer_window") is win))
        if answer is not None:
            log.append(("submitted", win.submit_answer(answer)))

    win.set_callbacks(speak, lambda on: log.append(("gate", on)))
    return win, log


def test_submit_rejected_when_inactive_or_blank():
    win = AnswerWindow()
    assert win.is_active is False
    assert win.submit_answer("hello") is False
    assert win.submit_answer("   ") is False


def test_sync_answer_roundtrip_and_cleanup():
    win, log = _window(answer="  watch the oven  ")
    result = win.request_answer_sync("Prompt?", timeout_s=5)
    assert result == "watch the oven"
    assert log == [("gate", True), ("speak", "Prompt?"), ("registered", True), ("submitted", True), ("gate", False)]
    assert win.is_active is False
    assert registry.lookup("active_answer_window") is None


def test_sync_timeout_returns_empty():
    win, log = _window()
    assert win.request_answer_sync("", timeout_s=0.01) == ""  # clamped to 1s minimum
    assert ("gate", False) in log
    assert not any(e[0] == "speak" for e in log)  # empty prompt is not spoken


def test_async_answer_roundtrip():
    win, log = _window(answer="the door")
    result = asyncio.run(win.request_answer(timeout_s=5))
    assert result == "the door"
    assert log[1] == ("speak", DEFAULT_PROMPT)
    assert log[-1] == ("gate", False)
    assert win.is_active is False


def test_async_cancel_returns_empty():
    win, log = _window()

    async def scenario():
        task = asyncio.create_task(win.request_answer("p", timeout_s=30))
        await asyncio.sleep(0.01)
        assert win.is_active
        win.cancel()
        return await task

    assert asyncio.run(scenario()) == ""
    assert log[-1] == ("gate", False)


def test_async_timeout_returns_empty(monkeypatch):
    async def fake_wait_for(fut, timeout):
        assert timeout == 1.0  # timeouts below 1s are clamped
        raise asyncio.TimeoutError

    monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)
    win, _ = _window()
    assert asyncio.run(win.request_answer("p", timeout_s=0.2)) == ""
    assert win.is_active is False


def test_callback_exceptions_are_swallowed():
    def bad(*_a):
        raise RuntimeError("boom")

    win = AnswerWindow(speak_fn=bad, un_gate_fn=bad)
    assert win.request_answer_sync("p", timeout_s=0) == ""
    assert win.is_active is False


def test_cancel_when_inactive_is_noop():
    gates = []
    win = AnswerWindow(un_gate_fn=gates.append)
    win.cancel()
    assert gates == []
