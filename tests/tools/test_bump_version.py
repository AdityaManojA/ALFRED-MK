"""
tests/tools/test_bump_version.py — Tests for tools/bump_version.py (codebase version bumper).

All file edits happen inside a temporary fake project root.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

import tools.bump_version as bv


@pytest.mark.parametrize("n,roman", [(1, "I"), (4, "IV"), (8, "VIII"), (9, "IX"),
                                     (14, "XIV"), (40, "XL"), (1994, "MCMXCIV")])
def test_roman_roundtrip(n, roman):
    assert bv.int_to_roman(n) == roman
    assert bv.roman_to_int(roman) == n
    assert bv.roman_to_int(roman.lower()) == n


@pytest.mark.parametrize("raw", ["Mark-IX", "mark-9", "IX", "9", "MK-IX", "Alfred-Mark-IX", " mk ix "])
def test_parse_version_variants(raw):
    v = bv.parse_version_string(raw)
    assert (v.num, v.roman) == (9, "IX")
    assert v.full_hyphen == "Mark-IX"
    assert v.full_hyphen_upper == "MARK-IX"
    assert v.short_hyphen == "MK-IX"
    assert v.space_case == "Mark IX"
    assert v.numeric_id == "mk9"
    assert v.title_case_short == "ALFRED-MK-IX"


@pytest.mark.parametrize("raw", ["", "Mark-", "banana", "Mark-IXZ"])
def test_parse_version_rejects_garbage(raw):
    with pytest.raises(ValueError):
        bv.parse_version_string(raw)


def test_detect_current_version(tmp_path):
    with pytest.raises(FileNotFoundError):
        bv.detect_current_version(tmp_path)
    (tmp_path / "ui.py").write_text("X = 1\n", encoding="utf-8")
    with pytest.raises(ValueError):
        bv.detect_current_version(tmp_path)
    (tmp_path / "ui.py").write_text("APP_VERSION = 'Mark-VIII'\n", encoding="utf-8")
    assert bv.detect_current_version(tmp_path).num == 8


def test_replacement_pairs_unique_and_longest_first():
    pairs = bv.build_replacement_pairs(bv.parse_version_string("VIII"), bv.parse_version_string("IX"))
    keys = [k for k, _ in pairs]
    assert len(keys) == len(set(keys))
    assert [len(k) for k in keys] == sorted((len(k) for k in keys), reverse=True)
    mapping = dict(pairs)
    assert mapping["ALFRED-Mark-VIII"] == "ALFRED-Mark-IX"
    assert mapping["batcomputer.mk8"] == "batcomputer.mk9"
    assert mapping["MK-VIII"] == "MK-IX"


def test_replacement_pairs_identical_versions_empty():
    v = bv.parse_version_string("IX")
    assert bv.build_replacement_pairs(v, v) == []


@pytest.fixture
def project(tmp_path):
    (tmp_path / "ui.py").write_text('APP_VERSION = "Mark-VIII"\nTITLE = "ALFRED-MK-VIII"\n', encoding="utf-8")
    (tmp_path / "readme.md").write_text(
        "# Alfred-Mark-VIII\nWhat's New in Mark VIII\nid batcomputer.mk8\nunrelated\n", encoding="utf-8")
    (tmp_path / "main.py").write_text("print('nothing to see')\n", encoding="utf-8")
    return tmp_path


def test_apply_version_bump_live(project):
    stats = bv.apply_version_bump(project, bv.parse_version_string("IX"))
    assert set(stats) == {"ui.py", "readme.md"}
    assert stats["ui.py"] == 2
    ui = (project / "ui.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "Mark-IX"' in ui and "ALFRED-MK-IX" in ui
    readme = (project / "readme.md").read_text(encoding="utf-8")
    assert "Alfred-Mark-IX" in readme
    assert "What's New in Mark IX" in readme
    assert "batcomputer.mk9" in readme
    assert "VIII" not in readme and "mk8" not in readme
    assert (project / "main.py").read_text(encoding="utf-8") == "print('nothing to see')\n"


def test_apply_version_bump_dry_run_leaves_files(project):
    before = (project / "readme.md").read_text(encoding="utf-8")
    stats = bv.apply_version_bump(project, bv.parse_version_string("10"), dry_run=True)
    assert stats["readme.md"] >= 3
    assert (project / "readme.md").read_text(encoding="utf-8") == before


def test_apply_version_bump_same_version_noop(project):
    assert bv.apply_version_bump(project, bv.parse_version_string("Mark-VIII")) == {}
    assert "Mark-VIII" in (project / "ui.py").read_text(encoding="utf-8")


def test_main_bad_target_exits(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["bump_version.py", "banana"])
    apply = MagicMock()
    monkeypatch.setattr(bv, "apply_version_bump", apply)
    with pytest.raises(SystemExit) as ei:
        bv.main()
    assert ei.value.code == 1
    apply.assert_not_called()


def test_main_runs_follow_ups_only_after_live_changes(monkeypatch, tmp_path):
    run = MagicMock()
    monkeypatch.setattr(bv.subprocess, "run", run)
    monkeypatch.setattr(bv, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(bv, "apply_version_bump", MagicMock(return_value={"ui.py": 1}))

    monkeypatch.setattr(sys, "argv", ["bump_version.py", "IX", "--run-tests", "--update-graph"])
    bv.main()
    cmds = [c.args[0][1:] for c in run.call_args_list]
    assert cmds == [["-m", "unittest", "discover", "-s", "tests"], ["-m", "graphify", "update", "."]]
    assert all(c.kwargs["cwd"] == tmp_path for c in run.call_args_list)
    target = bv.apply_version_bump.call_args.args[1]
    assert target.roman == "IX"

    run.reset_mock()
    monkeypatch.setattr(sys, "argv", ["bump_version.py", "IX", "--dry-run", "--run-tests"])
    bv.main()
    run.assert_not_called()
    assert bv.apply_version_bump.call_args.kwargs["dry_run"] is True
