"""
tests/test_installer.py — Unit tests for core/installer.py dependency auto-installer.

subprocess.run and module discovery are mocked; nothing is ever installed.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import core.installer as installer


@pytest.fixture
def fake_run(monkeypatch):
    calls = []

    def run(args, capture_output=False, **_kw):
        calls.append(list(args))
        return SimpleNamespace(returncode=0, stderr=b"")
    monkeypatch.setattr(installer.subprocess, "run", run)
    return calls


def _pip_targets(calls):
    return [c[4] for c in calls if c[1:4] == ["-m", "pip", "install"]]


def test_available_uses_find_spec(monkeypatch):
    seen = []
    monkeypatch.setattr(installer.importlib.util, "find_spec",
                        lambda name: seen.append(name) or (object() if name == "yes" else None))
    assert installer._available("yes") is True
    assert installer._available("no") is False
    assert seen == ["yes", "no"]


def test_pip_success_logs_command(fake_run):
    logs = []
    assert installer._pip("foo", logs.append) is True
    assert fake_run[0][1:5] == ["-m", "pip", "install", "foo"]
    assert "--quiet" in fake_run[0]
    assert logs == ["SYS: pip install foo …"]


def test_pip_failure_logs_truncated_stderr(monkeypatch):
    monkeypatch.setattr(
        installer.subprocess, "run",
        lambda *a, **k: SimpleNamespace(returncode=1, stderr=("x" * 500).encode()),
    )
    logs = []
    assert installer._pip("bar", logs.append) is False
    assert logs[-1].startswith("ERR: bar install failed")
    assert logs[-1].count("x") == 140


def test_nothing_missing_installs_nothing(monkeypatch, fake_run):
    monkeypatch.setattr(installer, "_available", lambda m: True)
    logs = []
    installer.install_for_config({}, logs.append)
    assert fake_run == []
    assert logs == ["SYS: All dependencies already installed ✓"]


def test_installs_only_missing_with_engine_extras(monkeypatch, fake_run):
    monkeypatch.setattr(installer.platform, "system", lambda: "Linux")
    missing = {"numpy", "faster_whisper", "edge_tts"}
    monkeypatch.setattr(installer, "_available", lambda m: m not in missing)
    logs = []
    installer.install_for_config({"stt_engine": "Whisper", "tts_engine": "EDGETTS"}, logs.append)
    assert _pip_targets(fake_run) == ["numpy", "faster-whisper", "edge-tts"]
    assert any("Installing 3 package(s)" in l for l in logs)
    assert logs[-1] == "SYS: All dependencies ready ✓"


def test_kokoro_soundfile_is_deduplicated(monkeypatch, fake_run):
    monkeypatch.setattr(installer.platform, "system", lambda: "Linux")
    monkeypatch.setattr(installer, "_available", lambda m: m not in {"soundfile", "kokoro"})
    installer.install_for_config({"tts_engine": "kokoro", "stt_engine": "vosk"})
    targets = _pip_targets(fake_run)
    assert targets.count("soundfile") == 1
    assert "kokoro>=0.9" in targets


def test_windows_only_packages_added_on_windows(monkeypatch, fake_run):
    monkeypatch.setattr(installer.platform, "system", lambda: "Windows")
    monkeypatch.setattr(installer, "_available", lambda m: m not in {"pycaw", "comtypes"})
    installer.install_for_config({})
    assert _pip_targets(fake_run) == ["comtypes", "pycaw"]


def test_windows_packages_skipped_elsewhere(monkeypatch, fake_run):
    monkeypatch.setattr(installer.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(installer, "_available", lambda m: m not in {"pycaw", "comtypes"})
    logs = []
    installer.install_for_config({}, logs.append)
    assert fake_run == []
    assert "already installed" in logs[0]


def test_unknown_engines_add_nothing(monkeypatch, fake_run):
    monkeypatch.setattr(installer.platform, "system", lambda: "Linux")
    monkeypatch.setattr(installer, "_available", lambda m: m not in {"faster_whisper", "edge_tts", "vosk"})
    installer.install_for_config({"stt_engine": "nope", "tts_engine": "elevenlabs"})
    assert fake_run == []


def test_playwright_installed_with_chromium(monkeypatch, fake_run):
    monkeypatch.setattr(installer.platform, "system", lambda: "Linux")
    monkeypatch.setattr(installer, "_available", lambda m: m not in {"numpy", "playwright"})
    logs = []
    installer.install_for_config({}, logs.append)
    assert _pip_targets(fake_run) == ["numpy", "playwright"]
    assert fake_run[-1][1:] == ["-m", "playwright", "install", "chromium"]
    assert "SYS: Playwright browser ready." in logs
