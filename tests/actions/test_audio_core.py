"""Behavioural tests for actions.audio_core."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import actions.audio_core as audio_core_mod
from actions.audio_core import audio_core


@pytest.fixture(autouse=True)
def _reset_debounce():
    audio_core_mod._last_action = ""
    audio_core_mod._last_call_time = 0.0
    yield
    audio_core_mod._last_action = ""
    audio_core_mod._last_call_time = 0.0


class _BgPlayer:
    def __init__(self, playing=True, volume=0.25):
        self.calls = []
        self._playing = playing
        self._volume = volume

    def pause_core(self):
        self.calls.append("pause_core")

    def resume_core(self):
        self.calls.append("resume_core")

    def toggle_play(self):
        self.calls.append("toggle_play")
        self._playing = not self._playing

    def is_playing(self):
        return self._playing

    def set_base_volume(self, v):
        self.calls.append(("set_base_volume", v))

    def base_volume(self):
        return self._volume

    def next_track(self):
        self.calls.append("next_track")

    def prev_track(self):
        self.calls.append("prev_track")


def test_no_player_reports_inaccessible():
    assert "not accessible" in audio_core({"action": "pause"}, player=None)


def test_pause_prefers_player_method():
    player = SimpleNamespace(pause_audio_core=MagicMock())
    assert audio_core({"action": "stop"}, player=player) == "Audio Core paused, sir."
    player.pause_audio_core.assert_called_once()


def test_pause_falls_back_to_bg_player():
    bg = _BgPlayer()
    player = SimpleNamespace(_bg_music=bg)
    assert audio_core({"action": "mute"}, player=player) == "Audio Core paused, sir."
    assert bg.calls == ["pause_core"]


def test_pause_without_any_backend_fails_gracefully():
    player = SimpleNamespace()
    assert audio_core({"action": "pause"}, player=player) == "Could not pause the Audio Core, sir."


def test_resume_via_bg_player():
    bg = _BgPlayer()
    out = audio_core({"action": "PLAY"}, player=SimpleNamespace(_bg_music=bg))
    assert "resumed" in out
    assert bg.calls == ["resume_core"]


def test_toggle_reports_new_state():
    bg = _BgPlayer(playing=True)
    out = audio_core({"action": "toggle"}, player=SimpleNamespace(_bg_music=bg))
    assert out == "Audio Core paused, sir."


@pytest.mark.parametrize(
    "raw, expected",
    [(150, 100), (-5, 0), ("40", 40), ("loud", 10), (None, 10)],
)
def test_set_volume_clamps_and_defaults(raw, expected):
    player = SimpleNamespace(set_audio_core_volume=MagicMock())
    params = {"action": "set_volume"}
    if raw is not None:
        params["volume_percent"] = raw
    out = audio_core(params, player=player)
    player.set_audio_core_volume.assert_called_once_with(expected)
    assert out == f"Audio Core volume set to {expected}%, sir."


def test_set_volume_on_bg_player_uses_fraction():
    bg = _BgPlayer()
    audio_core({"action": "volume", "volume_percent": 30}, player=SimpleNamespace(_bg_music=bg))
    assert bg.calls == [("set_base_volume", 0.3)]


def test_next_and_prev_track():
    bg = _BgPlayer()
    player = SimpleNamespace(_bg_music=bg)
    assert "next track" in audio_core({"action": "next"}, player=player)
    assert "previous track" in audio_core({"action": "prev"}, player=player)
    assert bg.calls == ["next_track", "prev_track"]


def test_status_from_player_method():
    player = SimpleNamespace(
        get_audio_core_status=lambda: {"is_playing": False, "volume": 35, "track": "Derezzed"}
    )
    out = audio_core({"action": "status"}, player=player)
    assert out == "Audio Core is currently paused. Active track: Derezzed at 35% base volume, sir."


def test_status_from_bg_player():
    bg = _BgPlayer(playing=True, volume=0.42)
    out = audio_core({"action": "info"}, player=SimpleNamespace(_bg_music=bg))
    assert out == "Audio Core is currently playing at 42% volume, sir."


def test_unknown_action_lists_options():
    out = audio_core({"action": "dance"}, player=SimpleNamespace())
    assert out.startswith("Unknown Audio Core action 'dance'")


def test_backend_exception_is_reported():
    def boom():
        raise RuntimeError("device lost")

    out = audio_core({"action": "pause"}, player=SimpleNamespace(pause_audio_core=boom))
    assert "encountered an issue" in out and "device lost" in out


def test_duplicate_action_within_window_is_debounced():
    player = SimpleNamespace(pause_audio_core=MagicMock())
    audio_core({"action": "pause"}, player=player)
    out = audio_core({"action": "pause"}, player=player)
    assert "already executed" in out
    player.pause_audio_core.assert_called_once()


def test_write_log_is_called_with_volume_suffix():
    player = SimpleNamespace(write_log=MagicMock(), set_audio_core_volume=MagicMock())
    audio_core({"action": "set_volume", "volume_percent": 20}, player=player)
    player.write_log.assert_called_once_with("[AudioCore] Action: SET_VOLUME (20%)")
