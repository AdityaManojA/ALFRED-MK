"""
tests/test_streaming_provider_interface.py — Conformance tests for StreamingProvider interface.
"""
import sys
import unittest
from typing import List

from core.streaming.provider import (
    CapabilityClass,
    ProfileCard,
    ProviderState,
    Readiness,
    Result,
    StreamingProvider,
    Surface,
    SurfaceKind,
    Title,
)
from core.streaming.registry import (
    ProviderRegistry,
    get_selector,
    get_selectors_config,
)


class FakeStreamingProvider(StreamingProvider):
    """Minimal compliant provider for interface verification."""
    id = "fake_service"
    display_name = "Fake Service"

    def discover_surfaces(self) -> List[Surface]:
        return [
            Surface(
                id="fake_chrome",
                display_name="Google Chrome",
                kind=SurfaceKind.BROWSER,
                capability=CapabilityClass.FULL,
            )
        ]

    def readiness(self, surface: Surface) -> Readiness:
        if surface.capability == CapabilityClass.UNAVAILABLE:
            return Readiness.UNAVAILABLE
        return Readiness.READY

    def open(self, surface: Surface) -> Result:
        return Result(ok=True, message="Opened fake surface")

    def detect_state(self, surface: Surface) -> ProviderState:
        return ProviderState.HOME

    def list_profiles(self, surface: Surface) -> List[ProfileCard]:
        return [
            ProfileCard(id="p1", label="Bruce", is_locked=False),
            ProfileCard(id="p2", label="Wayne", is_locked=True),
        ]

    def select_profile(self, surface: Surface, label: str) -> Result:
        if label.lower() == "wayne":
            return Result(ok=False, message="Profile is PIN-locked")
        return Result(ok=True, message=f"Selected {label}")

    def search(self, surface: Surface, query: str) -> List[Title]:
        return [
            Title(id="t1", name="The Batman", is_series=False),
            Title(id="t2", name="Batman: The Animated Series", is_series=True),
        ]

    def play(self, surface: Surface, title: Title) -> Result:
        if title.is_premium_locked:
            return Result(ok=False, message="Requires premium")
        return Result(ok=True, message=f"Playing {title.name}")


class TestStreamingProviderInterface(unittest.TestCase):

    def test_fake_provider_conformance(self):
        provider = FakeStreamingProvider()
        surfaces = provider.discover_surfaces()
        self.assertEqual(len(surfaces), 1)
        self.assertEqual(surfaces[0].kind, SurfaceKind.BROWSER)

        readiness = provider.readiness(surfaces[0])
        self.assertEqual(readiness, Readiness.READY)

        res_open = provider.open(surfaces[0])
        self.assertTrue(res_open.ok)

        st = provider.detect_state(surfaces[0])
        self.assertEqual(st, ProviderState.HOME)

        profiles = provider.list_profiles(surfaces[0])
        self.assertEqual(len(profiles), 2)
        self.assertFalse(profiles[0].is_locked)
        self.assertTrue(profiles[1].is_locked)

        res_sel = provider.select_profile(surfaces[0], "Bruce")
        self.assertTrue(res_sel.ok)

        res_pin = provider.select_profile(surfaces[0], "Wayne")
        self.assertFalse(res_pin.ok)

        results = provider.search(surfaces[0], "Batman")
        self.assertEqual(len(results), 2)
        self.assertTrue(results[1].is_series)

        res_play = provider.play(surfaces[0], results[0])
        self.assertTrue(res_play.ok)

    def test_registry_lazy_registration_and_retrieval(self):
        reg = ProviderRegistry()
        reg.register("fake", lambda: FakeStreamingProvider())
        self.assertIn("fake", reg.list_available_providers())

        inst = reg.get("fake")
        self.assertIsNotNone(inst)
        self.assertIsInstance(inst, FakeStreamingProvider)
        # Verify cached singleton resolution
        self.assertIs(reg.get("fake"), inst)

    def test_selector_loader_and_fallbacks(self):
        cfg = get_selectors_config()
        self.assertIn("netflix", cfg)
        self.assertIn("crunchyroll", cfg)

        # Check netflix login selector
        sel = get_selector("netflix", "login")
        self.assertTrue(len(sel["primary"]) > 0)
        self.assertTrue(len(sel["fallbacks"]) > 0)

        # Check nested crunchyroll player skip intro
        skip_sel = get_selector("crunchyroll", "player", "skip_intro")
        self.assertEqual(skip_sel["primary"], "button[data-t='skip-intro-button']")
        self.assertIn("button:has-text('Skip Intro')", skip_sel["fallbacks"])

    def test_importing_core_streaming_does_not_pull_playwright(self):
        # Ensure playwright is not loaded just by importing core.streaming
        self.assertNotIn("playwright", sys.modules)


if __name__ == "__main__":
    unittest.main()
