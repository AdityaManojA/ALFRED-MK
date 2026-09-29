"""
tests/hud_video/test_mediatime.py — Unit tests for natural language time parsing.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core.hud_video.mediatime import parse_media_time


class TestMediaTimeParser(unittest.TestCase):

    def test_colon_timestamps(self):
        r1 = parse_media_time("play at 2:35")
        self.assertIsNotNone(r1)
        self.assertEqual(r1.seconds, 155.0)
        self.assertFalse(r1.is_relative)

        r2 = parse_media_time("jump to 1:02:03")
        self.assertIsNotNone(r2)
        self.assertEqual(r2.seconds, 3723.0)
        self.assertFalse(r2.is_relative)

        r3 = parse_media_time("0:45")
        self.assertIsNotNone(r3)
        self.assertEqual(r3.seconds, 45.0)

    def test_words_and_units(self):
        r1 = parse_media_time("2 minutes 35 seconds")
        self.assertIsNotNone(r1)
        self.assertEqual(r1.seconds, 155.0)

        r2 = parse_media_time("90 seconds")
        self.assertIsNotNone(r2)
        self.assertEqual(r2.seconds, 90.0)

        r3 = parse_media_time("two minutes and thirty seconds")
        self.assertIsNotNone(r3)
        self.assertEqual(r3.seconds, 150.0)

    def test_spoken_numbers(self):
        r1 = parse_media_time("play at two thirty five")
        self.assertIsNotNone(r1)
        self.assertEqual(r1.seconds, 155.0)

        r2 = parse_media_time("go to one fifteen")
        self.assertIsNotNone(r2)
        self.assertEqual(r2.seconds, 75.0)

        r3 = parse_media_time("three forty")
        self.assertIsNotNone(r3)
        self.assertEqual(r3.seconds, 220.0)

    def test_symbolic_positions(self):
        duration = 200.0

        r_start = parse_media_time("go to the start", duration_s=duration)
        self.assertIsNotNone(r_start)
        self.assertEqual(r_start.seconds, 0.0)

        r_half = parse_media_time("jump halfway", duration_s=duration)
        self.assertIsNotNone(r_half)
        self.assertEqual(r_half.seconds, 100.0)

        r_end = parse_media_time("skip to the end", duration_s=duration)
        self.assertIsNotNone(r_end)
        self.assertEqual(r_end.seconds, 200.0)

    def test_relative_skips(self):
        r_fwd = parse_media_time("forward 30 seconds")
        self.assertIsNotNone(r_fwd)
        self.assertEqual(r_fwd.seconds, 30.0)
        self.assertTrue(r_fwd.is_relative)

        r_back = parse_media_time("back 30 seconds")
        self.assertIsNotNone(r_back)
        self.assertEqual(r_back.seconds, -30.0)
        self.assertTrue(r_back.is_relative)

        r_skip_min = parse_media_time("skip a minute")
        self.assertIsNotNone(r_skip_min)
        self.assertEqual(r_skip_min.seconds, 60.0)
        self.assertTrue(r_skip_min.is_relative)

        r_rewind_min = parse_media_time("rewind a minute")
        self.assertIsNotNone(r_rewind_min)
        self.assertEqual(r_rewind_min.seconds, -60.0)
        self.assertTrue(r_rewind_min.is_relative)


if __name__ == "__main__":
    unittest.main()
