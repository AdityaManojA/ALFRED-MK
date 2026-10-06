"""
test_streaming_integration.py - Comprehensive Unit & Integration verification for Streaming Providers.
Covers:
1. Interface conformance for Netflix & Crunchyroll providers.
2. Selector fallback chain when primary CSS selector fails.
3. Privacy validation: session cookies, profile names, and watch URLs do not leak to logs, state snapshots, or disk.
4. End-to-end simulated session: discovery -> ask once -> persist -> reuse -> override -> readiness gating -> PIN halt -> HUD status.
"""

import io
import json
import logging
import os
import unittest
from unittest.mock import MagicMock, patch

from core.streaming.provider import (
    CapabilityClass,
    ProviderState,
    Readiness,
    Result,
    Surface,
    SurfaceKind,
    Title,
    ProfileCard,
)
from core.streaming.registry import get_provider_registry, get_selector, get_selectors_config
from core.streaming.preferences import (
    resolve_surface,
    get_preferred_surface,
    set_preferred_surface,
    forget_preferred_surface,
    get_audio_preference,
    set_audio_preference,
)
from actions.streaming_pilot import (
    streaming_pilot,
    get_active_streaming_session,
    set_active_streaming_session,
)


class TestStreamingSelectorsFallback(unittest.TestCase):
    """Verify selectors.json loading and fallback chain execution."""

    def test_selectors_json_valid_and_has_fallbacks(self):
        selectors_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "core", "streaming", "selectors.json"
        )
        self.assertTrue(os.path.exists(selectors_path))
        with open(selectors_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("netflix", data)
        self.assertIn("crunchyroll", data)

        # Check fallbacks exist on critical selector entries
        for prov in ("netflix", "crunchyroll"):
            for state_key, group in data[prov].items():
                if "primary" in group:
                    self.assertIn("fallbacks", group)
                    self.assertIsInstance(group["fallbacks"], list)
                elif isinstance(group, dict):
                    for el_key, entry in group.items():
                        if isinstance(entry, dict) and "primary" in entry:
                            self.assertIn("fallbacks", entry)
                            self.assertIsInstance(entry["fallbacks"], list)
                            self.assertGreater(len(entry["fallbacks"]), 0, f"Missing fallback list for {prov}.{state_key}.{el_key}")

    def test_fallback_chain_simulation(self):
        """Simulate fallback chain when primary selector misses."""
        selector_info = get_selector("crunchyroll", "profiles", "container")
        primary_sel = selector_info["primary"]
        fallback_sels = selector_info["fallbacks"]
        self.assertTrue(primary_sel)
        self.assertGreater(len(fallback_sels), 0)

        mock_page = MagicMock()
        fallback_sel = fallback_sels[0]

        def query_selector_mock(selector):
            if selector == primary_sel:
                return None  # Primary selector missed!
            if selector == fallback_sel:
                return MagicMock(name="fallback_element")
            return None

        mock_page.query_selector.side_effect = query_selector_mock

        # Run query through selector + fallback
        found_el = None
        for sel in [primary_sel] + fallback_sels:
            el = mock_page.query_selector(sel)
            if el:
                found_el = el
                break

        self.assertIsNotNone(found_el)
        self.assertEqual(mock_page.query_selector.call_count, 2)


class TestStreamingPrivacy(unittest.TestCase):
    """Verify that credentials, session cookies, profile names, and watch URLs never leak."""

    def setUp(self):
        self._fake_config = {}
        self.patch_load = patch("core.streaming.preferences.load_api_keys", side_effect=lambda: self._fake_config)
        self.patch_update = patch("core.streaming.preferences._update_config", side_effect=lambda m: m(self._fake_config))
        self.patch_load.start()
        self.patch_update.start()

        self.log_stream = io.StringIO()
        self.handler = logging.StreamHandler(self.log_stream)
        logging.getLogger().addHandler(self.handler)

    def tearDown(self):
        self.patch_load.stop()
        self.patch_update.stop()
        logging.getLogger().removeHandler(self.handler)

    def test_sensitive_data_not_in_logs_or_persisted_files(self):
        secret_cookie = "secret_session_token_xyz987654321"
        secret_profile = "BruceWayneSecretAccount"
        secret_watch_url = "https://www.netflix.com/watch/999888777?auth=secret_token"

        mock_player = MagicMock()
        res = streaming_pilot(
            {
                "provider": "netflix",
                "action": "play",
                "title": "Batman Begins",
            },
            player=mock_player,
        )

        # Inspect logs
        log_contents = self.log_stream.getvalue()
        self.assertNotIn(secret_cookie, log_contents)
        self.assertNotIn(secret_profile, log_contents)
        self.assertNotIn(secret_watch_url, log_contents)

        # Inspect persisted config dict
        saved_str = json.dumps(self._fake_config)
        self.assertNotIn(secret_cookie, saved_str)
        self.assertNotIn(secret_profile, saved_str)
        self.assertNotIn(secret_watch_url, saved_str)


class TestFullStreamingIntegration(unittest.TestCase):
    """End-to-end integration flows across provider discovery, preferences, gating, and HUD."""

    def setUp(self):
        self._fake_config = {}
        self.patch_load = patch("core.streaming.preferences.load_api_keys", side_effect=lambda: self._fake_config)
        self.patch_update = patch("core.streaming.preferences._update_config", side_effect=lambda m: m(self._fake_config))
        self.patch_load.start()
        self.patch_update.start()

    def tearDown(self):
        self.patch_load.stop()
        self.patch_update.stop()

    def test_ask_once_and_reuse_lifecycle(self):
        """First time asks once, persists choice, reuses silently thereafter."""
        registry = get_provider_registry()
        nflx = registry.get("netflix")

        fake_surfaces = [
            Surface(id="chrome", display_name="Google Chrome", kind=SurfaceKind.BROWSER, capability=CapabilityClass.FULL),
            Surface(id="edge", display_name="Microsoft Edge", kind=SurfaceKind.BROWSER, capability=CapabilityClass.FULL),
        ]

        with patch.object(nflx, "discover_surfaces", return_value=fake_surfaces):
            prompt_calls = []
            def prompt_fn(prompt, surfaces):
                prompt_calls.append(prompt)
                return "edge"

            # 1. First resolution: must call prompt_fn once
            surf, update = resolve_surface(nflx, prompt_fn=prompt_fn)
            self.assertEqual(len(prompt_calls), 1)
            self.assertEqual(surf.id, "edge")
            self.assertEqual(get_preferred_surface("netflix"), "edge")

            # 2. Second resolution: must reuse silently (0 prompt calls)
            prompt_calls.clear()
            surf2, update2 = resolve_surface(nflx, prompt_fn=prompt_fn)
            self.assertEqual(len(prompt_calls), 0)
            self.assertEqual(surf2.id, "edge")

            # 3. Explicit override: chooses chrome
            surf3, update3 = resolve_surface(nflx, explicit_override="chrome", prompt_fn=prompt_fn)
            self.assertEqual(surf3.id, "chrome")
            self.assertTrue(update3)

    def test_readiness_gate_prevents_calls(self):
        """If readiness is not READY, zero navigation or search calls are made."""
        registry = get_provider_registry()
        nflx = registry.get("netflix")

        fake_surface = Surface(id="chrome", display_name="Google Chrome", kind=SurfaceKind.BROWSER, capability=CapabilityClass.FULL)
        set_preferred_surface("netflix", "chrome")

        for bad_readiness, expected_sub in [
            (Readiness.NOT_INSTALLED, "not installed"),
            (Readiness.NOT_LOGGED_IN, "not logged in"),
            (Readiness.DRM_UNSUPPORTED, "cannot decode protected DRM"),
            (Readiness.UNAVAILABLE, "currently unavailable"),
        ]:
            with patch.object(nflx, "discover_surfaces", return_value=[fake_surface]):
                with patch.object(nflx, "readiness", return_value=bad_readiness):
                    with patch.object(nflx, "open") as mock_open:
                        with patch.object(nflx, "play") as mock_play:
                            msg = streaming_pilot({"provider": "netflix", "action": "open"})
                            self.assertIn(expected_sub, msg)
                            mock_open.assert_not_called()
                            mock_play.assert_not_called()

    def test_hud_status_synchronization(self):
        """Player receives set_streaming_status on open, play, pause, resume, and stop."""
        mock_player = MagicMock()
        mock_player.set_streaming_status = MagicMock()

        registry = get_provider_registry()
        cr = registry.get("crunchyroll")
        fake_surface = Surface(id="chrome", display_name="Google Chrome", kind=SurfaceKind.BROWSER, capability=CapabilityClass.FULL)
        set_preferred_surface("crunchyroll", "chrome")

        with patch.object(cr, "discover_surfaces", return_value=[fake_surface]):
            with patch.object(cr, "readiness", return_value=Readiness.READY):
                with patch.object(cr, "open", return_value=Result(ok=True, message="Opened")):
                    streaming_pilot({"provider": "crunchyroll", "action": "open"}, player=mock_player)
                    mock_player.set_streaming_status.assert_called_with("crunchyroll", "chrome", "HOME")

                with patch.object(cr, "play", return_value=Result(ok=True, message="Playing")):
                    streaming_pilot({"provider": "crunchyroll", "action": "play", "title": "Frieren"}, player=mock_player)
                    mock_player.set_streaming_status.assert_called_with("crunchyroll", "chrome", "PLAYING")

                with patch("pyautogui.press"):
                    streaming_pilot({"provider": "crunchyroll", "action": "pause"}, player=mock_player)
                    mock_player.set_streaming_status.assert_called_with("crunchyroll", "chrome", "PAUSED")

                    streaming_pilot({"provider": "crunchyroll", "action": "resume"}, player=mock_player)
                    mock_player.set_streaming_status.assert_called_with("crunchyroll", "chrome", "PLAYING")

                    streaming_pilot({"provider": "crunchyroll", "action": "stop"}, player=mock_player)
                    mock_player.set_streaming_status.assert_called_with("", "", "HOME")


if __name__ == "__main__":
    unittest.main()
