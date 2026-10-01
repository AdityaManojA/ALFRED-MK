"""
tools/benchmark_latency_pipeline.py — Comprehensive end-to-end latency profiling script.
Profiles the full voice/HUD pipeline: wake-word → STT → intent routing → tool → TTS → HUD paint.
"""

from __future__ import annotations

import cProfile
import io
import os
import pstats
import sys
import time
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QApplication

_APP = QApplication.instance() or QApplication([])

from core.audio.wakeword import WakeWordDetector, AUDIO_BUFFER_SIZE
from core.speech.stt import InstrumentedSTT
from core.intents.router import IntentRouter
from core.tools.runner import execute_bounded_tool
from core.speech.tts import InstrumentedTTS, TTS_CACHE
from ui import HudCanvas, FRAME_TIME_BUDGET_MS


def run_benchmark():
    print("=== Running ALFRED-MK-VIII Latency Profiling Benchmark ===")
    profile = cProfile.Profile()
    profile.enable()

    # 1. Wake word gate
    detector = WakeWordDetector(on_detect=lambda: None)
    dummy_frame = np.zeros(AUDIO_BUFFER_SIZE, dtype=np.int16)
    t_feed = time.perf_counter()
    for _ in range(50):
        detector.feed(dummy_frame, timestamp=t_feed)

    # 2. Intent router
    router = IntentRouter()
    commands = [
        "what time is it",
        "today's date",
        "mute",
        "unmute",
        "search netflix for Interstellar",
        "close tab",
    ]
    for _ in range(50):
        for cmd in commands:
            router.route(cmd)

    # 3. Tool execution (fast path)
    async def sample_tool():
        return "Command completed"

    import asyncio
    for _ in range(20):
        asyncio.run(execute_bounded_tool("sample_tool", sample_tool()))

    # 4. TTS caching & synthesis
    tts = InstrumentedTTS(synthesizer=lambda text: (np.zeros(1600, dtype=np.float32), 16000))
    for _ in range(30):
        tts.synthesize_or_cache("Done, sir.")
        tts.synthesize_or_cache("Checking, sir.")

    # 5. HUD Canvas paintEvent
    canvas = HudCanvas(face_path="", assistant_name="ALFRED")
    canvas.resize(400, 400)
    img = QImage(400, 400, QImage.Format.Format_ARGB32_Premultiplied)
    p = QPainter(img)
    try:
        for _ in range(100):
            canvas.paintEvent(None)
    finally:
        p.end()
        canvas._tmr.stop()

    profile.disable()
    print("=== Profiling Complete ===")

    report_stream = io.StringIO()
    stats = pstats.Stats(profile, stream=report_stream).strip_dirs()
    print("\n--- TOP 10 BY CUMULATIVE TIME ---")
    stats.sort_stats("cumulative").print_stats(10)
    output_text = report_stream.getvalue()
    print(output_text[:1200])

    perf_dir = ROOT / "logs" / "perf"
    perf_dir.mkdir(parents=True, exist_ok=True)
    report_file = perf_dir / "latency-benchmark-report.txt"
    report_file.write_text(output_text, encoding="utf-8")
    print(f"\nReport written to: {report_file}")


if __name__ == "__main__":
    run_benchmark()
