"""
tests/test_setup_script.py — Tests for the repo-root setup.py one-time installer script.

setup.py is a plain script (it does not call setuptools.setup). Importing it is safe
because main() is guarded by __main__; every subprocess call is mocked so nothing
is installed or downloaded.
"""
from __future__ import annotations

import subprocess
import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import setup as setup_script


def _fake_sys(version):
    def _exit(code=0):
        raise SystemExit(code)
    return SimpleNamespace(version_info=version, exit=_exit, platform=sys.platform,
                           executable=sys.executable)


def test_module_is_repo_setup_script():
    assert (setup_script.HERE / "setup.py").samefile(setup_script.__file__)
    assert (setup_script.HERE / "requirements.txt").exists()
    assert setup_script.MIN_PY < setup_script.MAX_PY


def test_run_invokes_subprocess_with_check(monkeypatch, capsys):
    run = MagicMock()
    monkeypatch.setattr(setup_script.subprocess, "run", run)
    setup_script._run("Doing a thing", ["cmd", "arg"])
    run.assert_called_once_with(["cmd", "arg"], check=True)
    assert "▶ Doing a thing" in capsys.readouterr().out


def test_check_python_too_old_exits(monkeypatch, capsys):
    monkeypatch.setattr(setup_script, "sys", _fake_sys((3, 10, 0)))
    with pytest.raises(SystemExit) as ei:
        setup_script._check_python()
    assert ei.value.code == 1
    assert "needs at" in capsys.readouterr().out


def test_check_python_newer_only_warns(monkeypatch, capsys):
    monkeypatch.setattr(setup_script, "sys", _fake_sys((3, 99, 0)))
    setup_script._check_python()
    assert "newer than" in capsys.readouterr().out


def test_check_python_supported_is_silent(monkeypatch, capsys):
    monkeypatch.setattr(setup_script, "sys", _fake_sys(setup_script.MIN_PY + (0,)))
    setup_script._check_python()
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("size,warns", [(None, True), (10, True), (5000, False)])
def test_check_assets(monkeypatch, tmp_path, capsys, size, warns):
    monkeypatch.setattr(setup_script, "HERE", tmp_path)
    if size is not None:
        (tmp_path / "core").mkdir()
        (tmp_path / "core" / "face_model.obj").write_bytes(b"v" * size)
    setup_script._check_assets()
    assert ("missing or truncated" in capsys.readouterr().out) is warns


def _stub_wake_modules(monkeypatch, ok, ready):
    ww = types.ModuleType("core.wake_word")
    ww.ensure_models_downloaded = lambda logger=None: (ok, "msg-from-download")
    ww.is_ready = lambda: ready
    cm = types.ModuleType("memory.config_manager")
    cm.save_wake_word_enabled = MagicMock()
    monkeypatch.setitem(sys.modules, "core.wake_word", ww)
    monkeypatch.setitem(sys.modules, "memory.config_manager", cm)
    return cm.save_wake_word_enabled


def test_setup_wake_word_enables_when_ready(monkeypatch, capsys):
    save = _stub_wake_modules(monkeypatch, ok=True, ready=True)
    setup_script._setup_wake_word()
    save.assert_called_once_with(True)
    assert "verified and enabled" in capsys.readouterr().out


def test_setup_wake_word_not_ready(monkeypatch, capsys):
    save = _stub_wake_modules(monkeypatch, ok=True, ready=False)
    setup_script._setup_wake_word()
    save.assert_not_called()
    assert "msg-from-download" in capsys.readouterr().out


def test_setup_wake_word_exception_is_non_fatal(monkeypatch, capsys):
    ww = types.ModuleType("core.wake_word")

    def boom(logger=None):
        raise RuntimeError("no network")
    ww.ensure_models_downloaded = boom
    ww.is_ready = lambda: True
    monkeypatch.setitem(sys.modules, "core.wake_word", ww)
    setup_script._setup_wake_word()
    assert "could not be completed" in capsys.readouterr().out


def test_linux_audio_check_skipped_off_linux(monkeypatch):
    monkeypatch.setattr(setup_script, "OS", "Darwin")
    monkeypatch.setattr(setup_script, "sys", SimpleNamespace(platform="darwin"))
    run = MagicMock()
    monkeypatch.setattr(setup_script.subprocess, "run", run)
    setup_script._check_and_install_linux_audio_deps()
    run.assert_not_called()


def test_linux_audio_found_library(monkeypatch, capsys):
    import ctypes.util
    monkeypatch.setattr(setup_script, "OS", "Linux")
    monkeypatch.setattr(ctypes.util, "find_library", lambda name: "libportaudio.so.2")
    run = MagicMock()
    monkeypatch.setattr(setup_script.subprocess, "run", run)
    setup_script._check_and_install_linux_audio_deps()
    run.assert_not_called()
    assert "libportaudio.so.2" in capsys.readouterr().out


def test_linux_audio_installs_via_apt(monkeypatch):
    import ctypes.util
    import shutil
    monkeypatch.setattr(setup_script, "OS", "Linux")
    monkeypatch.setattr(ctypes.util, "find_library", lambda name: None)
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/apt-get" if name == "apt-get" else None)
    run = MagicMock()
    monkeypatch.setattr(setup_script.subprocess, "run", run)
    setup_script._check_and_install_linux_audio_deps()
    args = run.call_args.args[0]
    assert args[:4] == ["sudo", "apt-get", "install", "-y"]
    assert "portaudio19-dev" in args


def test_linux_audio_no_apt_prints_instructions(monkeypatch, capsys):
    import ctypes.util
    import shutil
    monkeypatch.setattr(setup_script, "OS", "Linux")
    monkeypatch.setattr(ctypes.util, "find_library", lambda name: None)
    monkeypatch.setattr(shutil, "which", lambda name: None)
    run = MagicMock()
    monkeypatch.setattr(setup_script.subprocess, "run", run)
    setup_script._check_and_install_linux_audio_deps()
    run.assert_not_called()
    assert "CRITICAL DEPENDENCY MISSING: PortAudio" in capsys.readouterr().out


@pytest.fixture
def main_env(monkeypatch):
    runs = []
    monkeypatch.setattr(setup_script, "_run", lambda label, args: runs.append(args))
    monkeypatch.setattr(setup_script, "_check_python", MagicMock())
    monkeypatch.setattr(setup_script, "_check_assets", MagicMock())
    monkeypatch.setattr(setup_script, "_setup_wake_word", MagicMock())
    linux = MagicMock()
    monkeypatch.setattr(setup_script, "_check_and_install_linux_audio_deps", linux)
    return runs, linux


def test_main_installs_requirements_and_playwright(monkeypatch, main_env, capsys):
    runs, linux = main_env
    monkeypatch.setattr(setup_script, "OS", "Darwin")
    setup_script.main()
    assert runs[0][1:] == ["-m", "pip", "install", "-r", "requirements.txt"]
    assert runs[1][1:] == ["-m", "playwright", "install", "chromium", "firefox"]
    setup_script._check_assets.assert_called_once()
    setup_script._setup_wake_word.assert_called_once()
    linux.assert_not_called()
    out = capsys.readouterr().out
    assert "macOS note" in out and "Setup complete" in out


def test_main_playwright_failure_is_not_fatal(monkeypatch, main_env, capsys):
    runs, linux = main_env

    def run(label, args):
        runs.append(args)
        if "playwright" in args:
            raise subprocess.CalledProcessError(1, args)
    monkeypatch.setattr(setup_script, "_run", run)
    monkeypatch.setattr(setup_script, "OS", "Linux")
    setup_script.main()
    out = capsys.readouterr().out
    assert "Playwright browsers were not installed" in out
    assert "Setup complete" in out
    linux.assert_called_once()


def test_main_pip_failure_propagates(monkeypatch, main_env):
    def run(label, args):
        raise subprocess.CalledProcessError(1, args)
    monkeypatch.setattr(setup_script, "_run", run)
    with pytest.raises(subprocess.CalledProcessError):
        setup_script.main()
