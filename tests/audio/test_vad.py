"""
tests/audio/test_vad.py — Unit tests for VoiceActivityDetector constants, energy fallback, and state tracking.
"""

from __future__ import annotations

import unittest
import numpy as np

from core.audio.vad import (
    VoiceActivityDetector,
    VAD_SAMPLE_RATE,
    VAD_WINDOW_SAMPLES,
    VAD_THRESHOLD,
    VAD_SILENCE_TIMEOUT_MS,
)


class TestVoiceActivityDetector(unittest.TestCase):

    def setUp(self):
        self.vad = VoiceActivityDetector(silence_timeout_ms=50)

    def test_constants_defined(self):
        self.assertEqual(VAD_SAMPLE_RATE, 16000)
        self.assertEqual(VAD_WINDOW_SAMPLES, 512)
        self.assertEqual(VAD_THRESHOLD, 0.50)
        self.assertEqual(VAD_SILENCE_TIMEOUT_MS, 600)

    def test_silence_detection(self):
        silence_chunk = np.zeros(512, dtype=np.int16)
        prob = self.vad.speech_probability(silence_chunk)
        self.assertLess(prob, 0.1)

        result = self.vad.process_chunk(silence_chunk)
        self.assertFalse(result["is_speech"])
        self.assertFalse(result["in_speech"])

    def test_energy_fallback_speech_detection(self):
        # Force energy fallback mode
        self.vad._model_failed = True
        self.vad._model = None

        t = np.linspace(0, 512 / 16000, 512, endpoint=False)
        loud_signal = (np.sin(2 * np.pi * 440 * t) * 16000).astype(np.int16)

        prob = self.vad.speech_probability(loud_signal)
        self.assertGreater(prob, 0.5)

        result = self.vad.process_chunk(loud_signal)
        self.assertTrue(result["is_speech"])
        self.assertTrue(result["in_speech"])
        self.assertTrue(result["speech_started"])

    def test_process_chunk_tracks_silence_timeout(self):
        # Force energy fallback mode
        self.vad._model_failed = True
        self.vad._model = None

        t = np.linspace(0, 512 / 16000, 512, endpoint=False)
        loud_signal = (np.sin(2 * np.pi * 440 * t) * 16000).astype(np.int16)
        silence_chunk = np.zeros(512, dtype=np.int16)

        # Start speech
        self.vad.process_chunk(loud_signal)
        self.assertTrue(self.vad._in_speech)

        # Silence for less than timeout (timeout is 50ms)
        import time
        res = self.vad.process_chunk(silence_chunk)
        self.assertTrue(res["in_speech"])

        # Wait past silence timeout
        time.sleep(0.07)
        res = self.vad.process_chunk(silence_chunk)
        self.assertFalse(res["in_speech"])
        self.assertTrue(res["speech_ended"])

    def test_reset(self):
        self.vad._in_speech = True
        self.vad.reset()
        self.assertFalse(self.vad._in_speech)


if __name__ == "__main__":
    unittest.main()
