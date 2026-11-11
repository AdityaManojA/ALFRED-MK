"""
tests/tools/test_wake_model_live_check.py — Tests for tools/wake_model_live_check.py (live mic wake test).

The microphone stream, openWakeWord model, Whisper verifier and time.sleep are faked;
the infinite listen loop is ended by raising KeyboardInterrupt from the fake sleep.
"""
from __future__ import annotations

import importlib
import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

LOUD = np.full(1280, 1000, dtype=np.int16).tobytes()
SILENT = np.zeros(1280, dtype=np.int16).tobytes()


@pytest.fixture
def live(monkeypatch, fake_sounddevice):
    monkeypatch.delitem(sys.modules, "tools.wake_model_live_check", raising=False)
    mod = importlib.import_module("tools.wake_model_live_check")

    state = SimpleNamespace(feed=b"", scores=[], whisper=None, phrase_ok=False,
                            sleeps=[], max_sleeps=50, model_kwargs=None)

    class Stream:
        def __init__(self, **kwargs):
            state.stream_kwargs = kwargs
            self.cb = kwargs["callback"]

        def __enter__(self):
            self.cb(state.feed, len(state.feed) // 2, None, None)
            return self

        def __exit__(self, *exc):
            return False
    fake_sounddevice.RawInputStream = Stream
    monkeypatch.setattr(mod, "sd", fake_sounddevice)

    class Model:
        def __init__(self, wakeword_models, inference_framework):
            state.model_kwargs = (wakeword_models, inference_framework)
            self._scores = list(state.scores)

        def predict(self, arr):
            assert arr.dtype == np.int16 and arr.shape == (1280,)
            return self._scores.pop(0) if self._scores else {"alfred_v2": 0.0}
    model_mod = types.ModuleType("openwakeword.model")
    model_mod.Model = Model
    monkeypatch.setitem(sys.modules, "openwakeword", types.ModuleType("openwakeword"))
    monkeypatch.setitem(sys.modules, "openwakeword.model", model_mod)

    ww = types.ModuleType("core.wake_word")
    ww.get_wake_model_paths = lambda: ["/m/alfred.onnx", "/m/hey_alfred.onnx"]
    ww._is_alfred_wake_phrase = lambda text: state.phrase_ok and "alfred" in text.lower()
    ww._get_whisper_verifier = lambda: state.whisper
    monkeypatch.setitem(sys.modules, "core.wake_word", ww)

    def sleep(secs):
        state.sleeps.append(secs)
        if secs > 1 or len(state.sleeps) >= state.max_sleeps:
            raise KeyboardInterrupt
    monkeypatch.setattr(mod, "time", SimpleNamespace(sleep=sleep, monotonic=lambda: len(state.sleeps)))
    monkeypatch.setattr(sys, "argv", ["wake_model_live_check.py"])
    yield mod, state
    sys.modules.pop("tools.wake_model_live_check", None)


def test_constants(live):
    mod, _ = live
    assert mod.SAMPLE_RATE == 16000
    assert mod.STEP_SIZE == 1280
    assert 0 < mod.THRESHOLD < 1


def test_missing_model_argument_exits(live, monkeypatch, tmp_path, capsys):
    mod, _ = live
    monkeypatch.setattr(sys, "argv", ["x", "--model", str(tmp_path / "nope.onnx")])
    with pytest.raises(SystemExit) as ei:
        mod.main()
    assert ei.value.code == 1
    assert "Model not found" in capsys.readouterr().out


def test_explicit_model_is_used(live, monkeypatch, tmp_path):
    mod, state = live
    model = tmp_path / "custom.onnx"
    model.write_bytes(b"x")
    monkeypatch.setattr(sys, "argv", ["x", "--model", str(model)])
    state.max_sleeps = 1
    mod.main()
    assert state.model_kwargs == ([str(model)], "onnx")


def test_acoustic_trigger_detected(live, capsys):
    mod, state = live
    state.feed = SILENT * 2
    state.scores = [{"alfred_v2": 0.01, "other": 0.9}, {"alfred_v2": 0.5}]
    mod.main()
    out = capsys.readouterr().out
    assert state.model_kwargs == (["/m/alfred.onnx", "/m/hey_alfred.onnx"], "onnx")
    assert state.stream_kwargs["samplerate"] == 16000
    assert out.count("[WAKE DETECTED]") == 1
    assert "Acoustic Trigger via [alfred_v2]! Score=0.500" in out
    assert "Stopped." in out
    assert 1.2 in state.sleeps


def test_non_alfred_scores_fall_back_to_max(live, capsys):
    mod, state = live
    state.feed = SILENT
    state.scores = [{"other_model": 0.9}]
    mod.main()
    assert "Acoustic Trigger via [other_model]! Score=0.900" in capsys.readouterr().out


def test_speech_burst_verified_by_whisper(live, capsys):
    mod, state = live
    state.feed = LOUD * 3 + SILENT * 3
    state.phrase_ok = True
    seen_audio = []

    class Whisper:
        def transcribe(self, audio, **kw):
            seen_audio.append(audio)
            return [SimpleNamespace(text=" Hey"), SimpleNamespace(text="Alfred ")], None
    state.whisper = Whisper()
    mod.main()
    out = capsys.readouterr().out
    assert "Speech Verifier Match! Spoke: 'Hey Alfred'" in out
    audio = seen_audio[0]
    assert audio.dtype == np.float32 and audio.shape == (6 * 1280,)
    assert abs(audio.max() - 1000 / 32768.0) < 1e-6


def test_speech_burst_rejected_phrase_is_silent(live, capsys):
    mod, state = live
    state.feed = LOUD * 3 + SILENT * 3
    state.phrase_ok = False
    state.whisper = MagicMock()
    state.whisper.transcribe.return_value = ([SimpleNamespace(text="hello there")], None)
    state.max_sleeps = 10
    mod.main()
    out = capsys.readouterr().out
    state.whisper.transcribe.assert_called_once()
    assert "WAKE DETECTED" not in out
    assert "Wake Score=0.000" in out


def test_short_burst_skips_whisper(live):
    mod, state = live
    state.feed = LOUD + SILENT * 3  # 4 frames = 0.32 s < 0.35 s minimum
    state.whisper = MagicMock()
    state.max_sleeps = 8
    mod.main()
    state.whisper.transcribe.assert_not_called()
