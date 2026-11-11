"""Behavioural tests for actions.intel_notes (notes file redirected to tmp_path)."""
import json
from unittest.mock import MagicMock

import pytest

import actions.intel_notes as notes_mod
from actions.intel_notes import intel_notes


@pytest.fixture(autouse=True)
def notes_file(tmp_path, monkeypatch):
    f = tmp_path / "intel_notes.json"
    monkeypatch.setattr(notes_mod, "_NOTES_FILE", f)
    return f


@pytest.mark.parametrize(
    "content, explicit, expected",
    [
        ("see https://example.com/page", "", "link"),
        ("```py\nprint(1)\n```", "", "code"),
        ('{"a": 1}', "", "data"),
        ("[1, 2, 3]", "", "data"),
        ("def f():\n    return 1", "", "data"),
        ("name: alfred\nrole: butler\nhome: manor", "", "data"),
        ("buy milk", "", "note"),
        ("https://example.com", "CODE", "code"),   # explicit type wins
        ("buy milk", "bogus", "note"),             # invalid explicit ignored
    ],
)
def test_auto_detect_type(content, explicit, expected):
    assert notes_mod._auto_detect_type(content, explicit) == expected


def test_load_notes_handles_missing_and_corrupt(notes_file):
    assert notes_mod._load_notes() == []
    notes_file.write_text("{not json", encoding="utf-8")
    assert notes_mod._load_notes() == []


def test_add_requires_content_or_title():
    assert intel_notes({"action": "add"}) == (
        "Please provide content or a link to post into the Intel Terminal."
    )


def test_add_persists_entry_and_forwards_to_player(notes_file):
    player = MagicMock()
    out = intel_notes(
        {"title": "Docs", "content": "https://docs.python.org"}, player=player
    )
    assert out == "Link recorded to dedicated Notes Terminal: 'Docs'."
    saved = json.loads(notes_file.read_text(encoding="utf-8"))
    assert len(saved) == 1
    assert saved[0]["title"] == "Docs" and saved[0]["type"] == "link"
    assert set(saved[0]) == {"title", "content", "type", "time", "date"}
    player.add_intel_note.assert_called_once_with("Docs", "https://docs.python.org", "link")


def test_add_generates_title_from_first_line():
    long_line = "A" * 50
    out = intel_notes({"content": f"{long_line}\nsecond line"})
    assert f"'{'A' * 40}...'" in out


def test_add_survives_player_failure(notes_file):
    player = MagicMock()
    player.add_intel_note.side_effect = RuntimeError("ui gone")
    out = intel_notes({"content": "remember this"}, player=player)
    assert out.startswith("Note pinned")
    assert len(json.loads(notes_file.read_text(encoding="utf-8"))) == 1


def test_notes_are_capped_at_200(notes_file):
    notes_file.write_text(
        json.dumps([{"title": f"n{i}", "type": "note"} for i in range(200)]), encoding="utf-8"
    )
    intel_notes({"content": "newest"})
    saved = json.loads(notes_file.read_text(encoding="utf-8"))
    assert len(saved) == 200
    assert saved[0]["title"] == "n1"
    assert saved[-1]["content"] == "newest"


def test_list_shows_last_ten(notes_file):
    assert intel_notes({"action": "list"}) == "Intel & Notes Terminal is currently empty."
    notes_file.write_text(
        json.dumps([{"title": f"n{i}", "type": "code", "time": "10:00:00"} for i in range(12)]),
        encoding="utf-8",
    )
    out = intel_notes({"action": "LIST"})
    lines = out.splitlines()
    assert lines[0] == "Recent Intel entries (12 total):"
    assert len(lines) == 11
    assert lines[1] == "• [CODE] n2 (10:00:00)"


def test_clear_empties_file_and_player(notes_file):
    intel_notes({"content": "x"})
    player = MagicMock()
    assert intel_notes({"action": "clear"}, player=player) == "Dedicated Intel & Notes Terminal cleared."
    assert json.loads(notes_file.read_text(encoding="utf-8")) == []
    player.clear_intel_notes.assert_called_once()
