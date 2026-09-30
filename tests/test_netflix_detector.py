"""
tests/test_netflix_detector.py — Unit tests for Netflix UI State Detection Engine.
"""
import unittest
from unittest.mock import MagicMock, patch

from core.pilots.netflix.detector import (
    NetflixDetector,
    NetflixState,
    ProfileSlot,
)


class TestNetflixDetector(unittest.TestCase):
    def setUp(self):
        self.detector = NetflixDetector()

    def test_profile_gate_detection_and_slot_extraction(self):
        tokens = [
            ("Who's watching?", 0.98, (0.50, 0.15)),
            ("Aditya", 0.95, (0.32, 0.50)),
            ("Guest", 0.92, (0.50, 0.50)),
            ("Kids", 0.94, (0.68, 0.50)),
            ("Manage Profiles", 0.90, (0.50, 0.85)),
        ]
        state, profiles = self.detector.detect_state_from_tokens(tokens)

        self.assertEqual(state, NetflixState.PROFILE_GATE)
        self.assertEqual(len(profiles), 3)

        # Profiles must be sorted horizontally left-to-right (slot 1 to N)
        self.assertEqual(profiles[0].name, "Aditya")
        self.assertEqual(profiles[0].slot_index, 1)
        self.assertAlmostEqual(profiles[0].center_norm[0], 0.32)

        self.assertEqual(profiles[1].name, "Guest")
        self.assertEqual(profiles[1].slot_index, 2)
        self.assertAlmostEqual(profiles[1].center_norm[0], 0.50)

        self.assertEqual(profiles[2].name, "Kids")
        self.assertEqual(profiles[2].slot_index, 3)
        self.assertAlmostEqual(profiles[2].center_norm[0], 0.68)

    def test_not_logged_in_detection(self):
        tokens = [
            ("NETFLIX", 0.99, (0.10, 0.05)),
            ("Sign In", 0.96, (0.90, 0.05)),
            ("Unlimited movies, TV shows, and more", 0.93, (0.50, 0.40)),
            ("Starts at $6.99. Cancel anytime.", 0.88, (0.50, 0.48)),
            ("Get Started", 0.95, (0.65, 0.60)),
        ]
        state, profiles = self.detector.detect_state_from_tokens(tokens)
        self.assertEqual(state, NetflixState.NOT_LOGGED_IN)
        self.assertEqual(profiles, [])

    def test_browse_home_detection(self):
        tokens = [
            ("NETFLIX", 0.99, (0.05, 0.04)),
            ("Home", 0.98, (0.12, 0.04)),
            ("TV Shows", 0.95, (0.18, 0.04)),
            ("Movies", 0.96, (0.24, 0.04)),
            ("New & Popular", 0.92, (0.31, 0.04)),
            ("My List", 0.94, (0.38, 0.04)),
            ("Top 10 Movies Today", 0.89, (0.15, 0.35)),
        ]
        state, profiles = self.detector.detect_state_from_tokens(tokens)
        self.assertEqual(state, NetflixState.BROWSE_HOME)
        self.assertEqual(profiles, [])

    def test_playing_state_detection(self):
        tokens = [
            ("Back to Browse", 0.95, (0.05, 0.05)),
            ("Skip Intro", 0.98, (0.90, 0.85)),
            ("Audio & Subtitles", 0.91, (0.85, 0.95)),
        ]
        state, profiles = self.detector.detect_state_from_tokens(tokens)
        self.assertEqual(state, NetflixState.PLAYING)
        self.assertEqual(profiles, [])

    def test_unknown_state_fallback(self):
        tokens = [
            ("Google", 0.99, (0.50, 0.40)),
            ("Search", 0.95, (0.50, 0.50)),
        ]
        state, profiles = self.detector.detect_state_from_tokens(tokens)
        self.assertEqual(state, NetflixState.UNKNOWN)
        self.assertEqual(profiles, [])

    def test_zero_polling_when_not_frontmost(self):
        # When not frontmost and force=False, returns UNKNOWN without OCR
        mock_ocr = MagicMock()
        detector = NetflixDetector(ocr_engine=mock_ocr)

        with patch.object(detector, "is_netflix_frontmost", return_value=False):
            state, profiles = detector.inspect_state(force=False)
            self.assertEqual(state, NetflixState.UNKNOWN)
            self.assertEqual(profiles, [])
            mock_ocr.assert_not_called()


if __name__ == "__main__":
    unittest.main()
