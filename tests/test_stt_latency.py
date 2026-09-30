"""
tests/test_stt_latency.py — Unit tests for STT latency metrics and constants.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock
import numpy as np

from core.speech.stt import (
    InstrumentedSTT,
    LatencyReport,
    STT_PROVIDER,
    STT_TIMEOUT_S,
    STT_STREAMING_ENABLED,
    STT_RETRY_MAX_ATTEMPTS,
)
from core.local_stt import FINISH_MS


class TestSTTLatency(unittest.TestCase):

    def test_constants_defined(self):
        self.assertEqual(STT_PROVIDER, "whisper")
        self.assertEqual(STT_TIMEOUT_S, 2.0)
        self.assertTrue(STT_STREAMING_ENABLED)
        self.assertEqual(STT_RETRY_MAX_ATTEMPTS, 2)
        # Verify debounce delay is compressed from 900ms to 350ms
        self.assertEqual(FINISH_MS, 350)

    def test_instrumented_stt_latency_report(self):
        inst = InstrumentedSTT(max_retries=2)
        mock_engine = MagicMock()
        mock_engine.transcribe.return_value = "hello world"
        inst._engine = mock_engine

        audio = np.zeros(16000, dtype=np.float32)
        text, report = inst.transcribe_with_metrics(audio)

        self.assertEqual(text, "hello world")
        self.assertIsInstance(report, LatencyReport)
        self.assertGreaterEqual(report.total_latency_ms, 0.0)
        self.assertGreaterEqual(report.inference_latency_ms, 0.0)


if __name__ == "__main__":
    unittest.main()
