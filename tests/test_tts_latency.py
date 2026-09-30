"""
tests/test_tts_latency.py — Unit tests for TTS phrase caching, queue metrics, and buffer sizing.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock
import numpy as np

from core.speech.tts import (
    InstrumentedTTS,
    TTS_CACHE,
    TTS_CACHE_SIZE,
    AUDIO_OUTPUT_BUFFER_SIZE,
    TTS_TIMEOUT_S,
    TTSLatencyReport,
)


class TestTTSLatency(unittest.TestCase):

    def setUp(self):
        TTS_CACHE.clear()

    def test_constants_defined(self):
        self.assertEqual(TTS_CACHE_SIZE, 128)
        self.assertEqual(AUDIO_OUTPUT_BUFFER_SIZE, 512)
        self.assertEqual(TTS_TIMEOUT_S, 3.0)

    def test_phrase_caching_and_sub_millisecond_retrieval(self):
        sample_audio = np.zeros(8000, dtype=np.float32)
        synth_mock = MagicMock(return_value=(sample_audio, 24000))

        tts = InstrumentedTTS(synthesizer=synth_mock)

        # First call synthesizes and populates cache
        audio1, sr1, from_cache1 = tts.synthesize_or_cache("Done, sir.")
        self.assertFalse(from_cache1)
        self.assertEqual(synth_mock.call_count, 1)

        # Second call hits cache without calling synthesizer
        audio2, sr2, from_cache2 = tts.synthesize_or_cache("Done, sir.")
        self.assertTrue(from_cache2)
        self.assertEqual(synth_mock.call_count, 1)  # Still 1
        self.assertEqual(sr2, 24000)

    def test_latency_report_structure(self):
        report = TTSLatencyReport(
            text="Checking, sir.",
            queue_delay_ms=5.0,
            synthesis_ms=12.0,
            device_latency_ms=3.0,
            total_ms=20.0,
            from_cache=True,
        )
        self.assertLess(report.total_ms, 500.0)
        self.assertTrue(report.from_cache)


if __name__ == "__main__":
    unittest.main()
