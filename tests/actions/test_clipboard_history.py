"""Behavioural tests for actions.clipboard_history (pyperclip is mocked)."""
from unittest.mock import patch

import pytest

import actions.clipboard_history as ch
from actions.clipboard_history import clipboard_history_action


@pytest.fixture(autouse=True)
def _clean_history():
    ch._history.clear()
    yield
    ch._history.clear()


def _paste_returns(value):
    return patch.object(ch.pyperclip, "paste", return_value=value)


def test_push_requires_text():
    assert clipboard_history_action({"action": "push", "text": "   "}) == (
        "No text provided to push into clipboard history."
    )


def test_push_then_show_lists_entries_in_order():
    with _paste_returns(""):
        clipboard_history_action({"action": "push", "text": "first"})
        clipboard_history_action({"action": "push", "text": "second"})
        out = clipboard_history_action({"action": "show"})
    lines = out.splitlines()
    assert lines[0] == "Clipboard history (most recent last):"
    assert lines[1].endswith("first") and lines[1].strip().startswith("1.")
    assert lines[2].endswith("second") and lines[2].strip().startswith("2.")


def test_show_pulls_current_clipboard():
    with _paste_returns("from clipboard"):
        out = clipboard_history_action({"action": "show"})
    assert "from clipboard" in out


def test_show_empty_history():
    with patch.object(ch.pyperclip, "paste", side_effect=RuntimeError("no clipboard")):
        assert clipboard_history_action({"action": "list"}) == (
            "The clipboard history is empty for this session."
        )


def test_consecutive_duplicates_are_collapsed():
    ch._push("same")
    ch._push("same")
    ch._push("other")
    ch._push("same")
    assert [e["text"] for e in ch._snapshot()] == ["same", "other", "same"]


def test_duplicate_with_surrounding_whitespace_is_collapsed():
    # Regression: clipboard text with a trailing newline used to be appended
    # again on every 'show' because the stored copy was stripped but the
    # comparison was not.
    ch._push("hello\n")
    ch._push("hello\n")
    assert [e["text"] for e in ch._snapshot()] == ["hello"]


def test_ring_buffer_keeps_last_max_entries():
    for i in range(ch._MAX_ENTRIES + 5):
        ch._push(f"item {i}")
    texts = [e["text"] for e in ch._snapshot()]
    assert len(texts) == ch._MAX_ENTRIES
    assert texts[0] == "item 5"
    assert texts[-1] == f"item {ch._MAX_ENTRIES + 4}"


def test_long_entries_are_truncated_with_ellipsis_and_newlines_flattened():
    ch._push("line1\n" + "x" * 200)
    with _paste_returns(""):
        out = clipboard_history_action({"action": "show"})
    entry_line = out.splitlines()[1]
    assert "\n" not in entry_line
    assert entry_line.endswith("…")


def test_latest_returns_most_recent():
    ch._push("older")
    with _paste_returns("newest"):
        out = clipboard_history_action({"action": "latest"})
    assert out.startswith("Last copied [")
    assert out.endswith("newest")


def test_latest_reports_clipboard_failure():
    with patch.object(ch.pyperclip, "paste", side_effect=RuntimeError("boom")):
        assert clipboard_history_action({"action": "last"}) == "Could not read the clipboard."


def test_clear_empties_history():
    ch._push("something")
    assert clipboard_history_action({"action": "wipe"}) == "Clipboard history cleared."
    assert ch._snapshot() == []


def test_unknown_action():
    out = clipboard_history_action({"action": "explode"})
    assert "Unknown clipboard_history action: 'explode'" in out
