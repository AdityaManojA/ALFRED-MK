"""
tests/audio/test_wakeword_tiny.py — Unit tests for DualWakeWordDetector, thresholds, gating, and refractory lockout.
"""

from __future__ import annotations

import time
import unittest
import numpy as np

from core.audio.gate import AudioGate, GATE_TTS, get_audio_gate
from core.audio.wakeword_tiny import (
    DualWakeWordDetector,
    WakeDetectionResult,
    WAKEWORD_CONFIDENCE_HEY,
    WAKEWORD_CONFIDENCE_BARE,
    REFRACTORY_WINDOW_MS,
    SAMPLE_RATE,
    AUDIO_FRAME_SAMPLES,
)


class TestDualWakeWordDetector(unittest.TestCase):

    def setUp(self):
        self.gate = get_audio_gate()
        self.gate.reset()
        self.events: list[WakeDetectionResult] = []
        self.detector = DualWakeWordDetector(
            on_detect=lambda evt: self.events.append(evt),
            hey_threshold=0.70,
            bare_threshold=0.85,
            refractory_ms=100,  # fast refractory window for test speed
        )

    def tearDown(self):
        self.gate.reset()

    def test_constants_defined(self):
        self.assertEqual(WAKEWORD_CONFIDENCE_HEY, 0.70)
        self.assertEqual(WAKEWORD_CONFIDENCE_BARE, 0.85)
        self.assertEqual(REFRACTORY_WINDOW_MS, 1500)
        self.assertEqual(SAMPLE_RATE, 16000)
        self.assertEqual(AUDIO_FRAME_SAMPLES, 1280)

    def test_tts_acoustic_gate_suppression(self):
        self.gate.hold(GATE_TTS)
        dummy_pcm = np.zeros(AUDIO_FRAME_SAMPLES, dtype=np.int16)

        result = self.detector.feed(dummy_pcm)
        self.assertIsNone(result)
        self.assertEqual(len(self.events), 0)

    def test_refractory_lockout(self):
        self.detector._last_trigger_time = time.monotonic()
        dummy_pcm = np.zeros(AUDIO_FRAME_SAMPLES, dtype=np.int16)

        # In refractory window -> immediately returns None
        result = self.detector.feed(dummy_pcm)
        self.assertIsNone(result)

        # After refractory window -> can process
        time.sleep(0.12)
        # Should not be blocked by refractory now
        self.detector.feed(dummy_pcm)

    def test_buffer_accumulation(self):
        # Feeding less than AUDIO_FRAME_SAMPLES accumulates in buffer
        half_frame = np.zeros(AUDIO_FRAME_SAMPLES // 2, dtype=np.int16)
        res = self.detector.feed(half_frame)
        self.assertIsNone(res)
        self.assertEqual(len(self.detector._buffer), (AUDIO_FRAME_SAMPLES // 2) * 2)

    def test_dual_thresholds(self):
        self.assertEqual(self.detector.hey_threshold, 0.70)
        self.assertEqual(self.detector.bare_threshold, 0.85)
        self.assertGreater(self.detector.bare_threshold, self.detector.hey_threshold)


if __name__ == "__main__":
    unittest.main()
