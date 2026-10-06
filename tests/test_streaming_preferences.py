"""
tests/test_streaming_preferences.py — Verification of ask-once surface preference memory.
"""
import unittest
from unittest.mock import MagicMock, patch

from core.streaming.preferences import (
    forget_preferred_surface,
    format_surface_choice_prompt,
    get_audio_preference,
    get_preferred_surface,
    resolve_surface,
    set_audio_preference,
    set_preferred_surface,
)
from core.streaming.provider import (
    CapabilityClass,
    StreamingProvider,
    Surface,
    SurfaceKind,
)


class MockProvider(StreamingProvider):
    id = "test_provider"
    display_name = "Test Provider"

    def __init__(self, surfaces):
        self._surfaces = surfaces

    def discover_surfaces(self):
        return list(self._surfaces)

    def readiness(self, surface):
        pass

    def open(self, surface):
        pass

    def detect_state(self, surface):
        pass

    def list_profiles(self, surface):
        return []

    def select_profile(self, surface, label):
        pass

    def search(self, surface, query):
        return []

    def play(self, surface, title):
        pass


class TestStreamingPreferences(unittest.TestCase):

    def setUp(self):
        # Isolate config memory
        self._fake_config = {}
        self.patch_load = patch("core.streaming.preferences.load_api_keys", side_effect=lambda: self._fake_config)
        self.patch_update = patch("core.streaming.preferences._update_config", side_effect=self._mock_update_config)
        self.patch_load.start()
        self.patch_update.start()

    def tearDown(self):
        self.patch_load.stop()
        self.patch_update.stop()

    def _mock_update_config(self, mutator):
        mutator(self._fake_config)

    def test_ask_once_persists_and_silently_reuses(self):
        surf_chrome = Surface(id="chrome", display_name="Google Chrome", kind=SurfaceKind.BROWSER, capability=CapabilityClass.FULL)
        surf_app = Surface(id="native_app", display_name="Desktop App", kind=SurfaceKind.NATIVE_APP, capability=CapabilityClass.LAUNCH_ONLY)

        provider = MockProvider([surf_chrome, surf_app])
        prompt_mock = MagicMock(return_value="Desktop App")

        # 1. First resolution: No saved preference -> triggers prompt once
        chosen, override = resolve_surface(provider, prompt_fn=prompt_mock)
        self.assertEqual(chosen.id, "native_app")
        self.assertFalse(override)
        prompt_mock.assert_called_once()
        self.assertEqual(get_preferred_surface("test_provider"), "native_app")

        # 2. Second resolution: Saved preference exists -> reuses silently without prompting
        prompt_mock.reset_mock()
        chosen2, override2 = resolve_surface(provider, prompt_fn=prompt_mock)
        self.assertEqual(chosen2.id, "native_app")
        self.assertFalse(override2)
        prompt_mock.assert_not_called()

    def test_re_asks_if_preferred_surface_disappears(self):
        surf_chrome = Surface(id="chrome", display_name="Google Chrome", kind=SurfaceKind.BROWSER, capability=CapabilityClass.FULL)
        surf_edge = Surface(id="edge", display_name="Microsoft Edge", kind=SurfaceKind.BROWSER, capability=CapabilityClass.FULL)

        set_preferred_surface("test_provider", "firefox") # Saved surface is firefox

        provider = MockProvider([surf_chrome, surf_edge]) # Only chrome & edge present
        prompt_mock = MagicMock(return_value="edge")

        # Saved surface "firefox" is not present -> triggers prompt to pick from real surfaces
        chosen, override = resolve_surface(provider, prompt_fn=prompt_mock)
        self.assertEqual(chosen.id, "edge")
        prompt_mock.assert_called_once()
        self.assertEqual(get_preferred_surface("test_provider"), "edge")

    def test_explicit_override_wins_and_flags_for_update(self):
        surf_chrome = Surface(id="chrome", display_name="Google Chrome", kind=SurfaceKind.BROWSER, capability=CapabilityClass.FULL)
        surf_edge = Surface(id="edge", display_name="Microsoft Edge", kind=SurfaceKind.BROWSER, capability=CapabilityClass.FULL)

        set_preferred_surface("test_provider", "chrome")
        provider = MockProvider([surf_chrome, surf_edge])
        prompt_mock = MagicMock()

        # User says "open in Edge" -> explicit override wins
        chosen, should_persist = resolve_surface(provider, explicit_override="edge", prompt_fn=prompt_mock)
        self.assertEqual(chosen.id, "edge")
        self.assertTrue(should_persist) # Signal to update saved preference after open succeeds
        prompt_mock.assert_not_called()

        # Simulate successful open updating the preference
        set_preferred_surface("test_provider", chosen.id)
        self.assertEqual(get_preferred_surface("test_provider"), "edge")

    def test_forget_preferred_surface(self):
        set_preferred_surface("test_provider", "chrome")
        self.assertEqual(get_preferred_surface("test_provider"), "chrome")

        ok = forget_preferred_surface("test_provider")
        self.assertTrue(ok)
        self.assertIsNone(get_preferred_surface("test_provider"))

    def test_audio_preference_sub_dub(self):
        self.assertEqual(get_audio_preference("crunchyroll"), "sub") # default
        set_audio_preference("crunchyroll", "dub")
        self.assertEqual(get_audio_preference("crunchyroll"), "dub")
        set_audio_preference("crunchyroll", "sub")
        self.assertEqual(get_audio_preference("crunchyroll"), "sub")

    def test_format_prompt_truthful_limits(self):
        surf_chrome = Surface(id="chrome", display_name="Chrome", kind=SurfaceKind.BROWSER, capability=CapabilityClass.FULL)
        surf_app = Surface(id="app", display_name="Desktop App", kind=SurfaceKind.NATIVE_APP, capability=CapabilityClass.LAUNCH_ONLY)

        prompt = format_surface_choice_prompt("Crunchyroll", [surf_chrome, surf_app])
        self.assertIn("Desktop App", prompt)
        self.assertIn("Chrome", prompt)
        self.assertIn("cannot drive it past launch", prompt)
        self.assertIn("full control", prompt)


if __name__ == "__main__":
    unittest.main()
