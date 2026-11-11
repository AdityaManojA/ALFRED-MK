"""Behavioural tests for core.stt (WhisperSTT / VoskSTT wrappers).

faster_whisper, torch and vosk are replaced with fakes; no model is loaded or downloaded.
"""
from __future__ import annotations

import json
import sys
import types
from types import SimpleNamespace

import numpy as np
import pytest

from core.stt import VoskSTT, WhisperSTT


@pytest.fixture
def whisper(monkeypatch):
    state = {"errors": [], "inits": [], "transcribe_calls": [], "segments": [], "cuda": False}

    class FakeModel:
        def __init__(self, name, device, compute_type):
            state["inits"].append((name, device, compute_type))
            if state["errors"]:
                raise state["errors"].pop(0)

        def transcribe(self, audio, **kwargs):
            state["transcribe_calls"].append(kwargs)
            if isinstance(state["segments"], BaseException):
                raise state["segments"]
            return (SimpleNamespace(text=t) for t in state["segments"]), {"lang": "en"}

    fw = types.ModuleType("faster_whisper")
    fw.WhisperModel = FakeModel
    monkeypatch.setitem(sys.modules, "faster_whisper", fw)
    torch = types.ModuleType("torch")
    torch.cuda = SimpleNamespace(is_available=lambda: state["cuda"])
    monkeypatch.setitem(sys.modules, "torch", torch)
    return state


def test_whisper_cpu_int8_when_no_cuda(whisper):
    WhisperSTT("tiny")
    assert whisper["inits"] == [("tiny", "cpu", "int8")]


def test_whisper_cuda_float16(whisper):
    whisper["cuda"] = True
    WhisperSTT("small")
    assert whisper["inits"] == [("small", "cuda", "float16")]


def test_whisper_without_torch_defaults_to_cpu(whisper, monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", None)
    WhisperSTT()
    assert whisper["inits"] == [("base", "cpu", "int8")]


@pytest.mark.parametrize("language, expected", [(None, None), ("auto", None), (" AUTO ", None), (" EN ", "en"), ("", None)])
def test_whisper_language_normalised(whisper, language, expected):
    assert WhisperSTT(language=language)._language == expected


def test_whisper_offline_cache_miss_clears_flags_and_retries(whisper, monkeypatch):
    for var in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
        monkeypatch.setenv(var, "1")
    whisper["errors"] = [OSError("LocalEntryNotFoundError: model not in cache")]
    WhisperSTT("base")
    assert len(whisper["inits"]) == 2
    import os

    assert not any(v in os.environ for v in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"))


def test_whisper_download_failure_is_explained(whisper):
    whisper["errors"] = [OSError("offline mode"), ConnectionError("no route to host")]
    with pytest.raises(RuntimeError, match="model download failed") as info:
        WhisperSTT("base")
    assert isinstance(info.value.__cause__, ConnectionError)


def test_whisper_other_errors_propagate_without_retry(whisper):
    whisper["errors"] = [ValueError("invalid compute type")]
    with pytest.raises(ValueError):
        WhisperSTT()
    assert len(whisper["inits"]) == 1


def test_whisper_transcribe_joins_segments_with_fast_settings(whisper):
    whisper["segments"] = [" Hello", " there. "]
    stt = WhisperSTT(language="en")
    assert stt.transcribe(np.zeros(16000, dtype=np.float32)) == "Hello  there."
    kw = whisper["transcribe_calls"][0]
    assert kw["language"] == "en" and kw["beam_size"] == 1 and kw["best_of"] == 1
    assert kw["vad_filter"] is True and kw["condition_on_previous_text"] is False


def test_whisper_transcribe_error_reraised(whisper):
    whisper["segments"] = RuntimeError("decoder crashed")
    with pytest.raises(RuntimeError, match="decoder crashed"):
        WhisperSTT().transcribe(np.zeros(10, dtype=np.float32))


# ── Vosk ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def vosk(monkeypatch):
    state = {"models": [], "accept": [], "rate": None}

    class Model:
        def __init__(self, path=None, lang=None):
            state["models"].append((path, lang))

    class KaldiRecognizer:
        def __init__(self, model, rate):
            state["rate"] = rate

        def AcceptWaveform(self, data):
            return state["accept"].pop(0)

        def Result(self):
            return json.dumps({"text": "turn on the lights"})

        def PartialResult(self):
            return json.dumps({"partial": "turn on"})

    mod = types.ModuleType("vosk")
    mod.Model, mod.KaldiRecognizer = Model, KaldiRecognizer
    monkeypatch.setitem(sys.modules, "vosk", mod)
    return state


def test_vosk_model_selection(vosk):
    VoskSTT(model_path="/models/en")
    VoskSTT(language=" DE ")
    VoskSTT(language="auto")
    VoskSTT(language="")
    assert vosk["models"] == [("/models/en", None), (None, "de"), (None, "en-us"), (None, "en-us")]
    assert vosk["rate"] == 16000


def test_vosk_partial_then_final(vosk):
    vosk["accept"] = [False, True]
    stt = VoskSTT()
    assert stt.process_chunk(b"\x00\x00") == ("turn on", False)
    assert stt.process_chunk(b"\x00\x00") == ("turn on the lights", True)
