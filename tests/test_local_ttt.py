"""
tests/test_local_ttt.py — Unit tests for core/local_ttt.py (LocalTTSManager streaming TTS queue).

The underlying TTS player factory is mocked, so no audio engine is loaded.
"""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

import pytest

import core.local_ttt as local_ttt
from core.local_ttt import LocalTTSManager, create_local_tts_engine


@pytest.fixture
def player(monkeypatch):
    p = MagicMock()
    factory = MagicMock(return_value=p)
    monkeypatch.setattr(local_ttt, "create_tts_player", factory)
    return p, factory


def _drain(q):
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out


def test_init_passes_normalised_config(player):
    _, factory = player
    mgr = LocalTTSManager({"tts_engine": "EdgeTTS", "tts_voice": "v1", "tts_speed": "1.5"})
    assert mgr.engine_name == "edgetts"
    assert mgr.speed == 1.5
    factory.assert_called_once_with({"tts_engine": "edgetts", "tts_voice": "v1", "tts_speed": 1.5})


def test_init_falls_back_to_kokoro(monkeypatch):
    fallback = MagicMock()
    calls = []

    def factory(cfg):
        calls.append(cfg)
        if cfg["tts_engine"] != "kokoro":
            raise RuntimeError("engine missing")
        return fallback
    monkeypatch.setattr(local_ttt, "create_tts_player", factory)
    mgr = LocalTTSManager({"tts_engine": "elevenlabs"})
    assert mgr.engine_name == "kokoro"
    assert mgr.tts_engine is fallback
    assert calls[-1] == {"tts_engine": "kokoro", "tts_voice": "af_heart", "tts_speed": 1.0}


def test_init_kokoro_failure_reraises(monkeypatch):
    def factory(cfg):
        raise RuntimeError("no kokoro")
    monkeypatch.setattr(local_ttt, "create_tts_player", factory)
    with pytest.raises(RuntimeError, match="no kokoro"):
        LocalTTSManager({"tts_engine": "kokoro"})


def test_speak_text_strips_and_ignores_blank(player):
    mgr = create_local_tts_engine({})
    mgr.speak_text("   ")
    mgr.speak_text("")
    mgr.speak_text("  hello  ")
    assert _drain(mgr.text_queue) == ["hello"]


def test_speak_sentence_splits_on_boundaries_and_flush(player):
    mgr = LocalTTSManager({})
    mgr.speak_sentence("First one. Second")
    assert _drain(mgr.text_queue) == ["First one."]
    mgr.speak_sentence("part! Third")
    assert _drain(mgr.text_queue) == ["Second part!"]
    mgr.speak_sentence("")
    assert mgr.text_queue.empty()
    mgr.flush()
    assert _drain(mgr.text_queue) == ["Third"]
    mgr.flush()  # empty buffer → nothing queued
    assert mgr.text_queue.empty()


def test_speak_loop_speaks_queued_text_and_stop(player):
    p, _ = player
    spoken = threading.Event()
    p.speak.side_effect = lambda text: spoken.set()
    mgr = LocalTTSManager({})
    mgr.start()
    assert mgr.is_speaking
    first_thread = mgr.speak_thread
    mgr.start()  # second start is a no-op
    assert mgr.speak_thread is first_thread
    mgr.speak_text("Hello world")
    assert spoken.wait(2.0)
    mgr.stop()
    assert not mgr.is_speaking
    assert not first_thread.is_alive()
    p.speak.assert_called_with("Hello world")
    p.stop.assert_called_once()


def test_speak_loop_survives_engine_errors(player):
    p, _ = player
    seen = []
    done = threading.Event()

    def speak(text):
        seen.append(text)
        if text == "bad":
            raise RuntimeError("boom")
        done.set()
    p.speak.side_effect = speak
    mgr = LocalTTSManager({})
    mgr.start()
    mgr.speak_text("bad")
    mgr.speak_text("good")
    assert done.wait(2.0)
    mgr.stop()
    assert seen == ["bad", "good"]
