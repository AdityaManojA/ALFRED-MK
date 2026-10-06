"""
tests/test_netflix_provider.py — Unit tests for NetflixProvider behind StreamingProvider.
"""
import unittest
from unittest.mock import MagicMock, patch

from core.pilots.netflix.detector import NetflixState, ProfileSlot
from core.streaming.provider import (
    CapabilityClass,
    ProviderState,
    Readiness,
    Surface,
    SurfaceKind,
    Title,
)
from core.streaming.providers.netflix import PIN_LOCK_WARNING, NetflixProvider


class TestNetflixProvider(unittest.TestCase):

    def setUp(self):
        self.mock_detector = MagicMock()
        self.provider = NetflixProvider(detector=self.mock_detector)
        self.surface = Surface(
            id="chrome",
            display_name="Google Chrome",
            kind=SurfaceKind.BROWSER,
            capability=CapabilityClass.FULL,
        )

    def test_discover_surfaces_includes_browsers(self):
        surfaces = self.provider.discover_surfaces()
        self.assertTrue(len(surfaces) > 0)
        browser_ids = [s.id for s in surfaces]
        self.assertTrue(any(b in browser_ids for b in ("chrome", "msedge", "brave", "firefox")))

    def test_readiness_not_logged_in(self):
        self.mock_detector.inspect_state.return_value = (NetflixState.NOT_LOGGED_IN, [])
        readiness = self.provider.readiness(self.surface)
        self.assertEqual(readiness, Readiness.NOT_LOGGED_IN)

    def test_readiness_ready_when_home(self):
        self.mock_detector.inspect_state.return_value = (NetflixState.BROWSE_HOME, [])
        readiness = self.provider.readiness(self.surface)
        self.assertEqual(readiness, Readiness.READY)

    def test_list_profiles_extracts_cards(self):
        slots = [
            ProfileSlot(slot_index=1, name="Bruce", center_norm=(0.3, 0.4)),
            ProfileSlot(slot_index=2, name="Alfred", center_norm=(0.7, 0.4)),
        ]
        self.mock_detector.inspect_state.return_value = (NetflixState.PROFILE_GATE, slots)
        profiles = self.provider.list_profiles(self.surface)
        self.assertEqual(len(profiles), 2)
        self.assertEqual(profiles[0].label, "Bruce")
        self.assertEqual(profiles[1].label, "Alfred")

    @patch("pyautogui.size", return_value=(1920, 1080))
    @patch("pyautogui.click")
    def test_select_profile_success(self, mock_click, mock_size):
        slots = [
            ProfileSlot(slot_index=1, name="Bruce", center_norm=(0.3, 0.4)),
        ]
        # First call returns profile gate with slots, second call returns home screen
        self.mock_detector.inspect_state.side_effect = [
            (NetflixState.PROFILE_GATE, slots),
            (NetflixState.BROWSE_HOME, []),
        ]
        self.mock_detector._last_tokens = ["browse", "home", "tv shows"]

        res = self.provider.select_profile(self.surface, "Bruce")
        self.assertTrue(res.ok)
        self.assertIn("Accessing Bruce", res.message)
        mock_click.assert_called_once_with(int(0.3 * 1920), int(0.4 * 1080))

    @patch("pyautogui.size", return_value=(1920, 1080))
    @patch("pyautogui.click")
    def test_select_profile_pin_locked_halts_without_typing(self, mock_click, mock_size):
        slots = [
            ProfileSlot(slot_index=1, name="LockedProfile", center_norm=(0.3, 0.4)),
        ]
        # First call profile gate, second call inspects and sees PIN prompt
        self.mock_detector.inspect_state.side_effect = [
            (NetflixState.PROFILE_GATE, slots),
            (NetflixState.UNKNOWN, []),
        ]
        self.mock_detector._last_tokens = ["enter your pin", "profile lock"]

        res = self.provider.select_profile(self.surface, "LockedProfile")
        self.assertFalse(res.ok)
        self.assertEqual(res.message, PIN_LOCK_WARNING)
        mock_click.assert_called_once_with(int(0.3 * 1920), int(0.4 * 1080))

    @patch("actions.browser_control._open_native")
    def test_search_and_play(self, mock_open):
        titles = self.provider.search(self.surface, "The Batman")
        self.assertEqual(len(titles), 1)
        self.assertEqual(titles[0].name, "The Batman")
        self.assertIn("The%20Batman", titles[0].url)

        res = self.provider.play(self.surface, titles[0])
        self.assertTrue(res.ok)
        self.assertIn("Playing 'The Batman'", res.message)


if __name__ == "__main__":
    unittest.main()
