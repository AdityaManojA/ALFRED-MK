"""
tests/test_intent_router.py — Unit tests for fast-path intent routing and latency metrics.
"""

from __future__ import annotations

import unittest

from core.intents.router import (
    IntentRouter,
    INTENT_PARSE_TIMEOUT_S,
    PHRASE_CACHE_SIZE,
)


class TestIntentRouter(unittest.TestCase):

    def setUp(self):
        self.router = IntentRouter(cache_size=PHRASE_CACHE_SIZE)

    def test_constants_defined(self):
        self.assertEqual(INTENT_PARSE_TIMEOUT_S, 0.5)
        self.assertEqual(PHRASE_CACHE_SIZE, 256)

    def test_fast_path_routing_time(self):
        match = self.router.route("what time is it")
        self.assertIsNotNone(match)
        self.assertEqual(match.intent_name, "get_time")
        self.assertEqual(match.action_name, "system_status")
        # Ensure fast-path latency is well under 200ms (typically < 1ms)
        self.assertLess(match.metrics.total_ms, 20.0)

    def test_fast_path_entity_extraction(self):
        match = self.router.route("search netflix for Interstellar")
        self.assertIsNotNone(match)
        self.assertEqual(match.intent_name, "search_netflix")
        self.assertEqual(match.entities.get("query"), "interstellar")

    def test_lru_cache_hit(self):
        # First call populates cache
        m1 = self.router.route("what time is it")
        # Second call hits cache
        m2 = self.router.route("what time is it")
        self.assertIsNotNone(m2)
        self.assertEqual(m2.intent_name, "get_time")
        self.assertLess(m2.metrics.total_ms, 5.0)

    def test_unmatched_falls_back(self):
        match = self.router.route("compose a sonnet about quantum electrodynamics")
        self.assertIsNone(match)


if __name__ == "__main__":
    unittest.main()
