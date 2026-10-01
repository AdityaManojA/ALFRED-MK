import hashlib
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from core.wake_word import (
    WakeWordDetector,
    WAKE_MODEL,
    WAKE_MODEL_PATH,
    WAKE_MODEL_SHA256,
    WAKE_PHRASE,
    _prediction_score,
)


class WakeWordConfigurationTests(unittest.TestCase):
    def test_alfred_model_is_bundled_and_verified(self):
        self.assertEqual(WAKE_PHRASE, "Alfred")
        self.assertEqual(WAKE_MODEL, "alfred")
        self.assertTrue(WAKE_MODEL_PATH.is_file())
        digest = hashlib.sha256(WAKE_MODEL_PATH.read_bytes()).hexdigest()
        self.assertEqual(digest, WAKE_MODEL_SHA256)

    def test_prediction_score_prefers_alfred_classifier(self):
        scores = {"noise": 0.95, "alfred_v1": 0.72}
        self.assertEqual(_prediction_score(scores), 0.72)

    def test_prediction_score_handles_backend_fallbacks(self):
        self.assertEqual(_prediction_score({"custom": 0.61}), 0.61)
        self.assertEqual(_prediction_score(None), 0.0)

    def test_concurrent_start_spawns_single_thread(self):
        logs = []
        detector = WakeWordDetector(
            on_detect=lambda: None,
            logger=lambda msg: logs.append(msg),
        )

        mock_model = MagicMock()
        with patch("core.wake_word.get_shared_model", return_value=mock_model):
            threads = [threading.Thread(target=detector.start) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertTrue(detector.ready)
            listen_logs = [m for m in logs if f"listening for '{WAKE_PHRASE}'" in m]
            self.assertEqual(len(listen_logs), 1)
            detector.stop()

    def test_new_detector_stops_previous_instance(self):
        d1 = WakeWordDetector(on_detect=lambda: None)
        mock_model = MagicMock()
        with patch("core.wake_word.get_shared_model", return_value=mock_model):
            d1.start()
            self.assertTrue(d1.ready)

            # Instantiating d2 should stop d1
            d2 = WakeWordDetector(on_detect=lambda: None)
            self.assertFalse(d1.ready)
            d2.stop()


if __name__ == "__main__":
    unittest.main()
