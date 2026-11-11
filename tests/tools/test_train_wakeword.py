"""
tests/tools/test_train_wakeword.py — Tests for tools/train_wakeword.py (ONNX model verify/download CLI).

onnxruntime and urllib downloads are stubbed; the model path is redirected to tmp_path.
"""
from __future__ import annotations

import hashlib
import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import tools.train_wakeword as tw


@pytest.fixture
def model_dir(tmp_path, monkeypatch):
    models = tmp_path / "models"
    monkeypatch.setattr(tw, "MODELS_DIR", models)
    monkeypatch.setattr(tw, "DEFAULT_MODEL_PATH", models / "alfred.onnx")
    return models


def _stub_ort(monkeypatch, fail=False):
    ort = types.ModuleType("onnxruntime")
    created = []

    class Session:
        def __init__(self, path, providers=None):
            if fail:
                raise RuntimeError("invalid protobuf")
            created.append((path, providers))

        def get_inputs(self):
            return [SimpleNamespace(name="input")]

        def get_outputs(self):
            return [SimpleNamespace(name="score")]
    ort.InferenceSession = Session
    monkeypatch.setitem(sys.modules, "onnxruntime", ort)
    return created


def test_constants():
    assert tw.TARGET_PHRASES == ["hey alfred", "alfred"]
    assert tw.OFFICIAL_MODEL_URL.endswith("alfred.onnx")
    assert len(tw.EXPECTED_SHA256) == 64


def test_verify_missing_model(model_dir):
    assert tw.verify_model() is False


def test_verify_success_logs_hash(model_dir, monkeypatch, caplog):
    model_dir.mkdir()
    tw.DEFAULT_MODEL_PATH.write_bytes(b"onnx-bytes")
    created = _stub_ort(monkeypatch)
    with caplog.at_level("INFO", logger="train_wakeword"):
        assert tw.verify_model() is True
    assert created == [(str(tw.DEFAULT_MODEL_PATH), ["CPUExecutionProvider"])]
    assert hashlib.sha256(b"onnx-bytes").hexdigest() in caplog.text
    assert "['input']" in caplog.text


def test_verify_runtime_failure(model_dir, monkeypatch):
    model_dir.mkdir()
    tw.DEFAULT_MODEL_PATH.write_bytes(b"junk")
    _stub_ort(monkeypatch, fail=True)
    assert tw.verify_model() is False


def test_download_skips_existing_without_force(model_dir, monkeypatch):
    model_dir.mkdir()
    tw.DEFAULT_MODEL_PATH.write_bytes(b"x")
    import urllib.request
    retrieve = MagicMock()
    monkeypatch.setattr(urllib.request, "urlretrieve", retrieve)
    assert tw.download_model() is True
    retrieve.assert_not_called()


def test_download_force_fetches_and_verifies(model_dir, monkeypatch):
    model_dir.mkdir()
    tw.DEFAULT_MODEL_PATH.write_bytes(b"old")
    import urllib.request
    calls = []

    def retrieve(url, dest):
        calls.append(url)
        dest.write_bytes(b"new")
    monkeypatch.setattr(urllib.request, "urlretrieve", retrieve)
    monkeypatch.setattr(tw, "verify_model", lambda: True)
    assert tw.download_model(force=True) is True
    assert calls == [tw.OFFICIAL_MODEL_URL]
    assert tw.DEFAULT_MODEL_PATH.read_bytes() == b"new"


def test_download_creates_dir_and_handles_failure(model_dir, monkeypatch):
    import urllib.request

    def retrieve(url, dest):
        raise OSError("offline")
    monkeypatch.setattr(urllib.request, "urlretrieve", retrieve)
    assert tw.download_model() is False
    assert model_dir.is_dir()


@pytest.mark.parametrize("argv,fn,result,code", [
    (["--download"], "download_model", True, 0),
    (["--download", "--force"], "download_model", False, 1),
    (["--verify"], "verify_model", True, 0),
    ([], "verify_model", False, 1),
])
def test_main_exit_codes(monkeypatch, argv, fn, result, code):
    mock = MagicMock(return_value=result)
    monkeypatch.setattr(tw, fn, mock)
    monkeypatch.setattr(sys, "argv", ["train_wakeword.py", *argv])
    with pytest.raises(SystemExit) as ei:
        tw.main()
    assert ei.value.code == code
    if fn == "download_model":
        mock.assert_called_once_with(force="--force" in argv)


def test_main_force_only_does_nothing(monkeypatch):
    dl, vf = MagicMock(), MagicMock()
    monkeypatch.setattr(tw, "download_model", dl)
    monkeypatch.setattr(tw, "verify_model", vf)
    monkeypatch.setattr(sys, "argv", ["train_wakeword.py", "--force"])
    tw.main()
    dl.assert_not_called()
    vf.assert_not_called()
