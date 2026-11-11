"""Behavioural tests for actions.desktop.

The Desktop folder is redirected to tmp_path and the OS is forced to Linux so
the same branches run on every host. subprocess/Gemini/network are mocked.
"""
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import actions.desktop as desk
from actions.desktop import desktop_control


@pytest.fixture
def desktop_dir(tmp_path, monkeypatch):
    d = tmp_path / "Desktop"
    d.mkdir()
    monkeypatch.setattr(desk, "_OS", "Linux")
    monkeypatch.setattr(desk, "_get_desktop", lambda: d)
    return d


# ── sandboxed exec ───────────────────────────────────────────────────────────

def test_execute_rejects_unsafe_and_empty():
    msg = "This action cannot be performed safely."
    assert desk._execute_generated_code("UNSAFE") == msg
    assert desk._execute_generated_code("") == msg


def test_execute_captures_print_output():
    assert desk._execute_generated_code("print('a', 1)\nprint(len([1,2]))") == "a 1\n2"


def test_execute_strips_code_fence():
    assert desk._execute_generated_code("```python\nprint('ok')\n```") == "ok"


def test_execute_without_output_returns_done():
    assert desk._execute_generated_code("x = 1 + 1") == "Done."


@pytest.mark.parametrize("code", ["import os", "open('x', 'w')", "eval('1')"])
def test_execute_blocks_dangerous_builtins(code):
    assert desk._execute_generated_code(code).startswith("Execution error:")


def test_sandbox_shutil_has_no_destructive_helpers():
    sandbox = desk._build_sandbox()
    assert hasattr(sandbox["shutil"], "copy2")
    assert not hasattr(sandbox["shutil"], "rmtree")
    assert not hasattr(sandbox["shutil"], "move")


# ── _get_desktop ─────────────────────────────────────────────────────────────

def test_get_desktop_honours_xdg_on_linux(tmp_path, monkeypatch):
    monkeypatch.setattr(desk, "_OS", "Linux")
    monkeypatch.setenv("XDG_DESKTOP_DIR", str(tmp_path))
    assert desk._get_desktop() == tmp_path


def test_get_desktop_defaults_to_home(monkeypatch):
    monkeypatch.setattr(desk, "_OS", "Windows")
    assert desk._get_desktop() == Path.home() / "Desktop"


# ── file organisation ────────────────────────────────────────────────────────

def test_organize_by_type_moves_files_and_skips_shortcuts(desktop_dir):
    (desktop_dir / "photo.JPG").write_text("x")
    (desktop_dir / "notes.txt").write_text("x")
    (desktop_dir / "mystery.zzz").write_text("x")
    (desktop_dir / "app.desktop").write_text("x")  # Linux shortcut, skipped
    (desktop_dir / ".hidden").write_text("x")

    out = desk.organize_desktop("by_type")

    assert out.startswith("Desktop organized (by_type): 3 files moved.")
    assert (desktop_dir / "Images" / "photo.JPG").exists()
    assert (desktop_dir / "Documents" / "notes.txt").exists()
    assert (desktop_dir / "Others" / "mystery.zzz").exists()
    assert (desktop_dir / "app.desktop").exists()
    assert (desktop_dir / ".hidden").exists()


def test_organize_skips_name_conflicts(desktop_dir):
    (desktop_dir / "Images").mkdir()
    (desktop_dir / "Images" / "a.png").write_text("old")
    (desktop_dir / "a.png").write_text("new")
    out = desk.organize_desktop()
    assert "0 files moved" in out
    assert "1 file(s) skipped (name conflict)." in out
    assert (desktop_dir / "a.png").read_text() == "new"


def test_organize_by_date_uses_year_month(desktop_dir):
    f = desktop_dir / "old.bin"
    f.write_text("x")
    ts = 1_600_000_000  # 2020-09-13 UTC
    os.utime(f, (ts, ts))
    desk.organize_desktop("by_date")
    from datetime import datetime
    folder = datetime.fromtimestamp(ts).strftime("%Y-%m")
    assert (desktop_dir / folder / "old.bin").exists()


def test_organize_summary_truncates_after_eight(desktop_dir):
    for i in range(10):
        (desktop_dir / f"f{i}.txt").write_text("x")
    out = desk.organize_desktop()
    assert "10 files moved." in out
    assert out.endswith("... and 2 more.")


def test_list_desktop(desktop_dir):
    assert desk.list_desktop() == "Desktop is empty."
    (desktop_dir / "folder").mkdir()
    (desktop_dir / "folder" / "inner.txt").write_text("x")
    (desktop_dir / "file.bin").write_bytes(b"x" * 2048)
    out = desk.list_desktop()
    assert out.startswith("Desktop (2 items):")
    assert "📄 file.bin (2.0 KB)" in out
    assert "📁 folder/ (1 items)" in out


def test_clean_desktop_archives_loose_files(desktop_dir):
    (desktop_dir / "a.txt").write_text("x")
    (desktop_dir / "keep").mkdir()
    out = desk.clean_desktop()
    assert out.startswith("Desktop cleaned: 1 files archived to 'Desktop Archive ")
    archives = [p for p in desktop_dir.iterdir() if p.name.startswith("Desktop Archive")]
    assert len(archives) == 1 and (archives[0] / "a.txt").exists()
    assert (desktop_dir / "keep").is_dir()


def test_desktop_stats(desktop_dir):
    (desktop_dir / "a.bin").write_bytes(b"x" * 1024)
    (desktop_dir / "sub").mkdir()
    out = desk.get_desktop_stats()
    assert "Files   : 1" in out
    assert "Folders : 1" in out
    assert "Size    : 1.0 KB" in out


# ── wallpaper ────────────────────────────────────────────────────────────────

def test_set_wallpaper_missing_and_unsupported(tmp_path):
    assert desk.set_wallpaper(str(tmp_path / "nope.png")).startswith("Image not found")
    gif = tmp_path / "a.gif"
    gif.write_bytes(b"GIF")
    assert desk.set_wallpaper(str(gif)) == "Unsupported format: .gif. Use jpg, png, bmp or webp."


def test_set_wallpaper_gnome_calls_gsettings(tmp_path, monkeypatch):
    img = tmp_path / "w.jpg"
    img.write_bytes(b"\xff\xd8")
    monkeypatch.setattr(desk, "_OS", "Linux")
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "ubuntu:GNOME")
    with patch.object(desk.subprocess, "run") as run:
        assert desk.set_wallpaper(str(img)) == "Wallpaper set: w.jpg"
    calls = [c.args[0] for c in run.call_args_list]
    assert [c[3] for c in calls] == ["picture-uri", "picture-uri-dark"]
    assert all(c[4] == f"file://{img.resolve()}" for c in calls)


def test_set_wallpaper_feh_failure_message(tmp_path, monkeypatch):
    img = tmp_path / "w.png"
    img.write_bytes(b"\x89PNG")
    monkeypatch.setattr(desk, "_OS", "Linux")
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "i3")
    with patch.object(desk.subprocess, "run", return_value=SimpleNamespace(returncode=1)):
        out = desk.set_wallpaper(str(img))
    assert "install 'feh'" in out


def test_current_wallpaper_unsupported_de(monkeypatch):
    monkeypatch.setattr(desk, "_OS", "Linux")
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "sway")
    assert "not supported" in desk.get_current_wallpaper()


def test_set_wallpaper_from_url_reports_download_error():
    with patch("urllib.request.urlretrieve", side_effect=OSError("offline")):
        assert desk.set_wallpaper_from_url("http://x/y.jpg") == (
            "Could not download wallpaper: offline"
        )


# ── desktop_control dispatch ─────────────────────────────────────────────────

def test_dispatch_validations():
    assert desktop_control({"action": "wallpaper"}) == "No image path provided."
    assert desktop_control({"action": "wallpaper_url"}) == "No URL provided."
    assert desktop_control({"action": "task"}) == "Please describe what you want to do on the desktop."
    assert desktop_control({}) == "No action or task specified."


def test_dispatch_list_routes_to_list_desktop(desktop_dir):
    player = MagicMock()
    assert desktop_control({"action": "LIST"}, player=player) == "Desktop is empty."
    player.write_log.assert_any_call("[desktop] list")


def test_dispatch_task_runs_generated_code():
    with patch.object(desk, "_ask_gemini_for_desktop_action", return_value="print('done it')") as ask:
        assert desktop_control({"task": "say hi"}) == "done it"
    ask.assert_called_once_with("say hi")


def test_dispatch_free_form_action_goes_to_gemini():
    with patch.object(desk, "_ask_gemini_for_desktop_action", return_value="UNSAFE"):
        assert desktop_control({"action": "delete everything"}) == (
            "This action cannot be performed safely."
        )


def test_dispatch_wraps_unexpected_errors():
    with patch.object(desk, "list_desktop", side_effect=PermissionError("denied")):
        assert desktop_control({"action": "list"}) == "Desktop control error: denied"


def test_ask_gemini_strips_fence_and_handles_failure():
    from core import gemini
    with patch.object(gemini, "call", return_value=SimpleNamespace(text="```\nprint(1)\n```")):
        assert desk._ask_gemini_for_desktop_action("t") == "print(1)"
    with patch.object(gemini, "call", return_value=None):
        assert desk._ask_gemini_for_desktop_action("t").startswith("ERROR:")
