"""
tests/test_crunchyroll_provider.py — Unit tests for CrunchyrollProvider behind StreamingProvider.
"""
import unittest
from unittest.mock import MagicMock, patch

from core.streaming.preferences import get_audio_preference, set_audio_preference
from core.streaming.provider import (
    CapabilityClass,
    Readiness,
    Surface,
    SurfaceKind,
    Title,
)
from core.streaming.providers.crunchyroll import (
    MSG_PREMIUM_LOCKED,
    CrunchyrollProvider,
    parse_query_episode_specs,
)


class TestCrunchyrollProvider(unittest.TestCase):

    def setUp(self):
        self.provider = CrunchyrollProvider()
        self.surface = Surface(
            id="chrome",
            display_name="Google Chrome",
            kind=SurfaceKind.BROWSER,
            capability=CapabilityClass.FULL,
        )

    def test_parse_query_episode_specs(self):
        # 1. Plain series
        s, season, ep, audio = parse_query_episode_specs("frieren")
        self.assertEqual(s, "frieren")
        self.assertIsNone(season)
        self.assertIsNone(ep)
        self.assertIsNone(audio)

        # 2. Episode and dub
        s, season, ep, audio = parse_query_episode_specs("frieren episode 5 dub")
        self.assertEqual(s, "frieren")
        self.assertEqual(ep, 5)
        self.assertEqual(audio, "dub")

        # 3. Season and episode and sub
        s, season, ep, audio = parse_query_episode_specs("jujutsu kaisen season 2 ep 12 sub")
        self.assertEqual(s, "jujutsu kaisen")
        self.assertEqual(season, 2)
        self.assertEqual(ep, 12)
        self.assertEqual(audio, "sub")

    @patch("actions.browser_control._open_native")
    def test_search_resolves_series_and_remembers_audio_pref(self, mock_open):
        set_audio_preference("crunchyroll", "sub")
        titles = self.provider.search(self.surface, "Frieren episode 5 dub")
        self.assertEqual(len(titles), 1)
        self.assertEqual(titles[0].name, "Frieren")
        self.assertEqual(titles[0].episode_number, 5)
        self.assertEqual(titles[0].audio_type, "dub")
        # Preference was updated to dub
        self.assertEqual(get_audio_preference("crunchyroll"), "dub")

    @patch("actions.browser_control._open_native")
    def test_play_premium_locked_reports_cleanly(self, mock_open):
        locked_title = Title(
            id="locked-ep",
            name="Demon Slayer Ep 1",
            is_premium_locked=True,
        )
        res = self.provider.play(self.surface, locked_title)
        self.assertFalse(res.ok)
        self.assertEqual(res.message, MSG_PREMIUM_LOCKED)
        mock_open.assert_not_called()

    @patch("pyautogui.press")
    @patch("actions.browser_control._open_native")
    def test_play_free_episode_succeeds(self, mock_open, mock_press):
        title = Title(
            id="frieren",
            name="Frieren",
            episode_number=3,
            audio_type="sub",
            is_premium_locked=False,
        )
        res = self.provider.play(self.surface, title)
        self.assertTrue(res.ok)
        self.assertIn("Playing Frieren (Episode 3) on Crunchyroll (sub)", res.message)
        mock_open.assert_called_once()


if __name__ == "__main__":
    unittest.main()
