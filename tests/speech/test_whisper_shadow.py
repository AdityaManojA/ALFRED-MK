"""
tests/speech/test_whisper_shadow.py — Unit tests for ShadowWhisperWorker, queue processing, and partials.
"""

from __future__ import annotations

import time
import unittest
import numpy as np

from core.speech.whisper_shadow import (
    ShadowWhisperWorker,
    WhisperPartial,
    WHISPER_MODEL_NAME,
    WHISPER_COMPUTE_TYPE,
    WHISPER_DEVICE,
    WHISPER_THREADS,
    PARTIAL_WINDOW_S,
    SAMPLE_RATE,
)


class TestWhisperShadow(unittest.TestCase):

    def test_constants_defined(self):
        self.assertEqual(WHISPER_MODEL_NAME, "tiny.en")
        self.assertEqual(WHISPER_COMPUTE_TYPE, "int8")
        self.assertEqual(WHISPER_DEVICE, "cpu")
        self.assertEqual(WHISPER_THREADS, 4)
        self.assertEqual(PARTIAL_WINDOW_S, 1.5)
        self.assertEqual(SAMPLE_RATE, 16000)

    def test_worker_lifecycle_and_queue(self):
        partials = []
        worker = ShadowWhisperWorker(
            on_partial=lambda p: partials.append(p),
            window_s=0.5,
        )
        self.assertFalse(worker._running)

        worker.start()
        self.assertTrue(worker._running)
        self.assertIsNotNone(worker._thread)
        self.assertTrue(worker._thread.is_alive())

        # Feed silence chunks
        silence = np.zeros(512, dtype=np.int16)
        for _ in range(10):
            worker.feed_chunk(silence)

        time.sleep(0.1)
        worker.stop()
        self.assertFalse(worker._running)
        self.assertIsNone(worker._thread)

    def test_partial_dataclass(self):
        p = WhisperPartial(
            text="hello alfred",
            is_final=False,
            confidence=0.88,
            timestamp=123.456,
        )
        self.assertEqual(p.text, "hello alfred")
        self.assertFalse(p.is_final)
        self.assertEqual(p.confidence, 0.88)
        self.assertEqual(p.timestamp, 123.456)


if __name__ == "__main__":
    unittest.main()
