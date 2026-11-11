"""Behavioural tests for core.undo (shared undo stack)."""
from __future__ import annotations

import threading

import pytest

from core import undo


@pytest.fixture(autouse=True)
def _fresh_stack():
    undo.clear()
    yield
    undo.clear()


def test_empty_stack():
    assert undo.can_undo() is False
    assert undo.peek() == ""
    assert undo.history() == []
    assert undo.undo_last().startswith("There is nothing to undo.")


def test_lifo_order_and_messages():
    log = []
    undo.push_undo("first", lambda: log.append(1) or "restored A")
    undo.push_undo("second", lambda: log.append(2))
    assert undo.peek() == "second"
    assert undo.history() == ["second", "first"]
    assert undo.undo_last() == "Undone: second."
    assert undo.undo_last() == "Undone: first. restored A"
    assert log == [2, 1]
    assert undo.can_undo() is False


def test_non_callable_ignored_and_label_truncated():
    undo.push_undo("bad", "not callable")  # type: ignore[arg-type]
    assert undo.can_undo() is False
    undo.push_undo("x" * 500, lambda: "")
    assert undo.peek() == "x" * 120


def test_depth_is_capped_dropping_oldest():
    for i in range(undo.MAX_DEPTH + 5):
        undo.push_undo(f"op{i}", lambda: "")
    hist = undo.history()
    assert len(hist) == undo.MAX_DEPTH
    assert hist[0] == f"op{undo.MAX_DEPTH + 4}" and hist[-1] == "op5"


def test_failing_undo_is_popped_not_retried():
    def broken():
        raise FileNotFoundError("gone")

    undo.push_undo("ok", lambda: "")
    undo.push_undo("move file", broken)
    assert undo.undo_last() == "Could not undo 'move file': gone"
    assert undo.peek() == "ok"


def test_clear_empties_stack():
    undo.push_undo("a", lambda: "")
    undo.clear()
    assert undo.can_undo() is False


def test_concurrent_pushes_respect_cap():
    def worker(n):
        for i in range(50):
            undo.push_undo(f"{n}-{i}", lambda: "")

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(undo.history()) == undo.MAX_DEPTH
