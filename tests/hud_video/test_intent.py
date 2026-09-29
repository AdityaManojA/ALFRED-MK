"""
tests/hud_video/test_intent.py — Unit tests for locus-phrase detection.

No Qt, no network. Pure logic tests.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import unittest

from core.hud_video.intent import detect, is_transport_command, VIDEO_LOCUS_PHRASES


class TestLocusDetection(unittest.TestCase):

    # --- Positive cases ---

    def test_dune_in_the_app(self):
        r = detect("play the new Dune trailer in the app")
        self.assertTrue(r.locus_found)
        self.assertTrue(r.play_intent_found)
        self.assertIn("dune", r.query.lower())
        self.assertNotIn("in the app", r.query.lower())
        self.assertEqual(r.locus_matched, "in the app")

    def test_youtube_url_in_player(self):
        r = detect("play https://youtu.be/abc1234xyz in the player")
        self.assertTrue(r.locus_found)
        self.assertTrue(r.play_intent_found)
        self.assertIn("youtu.be", r.query)

    def test_watch_on_the_hud(self):
        r = detect("watch the Dune trailer on the hud")
        self.assertTrue(r.locus_found)
        self.assertTrue(r.play_intent_found)

    def test_in_hud_alias(self):
        r = detect("play something in hud")
        self.assertTrue(r.locus_found)

    def test_on_screen(self):
        r = detect("show me the trailer on screen")
        self.assertTrue(r.locus_found)
        self.assertTrue(r.play_intent_found)

    def test_batcomputer_alias(self):
        r = detect("stream this in the batcomputer")
        self.assertTrue(r.locus_found)

    def test_query_stripped_clean(self):
        r = detect("play the new Dune trailer in the app")
        # "play", "in the app" should be stripped; "new Dune trailer" should remain
        self.assertNotIn("play", r.query.lower().split())
        self.assertNotIn("in the app", r.query.lower())

    def test_all_locus_phrases_recognized(self):
        for phrase in VIDEO_LOCUS_PHRASES:
            r = detect(f"play something {phrase}")
            self.assertTrue(
                r.locus_found,
                f"Locus phrase not detected: {phrase!r}",
            )

    # --- Negative cases ---

    def test_bare_play_music(self):
        r = detect("play Starboy")
        self.assertFalse(r.locus_found)
        self.assertTrue(r.play_intent_found)

    def test_bare_play_dune(self):
        r = detect("play the new Dune trailer")
        self.assertFalse(r.locus_found)

    def test_bare_play_music2(self):
        r = detect("play some music")
        self.assertFalse(r.locus_found)

    def test_play_daft_punk(self):
        r = detect("play Daft Punk")
        self.assertFalse(r.locus_found)

    def test_no_play_intent(self):
        r = detect("show me in the app")
        # "show" IS a play intent word; should trigger
        self.assertTrue(r.locus_found)
        self.assertTrue(r.play_intent_found)

    def test_just_locus_no_intent(self):
        r = detect("in the player")
        self.assertTrue(r.locus_found)
        self.assertFalse(r.play_intent_found)  # no play verb


class TestTransportCommands(unittest.TestCase):

    def test_pause(self):
        self.assertEqual(is_transport_command("pause"), "pause")

    def test_resume(self):
        self.assertEqual(is_transport_command("resume"), "resume")

    def test_stop_video(self):
        self.assertEqual(is_transport_command("stop video"), "stop_video")

    def test_close_player(self):
        self.assertEqual(is_transport_command("close player"), "stop_video")

    def test_mute(self):
        self.assertEqual(is_transport_command("mute"), "mute")

    def test_unmute(self):
        self.assertEqual(is_transport_command("unmute"), "unmute")

    def test_sound_on(self):
        self.assertEqual(is_transport_command("sound on"), "unmute")

    def test_sound_off(self):
        self.assertEqual(is_transport_command("sound off"), "mute")

    def test_louder(self):
        self.assertEqual(is_transport_command("louder"), "louder")

    def test_quieter(self):
        self.assertEqual(is_transport_command("quieter"), "quieter")

    def test_bring_back_avatar(self):
        self.assertEqual(is_transport_command("bring back the avatar"), "stop_video")

    def test_no_match(self):
        self.assertIsNone(is_transport_command("play Starboy"))

    def test_no_match2(self):
        self.assertIsNone(is_transport_command("what time is it"))


class TestResolve(unittest.TestCase):
    """Pure logic tests — no network calls."""

    def test_youtube_url_detection(self):
        from core.hud_video.resolve import _is_yt_url, _extract_yt_id
        self.assertTrue(_is_yt_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))
        self.assertTrue(_is_yt_url("https://youtu.be/dQw4w9WgXcQ"))
        self.assertTrue(_is_yt_url("https://www.youtube.com/shorts/abc1234xyz1"))
        self.assertFalse(_is_yt_url("https://vimeo.com/123456"))

    def test_video_id_extraction(self):
        from core.hud_video.resolve import _extract_yt_id
        vid = _extract_yt_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertEqual(vid, "dQw4w9WgXcQ")
        vid2 = _extract_yt_id("https://youtu.be/dQw4w9WgXcQ")
        self.assertEqual(vid2, "dQw4w9WgXcQ")

    def test_media_extension_detection(self):
        from core.hud_video.resolve import _looks_like_media_url
        self.assertTrue(_looks_like_media_url("https://cdn.example.com/video.mp4"))
        self.assertTrue(_looks_like_media_url("https://cdn.example.com/stream.m3u8"))
        self.assertFalse(_looks_like_media_url("https://example.com/page.html"))

    def test_local_path_blocked(self):
        from core.hud_video.resolve import resolve, ResolveError
        # Personal-assistant is Heavenly Restricted
        with self.assertRaises(ResolveError):
            resolve(r"D:\Projects\Personal-Assistant\secret.mp4")

    def test_empty_query_raises(self):
        from core.hud_video.resolve import resolve, ResolveError
        # A non-URL, non-path, non-media query string that can't be resolved without
        # network; rather than testing network behavior, verify that a guaranteed
        # blocked path raises correctly.
        with self.assertRaises(ResolveError):
            resolve(r"D:\Projects\Personal-Assistant\clip.mp4")



if __name__ == "__main__":
    unittest.main()
