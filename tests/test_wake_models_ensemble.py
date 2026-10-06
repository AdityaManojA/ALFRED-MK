import unittest
from pathlib import Path
import numpy as np

from core.wake_word import (
    get_wake_model_paths,
    _make_model,
    _prediction_score,
    _top_prediction,
    VALID_WAKE_MODEL_SHA256S,
)


class TestWakeModelsEnsemble(unittest.TestCase):
    """Test suite for multi-head wake word ensemble with 1.onnx, 2.onnx, 3.onnx."""

    def test_discovered_model_paths_include_numbered_models(self):
        """Verify get_wake_model_paths discovers alfred.onnx, 1.onnx, 2.onnx, and 3.onnx."""
        paths = get_wake_model_paths()
        names = {Path(p).name.lower() for p in paths}
        self.assertIn("alfred.onnx", names)
        self.assertIn("1.onnx", names)
        self.assertIn("2.onnx", names)
        self.assertIn("3.onnx", names)

    def test_prediction_score_with_ensemble_keys(self):
        """Verify _prediction_score handles numbered and named keys accurately."""
        scores = {"alfred": 0.02, "1": 0.15, "2": 0.88, "3": 0.45}
        self.assertAlmostEqual(_prediction_score(scores), 0.88)

        # Empty or invalid dictionary returns 0.0
        self.assertEqual(_prediction_score({}), 0.0)
        self.assertEqual(_prediction_score(None), 0.0)

    def test_top_prediction_with_ensemble_keys(self):
        """Verify _top_prediction returns the highest confidence model name and score."""
        scores = {"alfred": 0.02, "1": 0.15, "2": 0.94, "3": 0.45}
        top_name, top_score = _top_prediction(scores)
        self.assertEqual(top_name, "2")
        self.assertAlmostEqual(top_score, 0.94)

    def test_openwakeword_model_instantiation(self):
        """Verify OpenWakeWord instantiates with all 4 heads active."""
        model = _make_model()
        heads = set(model.models.keys())
        self.assertIn("alfred", heads)
        self.assertIn("1", heads)
        self.assertIn("2", heads)
        self.assertIn("3", heads)

        # Predict one frame of silence (1280 int16 samples)
        frame = np.zeros(1280, dtype=np.int16)
        pred = model.predict(frame)
        for h in ("alfred", "1", "2", "3"):
            self.assertIn(h, pred)
            self.assertIsInstance(pred[h], (float, np.floating))


if __name__ == "__main__":
    unittest.main()
