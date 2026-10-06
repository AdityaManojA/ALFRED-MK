"""
tests/test_wake_word_latency.py — Unit tests for wake-word gate latency and caching.
"""

from __future__ import annotations

import time
import unittest
from unittest.mock import MagicMock, patch
import numpy as np

from core.audio.wakeword import (
    WakeWordDetector,
    WAKEWORD_MODEL_PATH,
    AUDIO_BUFFER_SIZE,
    WAKEWORD_TIMEOUT_S,
    DEFAULT_THRESHOLD,
)


class TestWakeWordLatency(unittest.TestCase):

    def test_constants_defined(self):
        self.assertTrue(WAKEWORD_MODEL_PATH.is_file())
        self.assertEqual(AUDIO_BUFFER_SIZE, 1280)
        self.assertEqual(WAKEWORD_TIMEOUT_S, 5.0)

    def test_feed_and_loop_timestamp_logging(self):
        on_detect_mock = MagicMock()
        log_messages = []

        def mock_logger(msg: str):
            log_messages.append(msg)

        detector = WakeWordDetector(
            on_detect=on_detect_mock,
            threshold=0.5,
            logger=mock_logger,
            enable_speaker_verification=False,
        )

        mock_model = MagicMock()
        # Return detection score > threshold
        mock_model.predict.return_value = {"alfred": 0.85}

        with patch("core.wake_word.get_shared_model", return_value=mock_model):
            started = detector.start()
            self.assertTrue(started)
            self.assertTrue(detector.ready)

            # Feed dummy audio frames with timestamp to satisfy 2 consecutive hits
            dummy_frame = np.zeros(AUDIO_BUFFER_SIZE, dtype=np.int16)
            t_feed = time.perf_counter()
            detector.feed(dummy_frame, timestamp=t_feed)
            detector.feed(dummy_frame, timestamp=t_feed)

            # Wait briefly for worker thread to process frames
            time.sleep(0.10)

            detector.stop()

        on_detect_mock.assert_called_once()
        # Verify latency log entry was produced
        has_gate_log = any("gate_latency=" in m for m in log_messages)
        self.assertTrue(has_gate_log, f"Expected gate latency log, got: {log_messages}")


if __name__ == "__main__":
    unittest.main()
