"""Shared stubs for tests/tools: fake sounddevice, scipy.io.wavfile and openWakeWord modules."""
from __future__ import annotations

import sys
import threading
import types
from unittest.mock import MagicMock

import numpy as np
import pytest


@pytest.fixture
def fake_wavfile(monkeypatch):
    """Install a minimal scipy.io.wavfile stub that round-trips int16 PCM through real files."""
    wav = types.ModuleType("scipy.io.wavfile")
    writes = []

    def write(path, rate, data):
        arr = np.asarray(data, dtype=np.int16)
        writes.append((str(path), rate, arr.copy()))
        with open(path, "wb") as fh:
            fh.write(arr.tobytes())

    def read(path):
        with open(path, "rb") as fh:
            return 16000, np.frombuffer(fh.read(), dtype=np.int16).copy()

    wav.write = write
    wav.read = read
    wav.writes = writes
    io_mod = types.ModuleType("scipy.io")
    io_mod.wavfile = wav
    scipy_mod = types.ModuleType("scipy")
    scipy_mod.io = io_mod
    monkeypatch.setitem(sys.modules, "scipy", scipy_mod)
    monkeypatch.setitem(sys.modules, "scipy.io", io_mod)
    monkeypatch.setitem(sys.modules, "scipy.io.wavfile", wav)
    return wav


@pytest.fixture
def fake_sounddevice(monkeypatch):
    """Install a sounddevice stub whose rec() returns a ramp of int16 samples."""
    sd = types.ModuleType("sounddevice")
    sd.rec = MagicMock(side_effect=lambda n, samplerate, channels, dtype:
                       np.arange(n, dtype=np.int16).reshape(n, channels))
    sd.wait = MagicMock()
    sd.RawInputStream = MagicMock()
    monkeypatch.setitem(sys.modules, "sounddevice", sd)
    return sd


class FakeOWWModel:
    """openwakeword.model.Model stand-in returning (1, 16, 96) feature frames."""

    instances: list = []

    def __init__(self, wakeword_models=None, inference_framework=None):
        self.wakeword_models = wakeword_models
        self.inference_framework = inference_framework
        self.models = {"alfred": object()}
        self.model_inputs = {"alfred": 16}
        self.preprocessor = MagicMock()
        self.preprocessor.get_features.return_value = np.zeros((1, 16, 96), dtype=np.float32)
        self.predict_calls = 0
        self.resets = 0
        FakeOWWModel.instances.append(self)

    def predict(self, chunk):
        self.predict_calls += 1
        return {"alfred": 0.0}

    def reset(self):
        self.resets += 1


@pytest.fixture
def fake_oww(monkeypatch):
    """Stub core.wake_word helpers and openwakeword packages used by the training scripts."""
    FakeOWWModel.instances.clear()
    ww = types.ModuleType("core.wake_word")
    ww._ensure_openwakeword = MagicMock()
    ww._MODEL_INIT_LOCK = threading.Lock()
    monkeypatch.setitem(sys.modules, "core.wake_word", ww)

    oww_pkg = types.ModuleType("openwakeword")
    model_mod = types.ModuleType("openwakeword.model")
    model_mod.Model = FakeOWWModel
    cvm = types.ModuleType("openwakeword.custom_verifier_model")
    cvm.train_verifier_model = MagicMock(return_value={"clf": "trained"})
    oww_pkg.model = model_mod
    oww_pkg.custom_verifier_model = cvm
    monkeypatch.setitem(sys.modules, "openwakeword", oww_pkg)
    monkeypatch.setitem(sys.modules, "openwakeword.model", model_mod)
    monkeypatch.setitem(sys.modules, "openwakeword.custom_verifier_model", cvm)
    return types.SimpleNamespace(wake_word=ww, Model=FakeOWWModel, cvm=cvm)
