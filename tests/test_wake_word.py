import hashlib
import unittest

from core.wake_word import (
    WAKE_MODEL,
    WAKE_MODEL_PATH,
    WAKE_MODEL_SHA256,
    WAKE_PHRASE,
    _prediction_score,
)


class WakeWordConfigurationTests(unittest.TestCase):
    def test_alfred_model_is_bundled_and_verified(self):
        self.assertEqual(WAKE_PHRASE, "Hey Alfred")
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


if __name__ == "__main__":
    unittest.main()
