"""
tests/tools/test_train_personal_verifier.py — Tests for tools/train_personal_verifier.py (legacy verifier).

openWakeWord, the microphone and scipy are stubbed; samples and the pickle go to tmp_path.
"""
from __future__ import annotations

import pickle
from types import SimpleNamespace
import sys
from unittest.mock import MagicMock

import numpy as np
import pytest

import tools.train_personal_verifier as tpv
from tests.tools.conftest import FakeOWWModel


@pytest.fixture
def paths(tmp_path, monkeypatch):
    pos, neg, models = tmp_path / "positive", tmp_path / "negative", tmp_path / "models"
    monkeypatch.setattr(tpv, "POS_DIR", pos)
    monkeypatch.setattr(tpv, "NEG_DIR", neg)
    monkeypatch.setattr(tpv, "MODELS_DIR", models)
    monkeypatch.setattr(tpv, "MODEL_PATH", models / "alfred.onnx")
    monkeypatch.setattr(tpv, "VERIFIER_PATH", models / "alfred_verifier.pkl")
    return pos, neg, models


def _write_pcm(path, samples):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(np.asarray(samples, dtype=np.int16).tobytes())


def test_record_clip(fake_sounddevice):
    out = tpv.record_clip(0.25)
    fake_sounddevice.rec.assert_called_once_with(4000, samplerate=16000, channels=1, dtype="int16")
    assert out.shape == (4000,)


def test_record_interactive_positive_filenames(paths, fake_wavfile, monkeypatch):
    pos, _, _ = paths
    monkeypatch.setattr("builtins.input", lambda msg="": "")
    monkeypatch.setattr(tpv, "record_clip", lambda d: np.zeros(3, dtype=np.int16))
    monkeypatch.setattr(tpv, "time", SimpleNamespace(time=lambda: 7))
    tpv.record_interactive_positive("Alfred Pennyworth", "Hey Alfred", num_clips=1)
    assert [p.name for p in pos.iterdir()] == ["alfred_pennyworth_hey_alfred_7_01.wav"]


def test_record_interactive_negative_filenames(paths, fake_wavfile, monkeypatch):
    _, neg, _ = paths
    monkeypatch.setattr("builtins.input", lambda msg="": "")
    monkeypatch.setattr(tpv, "record_clip", lambda d: np.zeros(3, dtype=np.int16))
    monkeypatch.setattr(tpv, "time", SimpleNamespace(time=lambda: 7))
    tpv.record_interactive_negative(num_clips=2)
    assert sorted(p.name for p in neg.iterdir()) == ["neg_7_01.wav", "neg_7_02.wav"]


def test_extract_positive_features_keeps_loud_chunks(tmp_path, fake_wavfile):
    wav = tmp_path / "loud.wav"
    # 1280 silent + 2*1280 loud + tail → 3 full steps, 2 of them loud
    _write_pcm(wav, np.concatenate([np.zeros(1280), np.full(2560, 1000), np.zeros(100)]))
    model = FakeOWWModel()
    feats = tpv.extract_positive_features(str(wav), model, "alfred")
    assert feats.shape == (2, 16, 96)
    assert model.predict_calls == 3
    assert model.resets == 1


def test_extract_positive_features_falls_back_to_loudest(tmp_path, fake_wavfile):
    wav = tmp_path / "quiet.wav"
    _write_pcm(wav, np.concatenate([np.full(1280, 10), np.full(1280, 50), np.full(1280, 30),
                                    np.full(1280, 20), np.zeros(10)]))
    model = FakeOWWModel()
    feats = tpv.extract_positive_features(str(wav), model, "alfred")
    assert feats.shape == (3, 16, 96)  # top-3 RMS windows re-fed
    assert model.resets == 2


def test_extract_features_wrong_shape_returns_empty(tmp_path, fake_wavfile):
    wav = tmp_path / "x.wav"
    _write_pcm(wav, np.full(4000, 1000))
    model = FakeOWWModel()
    model.preprocessor.get_features.return_value = np.zeros((1, 8, 96))
    assert tpv.extract_positive_features(str(wav), model, "alfred").shape == (0, 16, 96)
    assert tpv.extract_negative_features(str(wav), model, "alfred").shape == (0, 16, 96)


def test_extract_negative_features_every_step(tmp_path, fake_wavfile):
    wav = tmp_path / "n.wav"
    _write_pcm(wav, np.zeros(1280 * 4 + 1))
    feats = tpv.extract_negative_features(str(wav), FakeOWWModel(), "alfred")
    assert feats.shape == (4, 16, 96)


def test_train_verifier_requires_positives(paths, capsys):
    assert tpv.train_verifier() is False
    assert "No positive WAV files" in capsys.readouterr().out


def test_train_verifier_full_pipeline(paths, fake_wavfile, fake_oww, capsys):
    pos, neg, models = paths
    _write_pcm(pos / "bruce_hey_alfred_1_01.wav", np.full(1280 * 3 + 5, 1000))
    _write_pcm(pos / "dick_hey_alfred_1_01.wav", np.full(1280 * 2 + 5, 1000))

    assert tpv.train_verifier() is True

    # <5 negatives → 15 synthetic noise clips were generated
    assert len(list(neg.glob("synthetic_noise_*.wav"))) == 15
    model = fake_oww.Model.instances[0]
    assert model.wakeword_models == [str(tpv.MODEL_PATH)]
    X, y = fake_oww.cvm.train_verifier_model.call_args.args
    n_pos = 3 + 2
    assert int(y.sum()) == n_pos
    assert X.shape[0] == y.shape[0] and X.shape[1:] == (16, 96)
    with open(tpv.VERIFIER_PATH, "rb") as fh:
        assert pickle.load(fh) == {"clf": "trained"}
    out = capsys.readouterr().out
    assert "Bruce" in out and "Dick" in out


def test_train_verifier_no_extractable_positive_features(paths, fake_wavfile, fake_oww):
    pos, neg, _ = paths
    _write_pcm(pos / "a_x.wav", np.zeros(100))  # shorter than one step
    for i in range(5):
        _write_pcm(neg / f"n{i}.wav", np.zeros(2000))
    assert tpv.train_verifier() is False
    assert not tpv.VERIFIER_PATH.exists()
    assert not list(neg.glob("synthetic_noise_*"))


def test_test_live_requires_verifier(paths, capsys):
    tpv.test_live()
    assert "Verifier model not found" in capsys.readouterr().out


@pytest.mark.parametrize("argv,name,kwargs", [
    (["--record-positive", "--speaker", "a", "--clips", "2"], "record_interactive_positive",
     {"speaker_name": "a", "phrase": "Hey Alfred", "num_clips": 2}),
    (["--record-negative"], "record_interactive_negative", {"num_clips": 10}),
    (["--train"], "train_verifier", {}),
    (["--test"], "test_live", {}),
])
def test_main_dispatch(monkeypatch, argv, name, kwargs):
    names = ("record_interactive_positive", "record_interactive_negative", "train_verifier", "test_live")
    mocks = {n: MagicMock() for n in names}
    for n, m in mocks.items():
        monkeypatch.setattr(tpv, n, m)
    monkeypatch.setattr(sys, "argv", ["train_personal_verifier.py", *argv])
    tpv.main()
    mocks[name].assert_called_once_with(**kwargs)
    assert sum(m.called for m in mocks.values()) == 1
