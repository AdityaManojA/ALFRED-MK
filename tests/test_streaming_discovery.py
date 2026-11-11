"""Behavioural tests for core.streaming.discovery (host surface discovery).

OS detection, winreg, shutil.which and subprocess are all faked.
"""
from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest

from core.streaming import discovery
from core.streaming.provider import CapabilityClass, SurfaceKind


def test_unknown_os_finds_nothing(monkeypatch):
    monkeypatch.setattr(discovery, "_OS", "Plan9")
    assert discovery.discover_installed_browsers() == []
    assert discovery.discover_netflix_native_app() is None


def test_linux_first_available_binary_per_browser(monkeypatch):
    present = {"chromium-browser": "/usr/bin/chromium-browser", "chromium": "/usr/bin/chromium", "firefox": "/usr/bin/firefox"}
    monkeypatch.setattr(discovery, "_OS", "Linux")
    monkeypatch.setattr(discovery.shutil, "which", lambda b: present.get(b))
    surfaces = discovery.discover_installed_browsers()
    assert [(s.id, s.executable_path) for s in surfaces] == [
        ("chrome", "/usr/bin/chromium-browser"),
        ("firefox", "/usr/bin/firefox"),
    ]
    assert all(s.kind is SurfaceKind.BROWSER and s.capability is CapabilityClass.FULL for s in surfaces)
    assert surfaces[0].display_name == "Google Chrome"


def test_mac_only_existing_app_bundles(monkeypatch, tmp_path):
    (tmp_path / "Safari.app").mkdir()
    apps = [("chrome", str(tmp_path / "Chrome.app"), "Google Chrome"), ("safari", str(tmp_path / "Safari.app"), "Safari")]
    monkeypatch.setattr(discovery, "_OS", "Darwin")
    monkeypatch.setattr(discovery, "_MAC_BROWSER_APPS", apps)
    surfaces = discovery.discover_installed_browsers()
    assert [(s.id, s.display_name) for s in surfaces] == [("safari", "Safari")]


@pytest.fixture
def fake_winreg(monkeypatch):
    registry = {}
    mod = types.ModuleType("winreg")
    mod.HKEY_LOCAL_MACHINE, mod.HKEY_CURRENT_USER = "HKLM", "HKCU"

    def OpenKey(hive, path):
        if (hive, path) not in registry:
            raise FileNotFoundError(path)
        return (hive, path)

    mod.OpenKey = OpenKey
    mod.QueryValueEx = lambda key, name: (registry[key], 1)
    mod.CloseKey = lambda key: None
    monkeypatch.setitem(sys.modules, "winreg", mod)
    monkeypatch.setattr(discovery, "_OS", "Windows")
    return registry


def test_windows_registry_paths_verified_on_disk(fake_winreg, tmp_path):
    chrome = tmp_path / "chrome.exe"
    chrome.write_text("")
    edge = tmp_path / "msedge.exe"
    edge.write_text("")
    paths = discovery._WIN_BROWSER_PATHS
    fake_winreg[("HKCU", paths["chrome"][0])] = f'"{chrome}" --flag'  # quoted with args
    fake_winreg[("HKLM", paths["msedge"][0])] = str(edge)
    fake_winreg[("HKLM", paths["brave"][0])] = str(tmp_path / "missing.exe")  # stale registry entry
    surfaces = discovery.discover_installed_browsers()
    by_id = {s.id: s for s in surfaces}
    assert set(by_id) == {"chrome", "msedge"}
    assert by_id["chrome"].executable_path == str(chrome)
    assert by_id["chrome"].browser_channel == "chrome"
    assert by_id["msedge"].display_name == "Microsoft Edge"


def test_windows_hklm_wins_over_hkcu(fake_winreg, tmp_path):
    a, b = tmp_path / "a.exe", tmp_path / "b.exe"
    a.write_text("")
    b.write_text("")
    key = discovery._WIN_BROWSER_PATHS["firefox"][0]
    fake_winreg[("HKLM", key)] = str(a)
    fake_winreg[("HKCU", key)] = str(b)
    surfaces = discovery.discover_installed_browsers()
    assert [(s.id, s.executable_path, s.browser_channel) for s in surfaces] == [("firefox", str(a), None)]


def test_netflix_windows_appx_found(monkeypatch):
    calls = []
    monkeypatch.setattr(discovery, "_OS", "Windows")
    monkeypatch.setattr(
        discovery.subprocess, "run",
        lambda cmd, **kw: calls.append(cmd) or SimpleNamespace(stdout="4DF9E0F8.Netflix_mcm4njqhnhss8\r\n"),
    )
    surface = discovery.discover_netflix_native_app()
    assert surface.executable_path == "4DF9E0F8.Netflix_mcm4njqhnhss8!Netflix.App"
    assert surface.extra_metadata == {"aumid": surface.executable_path}
    assert surface.kind is SurfaceKind.NATIVE_APP and surface.capability is CapabilityClass.LAUNCH_ONLY
    assert calls[0][0] == "powershell" and "Get-AppxPackage 4DF9E0F8.Netflix" in calls[0][-1]


@pytest.mark.parametrize("result", [SimpleNamespace(stdout=""), SimpleNamespace(stdout="SomethingElse"), OSError("no ps")])
def test_netflix_windows_absent_or_error(monkeypatch, result):
    def run(cmd, **kw):
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr(discovery, "_OS", "Windows")
    monkeypatch.setattr(discovery.subprocess, "run", run)
    assert discovery.discover_netflix_native_app() is None


def test_netflix_not_probed_off_windows(monkeypatch):
    monkeypatch.setattr(discovery, "_OS", "Linux")
    monkeypatch.setattr(discovery.subprocess, "run", lambda *a, **k: pytest.fail("should not run"))
    assert discovery.discover_netflix_native_app() is None


def test_crunchyroll_never_fabricated():
    assert discovery.discover_crunchyroll_native_app() is None
