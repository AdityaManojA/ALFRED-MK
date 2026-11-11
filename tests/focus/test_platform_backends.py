"""OS-agnostic tests for the focus platform readers (win / mac / linux).

All OS calls (Win32 user32, psutil, osascript, xdotool, xprop, hyprctl) are faked
so these run identically on Windows, macOS and Linux CI.
"""
from __future__ import annotations

import ctypes
import importlib
import json
import sys
import types
from types import SimpleNamespace

import pytest

from core.sentry.focus.reader import hash_host

OWN_PID = 4242


# ── helpers ──────────────────────────────────────────────────────────────────

def _run_router(table):
    """Fake subprocess.run: map argv[0..1] tuple prefix -> SimpleNamespace result."""
    calls = []

    def run(cmd, **kwargs):
        calls.append(list(cmd))
        for prefix, result in table.items():
            if tuple(cmd[: len(prefix)]) == prefix:
                if isinstance(result, BaseException):
                    raise result
                return result
        return SimpleNamespace(returncode=1, stdout="")

    run.calls = calls
    return run


def ok(stdout):
    return SimpleNamespace(returncode=0, stdout=stdout)


# ── macOS ─────────────────────────────────────────────────────────────────────

from core.sentry.focus.platform import mac  # noqa: E402
from core.sentry.focus.platform.mac import MacPlatformReader  # noqa: E402


def test_mac_unknown_when_query_fails(monkeypatch):
    monkeypatch.setattr(mac.subprocess, "run", _run_router({("osascript",): RuntimeError("no")}))
    assert MacPlatformReader().get_frontmost_surface().capability == "UNKNOWN"


def test_mac_home_base_detected(monkeypatch):
    monkeypatch.setattr(mac.subprocess, "run", _run_router({("osascript",): ok("com.alfred.hud, Alfred\n")}))
    s = MacPlatformReader().get_frontmost_surface()
    assert s.is_home_base and s.is_self and s.spoken_label == "ALFRED"


def test_mac_chrome_reads_tab_url(monkeypatch):
    responses = iter([ok("com.google.Chrome, Google Chrome"), ok("https://www.youtube.com/watch?v=1\n")])
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        return next(responses)

    monkeypatch.setattr(mac.subprocess, "run", run)
    s = MacPlatformReader().get_frontmost_surface()
    assert s.is_browser and s.capability == "FULL"
    assert s.spoken_label == "Google Chrome"
    assert s.tab_host_hash == hash_host("www.youtube.com")
    assert calls[1] == ["osascript", "-e", 'tell application "Google Chrome" to get URL of active tab of front window']


def test_mac_firefox_is_browser_but_app_only(monkeypatch):
    run = _run_router({("osascript",): ok("org.mozilla.firefox, Firefox")})
    monkeypatch.setattr(mac.subprocess, "run", run)
    s = MacPlatformReader().get_frontmost_surface()
    assert s.is_browser and s.capability == "APP_ONLY" and s.tab_host_hash == ""
    assert len(run.calls) == 1  # no URL query for Firefox


def test_mac_plain_app_uses_name_and_single_part(monkeypatch):
    monkeypatch.setattr(mac.subprocess, "run", _run_router({("osascript",): ok("com.apple.Notes, Notes")}))
    s = MacPlatformReader().get_frontmost_surface()
    assert (s.app_id, s.spoken_label, s.is_browser) == ("com.apple.Notes", "Notes", False)
    monkeypatch.setattr(mac.subprocess, "run", _run_router({("osascript",): ok("com.x.Solo")}))
    assert MacPlatformReader()._get_frontmost_app() == ("com.x.Solo", "com.x.Solo")


# ── Linux ─────────────────────────────────────────────────────────────────────

from core.sentry.focus.platform import linux  # noqa: E402
from core.sentry.focus.platform.linux import LinuxPlatformReader  # noqa: E402


@pytest.fixture
def x11(monkeypatch):
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setattr(linux.os, "getpid", lambda: OWN_PID)


def test_linux_x11_no_active_window(x11, monkeypatch):
    monkeypatch.setattr(linux.subprocess, "run", _run_router({}))
    assert LinuxPlatformReader().get_frontmost_surface().capability == "UNKNOWN"


def test_linux_x11_own_pid_is_home_base(x11, monkeypatch):
    monkeypatch.setattr(linux.subprocess, "run", _run_router({
        ("xdotool", "getactivewindow"): ok("77\n"),
        ("xdotool", "getwindowpid"): ok(f"{OWN_PID}\n"),
    }))
    s = LinuxPlatformReader().get_frontmost_surface()
    assert s.is_home_base and s.app_id == "alfred"


def test_linux_x11_browser_with_domain_title(x11, monkeypatch):
    run = _run_router({
        ("xdotool", "getactivewindow"): ok("77\n"),
        ("xdotool", "getwindowpid"): ok("100\n"),
        ("xdotool", "getwindowname"): ok("Issues · github.com - Google Chrome\n"),
        ("xprop",): ok('WM_CLASS(STRING) = "google-chrome", "Google-chrome"\n'),
    })
    monkeypatch.setattr(linux.subprocess, "run", run)
    s = LinuxPlatformReader().get_frontmost_surface()
    assert s.app_id == "google-chrome" and s.spoken_label == "Chrome" and s.is_browser
    assert s.tab_host_hash == hash_host("github.com") and s.capability == "FULL"
    assert ["xprop", "-id", "77", "WM_CLASS"] in run.calls


def test_linux_x11_non_browser_app_only(x11, monkeypatch):
    monkeypatch.setattr(linux.subprocess, "run", _run_router({
        ("xdotool", "getactivewindow"): ok("5"),
        ("xdotool", "getwindowpid"): ok("not-a-pid"),
        ("xdotool", "getwindowname"): ok("notes.com draft"),
        ("xprop",): ok('WM_CLASS(STRING) = "Gedit", "gedit"'),
    }))
    s = LinuxPlatformReader().get_frontmost_surface()
    assert (s.app_id, s.spoken_label, s.capability, s.tab_host_hash) == ("gedit", "Gedit", "APP_ONLY", "")


def test_linux_x11_exception_is_unknown(x11, monkeypatch):
    monkeypatch.setattr(linux.subprocess, "run", _run_router({("xdotool",): FileNotFoundError("xdotool")}))
    assert LinuxPlatformReader().get_frontmost_surface().capability == "UNKNOWN"


@pytest.fixture
def wayland(monkeypatch):
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setattr(linux.os, "getpid", lambda: OWN_PID)


def test_linux_wayland_hyprctl_browser(wayland, monkeypatch):
    payload = json.dumps({"class": "Firefox", "pid": 9, "title": "r/python - reddit.com — Mozilla Firefox"})
    monkeypatch.setattr(linux.subprocess, "run", _run_router({("hyprctl", "activewindow", "-j"): ok(payload)}))
    s = LinuxPlatformReader().get_frontmost_surface()
    assert s.app_id == "firefox" and s.is_browser and s.capability == "FULL"
    assert s.tab_host_hash == hash_host("reddit.com")


def test_linux_wayland_self_and_failure(wayland, monkeypatch):
    payload = json.dumps({"class": "alfred", "pid": OWN_PID, "title": ""})
    monkeypatch.setattr(linux.subprocess, "run", _run_router({("hyprctl",): ok(payload)}))
    assert LinuxPlatformReader().get_frontmost_surface().is_home_base
    monkeypatch.setattr(linux.subprocess, "run", _run_router({("hyprctl",): FileNotFoundError()}))
    assert LinuxPlatformReader().get_frontmost_surface().capability == "APP_ONLY"


# ── Windows ───────────────────────────────────────────────────────────────────

class FakeUser32:
    """Minimal user32 stand-in driven by dict tables."""

    def __init__(self, foreground=0, pids=None, titles=None, z_order=(), minimized=(), hidden=()):
        self.foreground = foreground
        self.pids = pids or {}
        self.titles = titles or {}
        self.z_order = list(z_order)
        self.minimized = set(minimized)
        self.hidden = set(hidden)

    def GetForegroundWindow(self):
        return self.foreground

    def GetWindowThreadProcessId(self, hwnd, ref):
        ref._obj.value = self.pids.get(hwnd, 0)

    def GetWindowTextLengthW(self, hwnd):
        return len(self.titles.get(hwnd, ""))

    def GetWindowTextW(self, hwnd, buf, n):
        buf.value = self.titles.get(hwnd, "")[: n - 1]

    def IsWindowVisible(self, hwnd):
        return hwnd not in self.hidden

    def IsIconic(self, hwnd):
        return hwnd in self.minimized

    def EnumWindows(self, cb, _lparam):
        for hwnd in self.z_order:
            if not cb(hwnd, 0):
                break


@pytest.fixture
def win(monkeypatch):
    """Import core.sentry.focus.platform.win with Win32 APIs stubbed."""
    try:
        import ctypes.wintypes  # noqa: F401
    except Exception:  # pragma: no cover - very old non-Windows Pythons
        stub = types.SimpleNamespace(DWORD=ctypes.c_ulong)
        monkeypatch.setitem(sys.modules, "ctypes.wintypes", stub)
        monkeypatch.setattr(ctypes, "wintypes", stub, raising=False)
    if not hasattr(ctypes, "windll"):
        monkeypatch.setattr(ctypes, "windll", SimpleNamespace(user32=FakeUser32()), raising=False)
    monkeypatch.setattr(ctypes, "WINFUNCTYPE", lambda *a: (lambda fn: fn), raising=False)
    sys.modules.pop("core.sentry.focus.platform.win", None)
    module = importlib.import_module("core.sentry.focus.platform.win")
    yield module
    sys.modules.pop("core.sentry.focus.platform.win", None)


def _procs(monkeypatch, module, names):
    def Process(pid):
        if pid not in names:
            raise module.psutil.NoSuchProcess(pid)
        return SimpleNamespace(name=lambda: names[pid])

    monkeypatch.setattr(module.psutil, "Process", Process)


def _reader(module, monkeypatch, user32):
    monkeypatch.setattr(module, "user32", user32)
    monkeypatch.setattr(module.os, "getpid", lambda: OWN_PID)
    return module.WinPlatformReader()


def test_win_no_foreground_is_unknown(win, monkeypatch):
    r = _reader(win, monkeypatch, FakeUser32(foreground=0))
    assert r.get_frontmost_surface().capability == "UNKNOWN"


def test_win_own_process_is_home_base(win, monkeypatch):
    r = _reader(win, monkeypatch, FakeUser32(foreground=1, pids={1: OWN_PID}))
    s = r.get_frontmost_surface()
    assert s.is_home_base and s.spoken_label == "ALFRED"


def test_win_browser_url_in_title(win, monkeypatch):
    _procs(monkeypatch, win, {10: "Chrome.EXE"})
    r = _reader(win, monkeypatch, FakeUser32(foreground=1, pids={1: 10}, titles={1: "https://news.ycombinator.com/ - Chrome"}))
    s = r.get_frontmost_surface()
    assert s.app_id == "chrome.exe" and s.spoken_label == "Chrome" and s.is_browser
    assert s.capability == "FULL" and s.tab_host_hash == hash_host("news.ycombinator.com")
    assert s.raw_title.startswith("https://")


def test_win_non_browser_label_and_missing_process(win, monkeypatch):
    _procs(monkeypatch, win, {10: "Spotify.exe"})
    r = _reader(win, monkeypatch, FakeUser32(foreground=1, pids={1: 10, 2: 99}, titles={1: "Song"}))
    s = r.get_frontmost_surface()
    assert (s.app_id, s.spoken_label, s.capability, s.is_browser) == ("spotify.exe", "Spotify", "APP_ONLY", False)
    win.user32.foreground = 2
    s2 = r.get_frontmost_surface()
    assert s2.app_id == "unknown" and s2.capability == "APP_ONLY"


def test_win_extract_host_heuristics(win, monkeypatch):
    r = _reader(win, monkeypatch, FakeUser32())
    monkeypatch.setattr(r, "_read_uia_address_bar", lambda hwnd: "")
    assert r._extract_browser_host(1, "chrome.exe", "Docs - Example.org - Chrome") == "Example.org"
    assert r._extract_browser_host(1, "chrome.exe", "Cats - YouTube") == "youtube.com"
    assert r._extract_browser_host(1, "chrome.exe", "Xbox Store") == ""  # " x " needs surrounding spaces
    assert r._extract_browser_host(1, "chrome.exe", "Home / X / Feed") == "x.com"
    assert r._extract_browser_host(1, "chrome.exe", "Twitter home") == "x.com"
    assert r._extract_browser_host(1, "chrome.exe", "New Tab") == ""
    monkeypatch.setattr(r, "_read_uia_address_bar", lambda hwnd: "intranet.local")
    assert r._extract_browser_host(1, "chrome.exe", "New Tab") == "intranet.local"


def test_win_uia_address_bar(win, monkeypatch):
    r = _reader(win, monkeypatch, FakeUser32())
    edit = SimpleNamespace(Exists=lambda *a: True, GetValuePattern=lambda: SimpleNamespace(Value="https://mail.google.com/u/0"))
    ctrl = SimpleNamespace(Exists=lambda *a: True, EditControl=lambda searchDepth: edit)
    monkeypatch.setitem(sys.modules, "uiautomation", SimpleNamespace(ControlFromHandle=lambda h: ctrl))
    assert r._read_uia_address_bar(5) == "mail.google.com"
    monkeypatch.setitem(sys.modules, "uiautomation", SimpleNamespace(ControlFromHandle=lambda h: 1 / 0))
    assert r._read_uia_address_bar(5) == ""


def test_win_card_trap_finds_top_visible_browser(win, monkeypatch):
    _procs(monkeypatch, win, {20: "code.exe", 30: "msedge.exe", 40: "firefox.exe"})
    u = FakeUser32(
        foreground=1,
        pids={1: OWN_PID, 2: OWN_PID, 3: 30, 4: 20, 5: 30, 6: 40},
        titles={6: "Firefox page", 5: "Edge page"},
        z_order=[2, 3, 4, 5, 6],
        minimized={3},
    )
    r = _reader(win, monkeypatch, u)
    assert r._find_top_browser_window() == 5  # 2=self, 3=minimized, 4=not a browser
    s = r.get_frontmost_surface(from_card=True)
    assert s.app_id == "msedge.exe" and s.spoken_label == "Edge" and not s.is_home_base


def test_win_card_trap_falls_back_to_foreground(win, monkeypatch):
    u = FakeUser32(foreground=1, pids={1: OWN_PID}, z_order=[])
    r = _reader(win, monkeypatch, u)
    s = r.get_frontmost_surface(from_card=True)
    # Own window reached via card is not treated as home base.
    assert not s.is_home_base and s.app_id == "unknown"
