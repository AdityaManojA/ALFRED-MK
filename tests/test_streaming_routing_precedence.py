"""
tests/test_streaming_routing_precedence.py — Comprehensive verification of 6-level voice routing precedence.
"""
import unittest

from core.intents.router import IntentRouter


class TestStreamingRoutingPrecedence(unittest.TestCase):

    def setUp(self):
        self.router = IntentRouter()

    def test_case_1_explicit_provider(self):
        # Netflix explicit
        m1 = self.router.route("play The Batman on Netflix")
        self.assertIsNotNone(m1)
        self.assertEqual(m1.action_name, "streaming_pilot")
        self.assertEqual(m1.entities.get("provider"), "netflix")
        self.assertEqual(m1.entities.get("query").lower(), "the batman")

        # Crunchyroll explicit
        m2 = self.router.route("watch Frieren on Crunchyroll")
        self.assertIsNotNone(m2)
        self.assertEqual(m2.action_name, "streaming_pilot")
        self.assertEqual(m2.entities.get("provider"), "crunchyroll")

        m3 = self.router.route("open crunchyroll")
        self.assertIsNotNone(m3)
        self.assertEqual(m3.action_name, "streaming_pilot")
        self.assertEqual(m3.entities.get("provider"), "crunchyroll")

    def test_case_2_visual_hud_transport_precedence(self):
        ctx = {"is_hud_video_playing": True}
        m = self.router.route("pause", context=ctx)
        self.assertIsNotNone(m)
        self.assertEqual(m.action_name, "hud_video")

        m_resume = self.router.route("resume", context=ctx)
        self.assertIsNotNone(m_resume)
        self.assertEqual(m_resume.action_name, "hud_video")

    def test_case_3_provider_internal_transport_precedence(self):
        ctx = {"streaming_state": "PLAYING", "active_streaming_provider": "crunchyroll"}
        # "pause" during Crunchyroll playback routes to provider, NOT HUD, NOT Sentry FOCUS
        m_pause = self.router.route("pause", context=ctx)
        self.assertIsNotNone(m_pause)
        self.assertEqual(m_pause.action_name, "streaming_pilot")
        self.assertEqual(m_pause.entities.get("action"), "pause")
        self.assertEqual(m_pause.entities.get("provider"), "crunchyroll")

        m_skip = self.router.route("skip intro", context=ctx)
        self.assertIsNotNone(m_skip)
        self.assertEqual(m_skip.action_name, "streaming_pilot")
        self.assertEqual(m_skip.entities.get("action"), "skip_intro")

        m_next = self.router.route("next episode", context=ctx)
        self.assertIsNotNone(m_next)
        self.assertEqual(m_next.action_name, "streaming_pilot")
        self.assertEqual(m_next.entities.get("action"), "next_episode")

    def test_case_4_youtube_browser(self):
        m = self.router.route("play interstellar trailer on youtube")
        self.assertIsNotNone(m)
        self.assertEqual(m.action_name, "browser_control")
        self.assertEqual(m.entities.get("query"), "interstellar trailer")

        m_open = self.router.route("open youtube")
        self.assertIsNotNone(m_open)
        self.assertEqual(m_open.action_name, "browser_control")

    def test_case_5_spotify_readiness_gate(self):
        # Ready
        m_ready = self.router.route("play miles davis on spotify", context={"is_spotify_ready": True})
        self.assertIsNotNone(m_ready)
        self.assertEqual(m_ready.action_name, "spotify_control")

        # Not ready -> gated, zero network calls to spotify
        m_unready = self.router.route("play miles davis on spotify", context={"is_spotify_ready": False})
        self.assertIsNotNone(m_unready)
        self.assertEqual(m_unready.action_name, "spotify_not_configured")

    def test_case_6_ambiguous_play_asks_clarification(self):
        # Genuinely ambiguous "play Inception" with no context -> ask "Music or video, sir?"
        m = self.router.route("play Inception")
        self.assertIsNotNone(m)
        self.assertEqual(m.action_name, "ask_clarification")
        self.assertEqual(m.entities.get("question"), "Music or video, sir?")

        # Ambiguous with music context -> spotify
        m_music = self.router.route("play Inception", context={"conversation_context": "music"})
        self.assertIsNotNone(m_music)
        self.assertEqual(m_music.action_name, "spotify_control")

        # Ambiguous with video context -> streaming
        m_video = self.router.route("play Inception", context={"conversation_context": "movie"})
        self.assertIsNotNone(m_video)
        self.assertEqual(m_video.action_name, "streaming_pilot")


if __name__ == "__main__":
    unittest.main()
