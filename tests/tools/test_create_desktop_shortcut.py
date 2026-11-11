"""
tests/tools/test_create_desktop_shortcut.py — Tests for tools/create_desktop_shortcut.py.

Desktop/known-folder lookups, COM, wscript and PowerShell are all faked, and every
shortcut is written under tmp_path (never the real Desktop).
"""
from __future__ import annotations

import ctypes
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import tools.create_desktop_shortcut as cds


# ── get_real_desktop_dir ─────────────────────────────────────────────────────

def test_linux_uses_xdg_user_dir(monkeypatch, tmp_path):
    desk = tmp_path / "Schreibtisch"
    desk.mkdir()
    monkeypatch.setattr(cds, "_SYSTEM", "Linux")
    calls = []
    monkeypatch.setattr(cds.subprocess, "run",
                        lambda args, **k: calls.append(args) or SimpleNamespace(stdout=f"{desk}\n"))
    assert cds.get_real_desktop_dir() == desk
    assert calls == [["xdg-user-dir", "DESKTOP"]]


def test_linux_falls_back_to_home_desktop(monkeypatch, tmp_path):
    monkeypatch.setattr(cds, "_SYSTEM", "Linux")
    monkeypatch.setattr(cds.Path, "home", classmethod(lambda cls: tmp_path))

    def missing(*a, **k):
        raise FileNotFoundError("xdg-user-dir")
    monkeypatch.setattr(cds.subprocess, "run", missing)
    assert cds.get_real_desktop_dir() == tmp_path / "Desktop"


def test_other_os_returns_home_desktop(monkeypatch, tmp_path):
    monkeypatch.setattr(cds, "_SYSTEM", "Darwin")
    monkeypatch.setattr(cds.Path, "home", classmethod(lambda cls: tmp_path))
    assert cds.get_real_desktop_dir() == tmp_path / "Desktop"


def _fake_windll(result_path=None):
    freed = []

    def known_folder(fid_ref, flags, token, buf_ref):
        if result_path is None:
            return 1  # E_FAIL
        buf_ref._obj.value = str(result_path)
        return 0
    return SimpleNamespace(
        shell32=SimpleNamespace(SHGetKnownFolderPath=known_folder),
        ole32=SimpleNamespace(CoTaskMemFree=lambda buf: freed.append(buf)),
    ), freed


def test_windows_known_folder_path(monkeypatch, tmp_path):
    pytest.importorskip("ctypes.wintypes")
    desk = tmp_path / "OneDrive" / "Desktop"
    desk.mkdir(parents=True)
    windll, freed = _fake_windll(desk)
    monkeypatch.setattr(cds, "_SYSTEM", "Windows")
    monkeypatch.setattr(ctypes, "windll", windll, raising=False)
    assert cds.get_real_desktop_dir() == desk
    assert len(freed) == 1


def test_windows_registry_fallback_expands_vars(monkeypatch, tmp_path):
    desk = tmp_path / "RegDesk"
    desk.mkdir()
    windll, _ = _fake_windll(None)
    monkeypatch.setattr(cds, "_SYSTEM", "Windows")
    monkeypatch.setattr(ctypes, "windll", windll, raising=False)
    monkeypatch.setenv("ALFRED_TEST_DESK", str(tmp_path))

    class _Key:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    winreg = types.ModuleType("winreg")
    winreg.HKEY_CURRENT_USER = object()
    opened = []
    winreg.OpenKey = lambda root, path: opened.append(path) or _Key()
    winreg.QueryValueEx = lambda key, name: (
        ("%ALFRED_TEST_DESK%" + "/RegDesk", 2) if name == "Desktop" else (None, 0))
    monkeypatch.setitem(sys.modules, "winreg", winreg)
    assert cds.get_real_desktop_dir() == desk
    assert opened[0].endswith("User Shell Folders")


# ── resolve_icon_path ────────────────────────────────────────────────────────

def test_resolve_icon_prefers_alfred_then_jarvis(monkeypatch, tmp_path):
    monkeypatch.setattr(cds, "_PROJECT_ROOT", tmp_path)
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "jarvis.ico").write_bytes(b"j")
    (cfg / "batman_logo.ico").write_bytes(b"b")
    assert cds.resolve_icon_path() == cfg / "jarvis.ico"
    (cfg / "alfred.ico").write_bytes(b"a")
    assert cds.resolve_icon_path() == cfg / "alfred.ico"


def test_resolve_icon_generates_via_ui(monkeypatch, tmp_path):
    monkeypatch.setattr(cds, "_PROJECT_ROOT", tmp_path)
    builder = MagicMock(return_value=False)
    fake_ui = types.ModuleType("ui")
    fake_ui.MainWindow = SimpleNamespace(_build_jarvis_icon=builder)
    monkeypatch.setitem(sys.modules, "ui", fake_ui)
    out = cds.resolve_icon_path()
    assert out == tmp_path / "config" / "alfred.ico"
    builder.assert_called_once_with(out)


# ── create_windows_lnk ───────────────────────────────────────────────────────

@pytest.fixture
def lnk_args(tmp_path):
    icon = tmp_path / "alfred.ico"
    icon.write_bytes(b"i")
    return dict(
        lnk_path=tmp_path / "A.L.F.R.E.D.lnk",
        target_exe=tmp_path / "pythonw.exe",
        script_path=tmp_path / "main.py",
        work_dir=tmp_path,
        icon_path=icon,
    )


def _install_win32com(monkeypatch, dispatch):
    pkg = types.ModuleType("win32com")
    client = types.ModuleType("win32com.client")
    client.Dispatch = dispatch
    pkg.client = client
    monkeypatch.setitem(sys.modules, "win32com", pkg)
    monkeypatch.setitem(sys.modules, "win32com.client", client)


def test_lnk_via_pywin32(monkeypatch, lnk_args):
    sc = MagicMock()
    sc.save.side_effect = lambda: lnk_args["lnk_path"].write_bytes(b"lnk")
    shell = MagicMock()
    shell.CreateShortCut.return_value = sc
    _install_win32com(monkeypatch, lambda name: shell)
    ok, msg = cds.create_windows_lnk(**lnk_args)
    assert ok and "pywin32" in msg
    shell.CreateShortCut.assert_called_once_with(str(lnk_args["lnk_path"]))
    assert sc.TargetPath == str(lnk_args["target_exe"])
    assert sc.Arguments == f'"{lnk_args["script_path"]}"'
    assert sc.IconLocation == str(lnk_args["icon_path"])


def _no_pywin32(monkeypatch):
    def dispatch(name):
        raise OSError("COM not registered")
    _install_win32com(monkeypatch, dispatch)


def test_lnk_via_wscript_vbs(monkeypatch, lnk_args):
    _no_pywin32(monkeypatch)
    scripts = []

    class _Proc:
        def __init__(self, args, **kw):
            scripts.append((args, Path(args[-1]).read_text(encoding="utf-8")))
            lnk_args["lnk_path"].write_bytes(b"lnk")

        def wait(self, timeout=None):
            return 0
    monkeypatch.setattr(cds.subprocess, "Popen", _Proc)
    ok, msg = cds.create_windows_lnk(**lnk_args)
    assert ok and "WScript" in msg
    args, vbs = scripts[0]
    assert args[:2] == ["wscript.exe", "/nologo"]
    assert f'CreateShortcut("{lnk_args["lnk_path"]}")' in vbs
    assert "sc.Save" in vbs
    assert not Path(args[-1]).exists()  # temp script removed


def test_lnk_via_powershell_escapes_quotes(monkeypatch, tmp_path, lnk_args):
    _no_pywin32(monkeypatch)

    def popen(*a, **k):
        raise FileNotFoundError("wscript.exe")
    monkeypatch.setattr(cds.subprocess, "Popen", popen)
    weird = tmp_path / "O'Brien"
    weird.mkdir()
    lnk_args["work_dir"] = weird
    captured = []

    def run(args, **kw):
        captured.append(args)
        lnk_args["lnk_path"].write_bytes(b"lnk")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(cds.subprocess, "run", run)
    ok, msg = cds.create_windows_lnk(**lnk_args)
    assert ok and "PowerShell" in msg
    assert captured[0][0] == "powershell.exe"
    assert "O''Brien" in captured[0][-1]


def test_lnk_all_methods_fail_uses_exe_icon(monkeypatch, lnk_args):
    _no_pywin32(monkeypatch)
    monkeypatch.setattr(cds.subprocess, "Popen", MagicMock(side_effect=FileNotFoundError()))
    captured = []
    monkeypatch.setattr(cds.subprocess, "run", lambda args, **kw: captured.append(args))
    lnk_args["icon_path"] = lnk_args["work_dir"] / "missing.ico"
    ok, msg = cds.create_windows_lnk(**lnk_args)
    assert not ok
    assert "COM not registered" in msg
    assert f"{lnk_args['target_exe']},0" in captured[0][-1]


# ── main ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def main_env(monkeypatch, tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "main.py").write_text("print('hi')\n", encoding="utf-8")
    desk = tmp_path / "Desktop"
    monkeypatch.setattr(cds, "_PROJECT_ROOT", root)
    monkeypatch.setattr(cds, "get_real_desktop_dir", lambda: desk)
    monkeypatch.setattr(cds, "resolve_icon_path", lambda: root / "config" / "alfred.ico")
    return root, desk


def test_main_linux_writes_desktop_entry(monkeypatch, main_env):
    root, desk = main_env
    monkeypatch.setattr(cds, "_SYSTEM", "Linux")
    assert cds.main() == 0
    entry = (desk / "ALFRED.desktop").read_text()
    assert "[Desktop Entry]" in entry
    assert f"Exec={sys.executable} {root / 'main.py'}" in entry
    assert f"Path={root}" in entry


def test_main_macos_creates_app_bundle(monkeypatch, main_env):
    root, desk = main_env
    monkeypatch.setattr(cds, "_SYSTEM", "Darwin")
    assert cds.main() == 0
    launcher = desk / "A.L.F.R.E.D.app" / "Contents" / "MacOS" / "ALFRED"
    text = launcher.read_text()
    assert text.startswith("#!/usr/bin/env bash")
    assert f'cd "{root}"' in text


def test_main_missing_main_script(monkeypatch, main_env):
    root, _ = main_env
    (root / "main.py").unlink()
    monkeypatch.setattr(cds, "_SYSTEM", "Linux")
    assert cds.main() == 1


@pytest.mark.parametrize("ok,code", [(True, 0), (False, 1)])
def test_main_windows_delegates_to_lnk(monkeypatch, main_env, ok, code):
    root, desk = main_env
    monkeypatch.setattr(cds, "_SYSTEM", "Windows")
    _install_win32com(monkeypatch, MagicMock())
    seen = {}

    def fake_lnk(lnk_path, target_exe, script_path, work_dir, icon_path):
        seen.update(lnk=lnk_path, script=script_path, work=work_dir)
        if ok:
            lnk_path.write_bytes(b"lnk")
        return ok, "msg"
    monkeypatch.setattr(cds, "create_windows_lnk", fake_lnk)
    assert cds.main() == code
    assert seen["lnk"] == desk / "A.L.F.R.E.D.lnk"
    assert seen["script"] == root / "main.py"
    assert seen["work"] == root
