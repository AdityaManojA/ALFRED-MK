"""Behavioural tests for core.media.suppress (base, win, mac, linux backends).

winsdk (SMTC) and pycaw are replaced with in-memory fakes so these run on any OS.
"""
from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest

from core.media import suppress
from core.media.suppress import win as win_mod
from core.media.suppress.base import NullSuppressor, Suppressor
from core.media.suppress.linux import LinuxSuppressor
from core.media.suppress.mac import MacSuppressor
from core.media.suppress.win import WindowsSuppressor, _WindowsHandle


# ── base / placeholders ──────────────────────────────────────────────────────

def test_suppressor_is_abstract():
    with pytest.raises(TypeError):
        Suppressor()  # type: ignore[abstract]


@pytest.mark.parametrize("cls", [NullSuppressor, LinuxSuppressor, MacSuppressor])
def test_null_and_placeholder_backends_do_nothing(cls):
    s = cls()
    assert s.enumerate_players() == []
    assert s.pause(object()) is False
    assert s.resume(object()) is False
    assert s.is_playing(object()) is False


@pytest.mark.parametrize(
    "system, cls",
    [("Windows", WindowsSuppressor), ("Darwin", MacSuppressor), ("Linux", LinuxSuppressor), ("Plan9", NullSuppressor)],
)
def test_get_suppressor_selects_backend(monkeypatch, system, cls):
    monkeypatch.setattr(suppress.platform, "system", lambda: system)
    assert type(suppress.get_suppressor()) is cls


# ── Windows: SMTC ────────────────────────────────────────────────────────────

PLAYING, PAUSED = "PLAYING", "PAUSED"


class FakeSession:
    def __init__(self, app_id, status, pause_ok=True, play_ok=True):
        self.source_app_user_model_id = app_id
        self._status = status
        self.pause_ok, self.play_ok = pause_ok, play_ok
        self.paused = self.played = 0

    def get_playback_info(self):
        return SimpleNamespace(playback_status=self._status)

    async def try_pause_async(self):
        self.paused += 1
        return self.pause_ok

    async def try_play_async(self):
        self.played += 1
        return self.play_ok


@pytest.fixture
def smtc(monkeypatch):
    sessions = []

    class Manager:
        @staticmethod
        async def request_async():
            return SimpleNamespace(get_sessions=lambda: list(sessions))

    control = types.ModuleType("winsdk.windows.media.control")
    control.GlobalSystemMediaTransportControlsSessionManager = Manager
    control.GlobalSystemMediaTransportControlsSessionPlaybackStatus = SimpleNamespace(PLAYING=PLAYING)
    for name in ("winsdk", "winsdk.windows", "winsdk.windows.media"):
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    monkeypatch.setitem(sys.modules, "winsdk.windows.media.control", control)
    monkeypatch.setattr(win_mod.sys, "executable", "/opt/py/python.exe")
    return sessions


def test_smtc_lists_only_playing_external_sessions(smtc, monkeypatch):
    spotify, paused_app, own = FakeSession("Spotify.exe", PLAYING), FakeSession("vlc", PAUSED), FakeSession("C:/x/PYTHON.EXE", PLAYING)
    smtc.extend([spotify, paused_app, own])
    monkeypatch.setattr(WindowsSuppressor, "_pycaw_sessions", lambda self: pytest.fail("pycaw should not be used"))
    handles = WindowsSuppressor().enumerate_players()
    assert [h.session for h in handles] == [spotify]
    assert handles[0].kind == "smtc"


def test_smtc_pause_resume_and_is_playing(smtc):
    session = FakeSession("chrome", PLAYING, pause_ok=True, play_ok=False)
    h = _WindowsHandle(session, "smtc")
    s = WindowsSuppressor()
    assert s.pause(h) is True and session.paused == 1
    assert s.resume(h) is False and session.played == 1
    assert s.is_playing(h) is True


def test_smtc_failure_falls_back_to_pycaw(monkeypatch):
    monkeypatch.setitem(sys.modules, "winsdk", None)  # import fails
    marker = [_WindowsHandle(object(), "pycaw")]
    monkeypatch.setattr(WindowsSuppressor, "_pycaw_sessions", lambda self: marker)
    assert WindowsSuppressor().enumerate_players() is marker


# ── Windows: pycaw ───────────────────────────────────────────────────────────

class FakeVolume:
    def __init__(self, level):
        self.level = level
        self.calls = []

    def GetMasterVolume(self):
        return self.level

    def SetMasterVolume(self, value, ctx):
        self.calls.append((value, ctx))
        self.level = value


def test_pycaw_sessions_skip_self_and_processless(monkeypatch):
    monkeypatch.setattr(win_mod.os, "getpid", lambda: 7)
    ext = SimpleNamespace(Process=SimpleNamespace(pid=99))
    sessions = [SimpleNamespace(Process=None), SimpleNamespace(Process=SimpleNamespace(pid=7)), ext]
    pycaw = types.ModuleType("pycaw.pycaw")
    pycaw.AudioUtilities = SimpleNamespace(GetAllSessions=lambda: sessions)
    monkeypatch.setitem(sys.modules, "pycaw", types.ModuleType("pycaw"))
    monkeypatch.setitem(sys.modules, "pycaw.pycaw", pycaw)
    handles = WindowsSuppressor()._pycaw_sessions()
    assert [(h.session, h.kind) for h in handles] == [(ext, "pycaw")]


def test_pycaw_mute_and_restore_roundtrip():
    vol = FakeVolume(0.65)
    h = _WindowsHandle(SimpleNamespace(SimpleAudioVolume=vol), "pycaw")
    s = WindowsSuppressor()
    assert s.is_playing(h) is True
    assert s.pause(h) is True
    assert vol.level == 0.0 and h.original_volume == 0.65 and h.muted_by_alfred
    assert s.is_playing(h) is False
    assert s.resume(h) is True
    assert vol.level == 0.65 and not h.muted_by_alfred
    # Second resume: nothing ALFRED muted, so no-op.
    assert s.resume(h) is False
    assert vol.calls == [(0.0, None), (0.65, None)]


def test_pycaw_resume_without_prior_pause_is_noop():
    vol = FakeVolume(0.3)
    h = _WindowsHandle(SimpleNamespace(SimpleAudioVolume=vol), "pycaw")
    assert WindowsSuppressor().resume(h) is False
    assert vol.calls == []


def test_pause_error_returns_false():
    h = _WindowsHandle(SimpleNamespace(), "pycaw")  # no SimpleAudioVolume attribute
    assert WindowsSuppressor().pause(h) is False
    assert h.muted_by_alfred is False


def test_foreign_handles_rejected():
    s = WindowsSuppressor()
    for fn in (s.pause, s.resume, s.is_playing):
        assert fn("not-a-handle") is False
