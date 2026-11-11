"""
tests/tools/test_benchmark_latency_pipeline.py — Tests for tools/benchmark_latency_pipeline.py.

PyQt6, the HUD canvas, wake-word, STT/TTS, intent router and speaker modules are all
replaced with lightweight stubs so the benchmark orchestration can run headless and
fast. The report is written under tmp_path instead of the repo's logs/ folder.
"""
from __future__ import annotations

import importlib
import sys
import types
from unittest.mock import MagicMock

import numpy as np
import pytest


def _module(monkeypatch, name, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    monkeypatch.setitem(sys.modules, name, mod)
    return mod


@pytest.fixture
def bench(monkeypatch, tmp_path):
    rec = types.SimpleNamespace(feeds=[], routes=[], tools=[], synth=[], paints=0,
                                verify=0, speaker_available=False, timer_stopped=False)

    class QApplication:
        _inst = None

        def __init__(self, argv):
            QApplication._inst = self

        @staticmethod
        def instance():
            return QApplication._inst

    class QImage:
        class Format:
            Format_ARGB32_Premultiplied = 6

        def __init__(self, w, h, fmt):
            self.size = (w, h)

    class QPainter:
        def __init__(self, img):
            self.ended = False

        def end(self):
            self.ended = True

    _module(monkeypatch, "PyQt6")
    _module(monkeypatch, "PyQt6.QtGui", QImage=QImage, QPainter=QPainter)
    _module(monkeypatch, "PyQt6.QtWidgets", QApplication=QApplication)

    class WakeWordDetector:
        def __init__(self, on_detect):
            self.on_detect = on_detect

        def feed(self, frame, timestamp):
            rec.feeds.append((frame.shape, frame.dtype))

    _module(monkeypatch, "core.audio.wakeword", WakeWordDetector=WakeWordDetector, AUDIO_BUFFER_SIZE=1280)
    _module(monkeypatch, "core.speech.stt", InstrumentedSTT=MagicMock())

    class IntentRouter:
        def route(self, cmd):
            rec.routes.append(cmd)

    _module(monkeypatch, "core.intents.router", IntentRouter=IntentRouter)

    async def execute_bounded_tool(name, coro):
        rec.tools.append((name, await coro))

    _module(monkeypatch, "core.tools.runner", execute_bounded_tool=execute_bounded_tool)

    class InstrumentedTTS:
        def __init__(self, synthesizer):
            self.synthesizer = synthesizer

        def synthesize_or_cache(self, text):
            audio, sr = self.synthesizer(text)
            rec.synth.append((text, audio.shape, sr))

    _module(monkeypatch, "core.speech.tts", InstrumentedTTS=InstrumentedTTS, TTS_CACHE={})

    class HudCanvas:
        def __init__(self, face_path, assistant_name):
            self.args = (face_path, assistant_name)
            self._tmr = MagicMock()
            self._tmr.stop.side_effect = lambda: setattr(rec, "timer_stopped", True)

        def resize(self, w, h):
            self.size = (w, h)

        def paintEvent(self, event):
            rec.paints += 1

    _module(monkeypatch, "ui", HudCanvas=HudCanvas, FRAME_TIME_BUDGET_MS=16)

    class Extractor:
        def is_available(self):
            return rec.speaker_available

    class SpeakerVerifier:
        def verify(self, candidate):
            rec.verify += 1
            rec.candidate = candidate

    _module(monkeypatch, "core.speaker.types", WakeCandidateAudio=lambda **kw: types.SimpleNamespace(**kw))
    _module(monkeypatch, "core.speaker.verifier", SpeakerVerifier=SpeakerVerifier)
    _module(monkeypatch, "core.speaker.extractor", CampplusOnnxExtractor=Extractor)

    monkeypatch.delitem(sys.modules, "tools.benchmark_latency_pipeline", raising=False)
    mod = importlib.import_module("tools.benchmark_latency_pipeline")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    yield mod, rec, tmp_path
    sys.modules.pop("tools.benchmark_latency_pipeline", None)


def test_import_creates_qapplication(bench):
    mod, _, _ = bench
    assert mod._APP is sys.modules["PyQt6.QtWidgets"].QApplication.instance()


def test_run_benchmark_exercises_each_stage_and_writes_report(bench, capsys):
    mod, rec, root = bench
    mod.run_benchmark()

    assert len(rec.feeds) == 50
    assert rec.feeds[0] == ((1280,), np.dtype(np.int16))
    assert len(rec.routes) == 300
    assert rec.routes[:6] == ["what time is it", "today's date", "mute", "unmute",
                              "search netflix for Interstellar", "close tab"]
    assert rec.tools == [("sample_tool", "Command completed")] * 20
    assert len(rec.synth) == 60
    assert {t for t, _, _ in rec.synth} == {"Done, sir.", "Checking, sir."}
    assert rec.synth[0][1:] == ((1600,), 16000)
    assert rec.paints == 100
    assert rec.timer_stopped
    assert rec.verify == 0  # extractor unavailable → speaker stage skipped

    report = root / "logs" / "perf" / "latency-benchmark-report.txt"
    assert report.exists()
    assert "cumulative" in report.read_text(encoding="utf-8")
    out = capsys.readouterr().out
    assert "Profiling Complete" in out
    assert str(report) in out


def test_speaker_verification_stage_runs_when_available(bench):
    mod, rec, _ = bench
    rec.speaker_available = True
    mod.run_benchmark()
    assert rec.verify == 10
    cand = rec.candidate
    assert cand.sample_rate == 16000
    assert cand.audio_pcm.shape == (24000,) and cand.audio_pcm.dtype == np.int16
    assert cand.source == "acoustic"


def test_speaker_stage_failure_is_reported_not_raised(bench, capsys):
    mod, rec, _ = bench

    class Broken:
        def is_available(self):
            raise RuntimeError("onnx missing")
    sys.modules["core.speaker.extractor"].CampplusOnnxExtractor = Broken
    mod.run_benchmark()
    assert "Speaker verification benchmark skipped (onnx missing)" in capsys.readouterr().out
    assert rec.paints == 100
