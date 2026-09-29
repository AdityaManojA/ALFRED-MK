"""
tests/hud_video/test_voice_precedence.py — Unit tests for Visual HUD voice precedence and routing.

Tests deterministic routing between:
1. FOCUS commands ("pause focus", "resume focus")
2. Bare transport commands ("pause", "resume", "replay")
3. Current video references ("play the current video at 2:35")
4. Relative skips ("forward 30 seconds", "back 10s")
5. Time queries ("how much is left")
6. Closing Visual HUD ("close the visual hud", "back to the globe")
7. New video requests with timestamp ("play Dune trailer at 1:10 on the hud")
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import unittest

from core.hud_video.intent import classify_hud_intent, detect


class TestVoicePrecedence(unittest.TestCase):

    # 1. Explicit FOCUS commands always bypass HUD
    def test_pause_focus_bypasses_hud_even_when_playing(self):
        r = classify_hud_intent("pause focus", video_loaded=True, video_visible=True)
        self.assertEqual(r.action, "none")

    def test_resume_focus_bypasses_hud(self):
        r = classify_hud_intent("resume focus", video_loaded=True, video_visible=True)
        self.assertEqual(r.action, "none")

    def test_snooze_focus_bypasses_hud(self):
        r = classify_hud_intent("snooze focus", video_loaded=True, video_visible=True)
        self.assertEqual(r.action, "none")

    # 2. Bare transport words fall through when Visual HUD not visible/loaded
    def test_bare_pause_falls_through_when_no_video(self):
        r = classify_hud_intent("pause", video_loaded=False, video_visible=False)
        self.assertEqual(r.action, "none")

    def test_bare_pause_intercepted_when_hud_visible(self):
        r = classify_hud_intent("pause", video_loaded=True, video_visible=True)
        self.assertEqual(r.action, "pause")

    def test_bare_resume_intercepted_when_hud_visible(self):
        r = classify_hud_intent("resume", video_loaded=True, video_visible=True)
        self.assertEqual(r.action, "resume")

    def test_bare_freeze_intercepted_when_hud_visible(self):
        r = classify_hud_intent("freeze", video_loaded=True, video_visible=True)
        self.assertEqual(r.action, "pause")

    # 3. Current video references
    def test_play_current_video_at_timestamp(self):
        r = classify_hud_intent("play the current video at 2:35", video_loaded=True, video_visible=True)
        self.assertEqual(r.action, "seek")
        self.assertEqual(r.seek_s, 155.0)
        self.assertFalse(r.is_relative)

    def test_jump_to_in_this_video(self):
        r = classify_hud_intent("jump to 1:15 in this video", video_loaded=True, video_visible=True)
        self.assertEqual(r.action, "seek")
        self.assertEqual(r.seek_s, 75.0)
        self.assertFalse(r.is_relative)

    def test_pause_this_video(self):
        r = classify_hud_intent("pause this video", video_loaded=True, video_visible=True)
        self.assertEqual(r.action, "pause")

    # 4. Replay commands
    def test_replay_when_loaded(self):
        r = classify_hud_intent("replay", video_loaded=True, video_visible=True)
        self.assertEqual(r.action, "replay")

    def test_play_again_when_loaded(self):
        r = classify_hud_intent("play again", video_loaded=True, video_visible=True)
        self.assertEqual(r.action, "replay")

    def test_start_over_when_loaded(self):
        r = classify_hud_intent("start over", video_loaded=True, video_visible=True)
        self.assertEqual(r.action, "replay")

    # 5. Direct time seeks and skips while visible
    def test_skip_to_timestamp(self):
        r = classify_hud_intent("skip to 2:35", video_loaded=True, video_visible=True)
        self.assertEqual(r.action, "seek")
        self.assertEqual(r.seek_s, 155.0)

    def test_forward_relative_skip(self):
        r = classify_hud_intent("forward 30 seconds", video_loaded=True, video_visible=True)
        self.assertEqual(r.action, "seek")
        self.assertEqual(r.seek_s, 30.0)
        self.assertTrue(r.is_relative)

    # 6. Time query
    def test_how_much_is_left(self):
        r = classify_hud_intent("how much is left", video_loaded=True, video_visible=True)
        self.assertEqual(r.action, "query_time")

    def test_where_are_we(self):
        r = classify_hud_intent("where are we", video_loaded=True, video_visible=True)
        self.assertEqual(r.action, "query_time")

    # 7. Close / restore globe
    def test_close_the_visual_hud(self):
        r = classify_hud_intent("close the visual hud", video_loaded=True, video_visible=True)
        self.assertEqual(r.action, "stop")

    def test_back_to_the_globe(self):
        r = classify_hud_intent("back to the globe", video_loaded=True, video_visible=True)
        self.assertEqual(r.action, "stop")

    def test_restore_the_avatar(self):
        r = classify_hud_intent("restore the avatar", video_loaded=True, video_visible=True)
        self.assertEqual(r.action, "stop")

    # 8. New video with locus and optional start time
    def test_new_video_with_locus_and_timestamp(self):
        r = classify_hud_intent("play Dune trailer at 1:10 on the hud", video_loaded=True, video_visible=True)
        self.assertEqual(r.action, "new_video")
        self.assertIn("dune", r.target.lower())
        self.assertEqual(r.start_s, 70.0)

    def test_new_video_without_timestamp(self):
        r = classify_hud_intent("watch Oppenheimer trailer in the app", video_loaded=False, video_visible=False)
        self.assertEqual(r.action, "new_video")
        self.assertIn("oppenheimer", r.target.lower())
        self.assertIsNone(r.start_s)


if __name__ == "__main__":
    unittest.main()
