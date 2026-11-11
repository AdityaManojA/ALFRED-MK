"""
tests/tools/test_record_training_samples.py — Tests for tools/record_training_samples.py.

Microphone, scipy and torch are stubbed; all data/zip paths point into tmp_path.
"""
from __future__ import annotations

import sys
import types
import zipfile
from unittest.mock import MagicMock

import numpy as np
import pytest

import tools.record_training_samples as rts


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    pos, neg = tmp_path / "positive", tmp_path / "negative"
    monkeypatch.setattr(rts, "POS_DIR", pos)
    monkeypatch.setattr(rts, "NEG_DIR", neg)
    monkeypatch.setattr(rts, "ZIP_PATH", tmp_path / "alfred_training_data.zip")
    monkeypatch.setattr(rts, "MODELS_DIR", tmp_path / "models")
    return pos, neg


def test_record_clip_uses_16k_mono_int16(fake_sounddevice):
    audio = rts.record_clip(0.5)
    fake_sounddevice.rec.assert_called_once_with(8000, samplerate=16000, channels=1, dtype="int16")
    fake_sounddevice.wait.assert_called_once()
    assert audio.shape == (8000,)
    assert audio.dtype == np.int16


def test_record_positive_saves_named_clips(dirs, fake_wavfile, monkeypatch):
    pos, _ = dirs
    prompts = []
    monkeypatch.setattr("builtins.input", lambda msg="": prompts.append(msg) or "")
    monkeypatch.setattr(rts, "record_clip", lambda d: np.ones(10, dtype=np.int16))
    monkeypatch.setattr(rts, "time", types.SimpleNamespace(time=lambda: 1700000000))
    rts.record_positive(" Bruce Wayne ", phrase="Hey Alfred", num_clips=2)
    names = sorted(p.name for p in pos.iterdir())
    assert names == ["bruce_wayne_hey_alfred_1700000000_01.wav",
                     "bruce_wayne_hey_alfred_1700000000_02.wav"]
    assert all(rate == 16000 for _, rate, _ in fake_wavfile.writes)
    assert len(prompts) == 2 and "[1/2]" in prompts[0]


def test_record_negative_saves_clips(dirs, fake_wavfile, monkeypatch):
    _, neg = dirs
    monkeypatch.setattr("builtins.input", lambda msg="": "")
    monkeypatch.setattr(rts, "record_clip", lambda d: np.zeros(4, dtype=np.int16))
    monkeypatch.setattr(rts, "time", types.SimpleNamespace(time=lambda: 42))
    rts.record_negative(num_clips=3)
    assert sorted(p.name for p in neg.iterdir()) == ["neg_42_01.wav", "neg_42_02.wav", "neg_42_03.wav"]


def test_package_zip_requires_positives(dirs, capsys):
    rts.package_zip()
    assert "No positive WAV files" in capsys.readouterr().out
    assert not rts.ZIP_PATH.exists()


def test_package_zip_contents(dirs):
    pos, neg = dirs
    pos.mkdir()
    neg.mkdir()
    (pos / "a.wav").write_bytes(b"A")
    (pos / "b.wav").write_bytes(b"B")
    (pos / "notes.txt").write_text("skip")
    (neg / "n.wav").write_bytes(b"N")
    rts.package_zip()
    with zipfile.ZipFile(rts.ZIP_PATH) as zf:
        assert sorted(zf.namelist()) == ["negative/n.wav", "positive/a.wav", "positive/b.wav"]
        assert zf.read("positive/b.wav") == b"B"


def test_train_local_without_positives_returns_early(dirs, fake_wavfile, monkeypatch, capsys):
    torch = types.ModuleType("torch")
    for name in ("torch", "torch.nn", "torch.optim", "torch.utils", "torch.utils.data"):
        monkeypatch.setitem(sys.modules, name, MagicMock() if name != "torch" else torch)
    torch.nn = sys.modules["torch.nn"]
    torch.optim = sys.modules["torch.optim"]
    torch.utils = sys.modules["torch.utils"]
    rts.train_local()
    assert "No positive audio files found" in capsys.readouterr().out
    assert not dirs[1].exists()  # no synthetic negatives were generated


@pytest.mark.parametrize("argv,expected", [
    (["--record-positive"], ("record_positive", {"speaker": "user", "phrase": "Hey Alfred", "num_clips": 15})),
    (["--speaker", "dick", "--clips", "3"], ("record_positive", {"speaker": "dick", "phrase": "Hey Alfred", "num_clips": 3})),
    (["--negative", "--clips", "4"], ("record_negative", {"num_clips": 4})),
    (["--zip"], ("package_zip", {})),
    (["--train-local"], ("train_local", {})),
])
def test_main_dispatch(monkeypatch, argv, expected):
    mocks = {n: MagicMock() for n in ("record_positive", "record_negative", "package_zip", "train_local")}
    for n, m in mocks.items():
        monkeypatch.setattr(rts, n, m)
    monkeypatch.setattr(sys, "argv", ["record_training_samples.py", *argv])
    rts.main()
    name, kwargs = expected
    mocks[name].assert_called_once_with(**kwargs)
    assert sum(m.called for m in mocks.values()) == 1


def test_main_without_args_prints_help(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["record_training_samples.py"])
    for n in ("record_positive", "record_negative", "package_zip", "train_local"):
        monkeypatch.setattr(rts, n, MagicMock(side_effect=AssertionError(n)))
    rts.main()
    assert "usage:" in capsys.readouterr().out
