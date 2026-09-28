"""
tests/test_cache.py — Comprehensive Test Suite for CentralizedCache.
Tests:
- Deterministic key generation with collision-resistance
- Cache-aside execution (hit, miss, update)
- TTL expiration
- Prefix-based bulk invalidation
- LRU eviction when reaching capacity
- Graceful fail-open fallback on exceptions
- Integration with daily_brief weather and update_daily_briefing invalidation hooks
"""
import time
import unittest
from unittest.mock import patch, MagicMock

from core.cache import CentralizedCache, get_cache
from actions.daily_brief import _get_live_weather
from actions.update_daily_briefing import update_daily_briefing


class TestCentralizedCache(unittest.TestCase):

    def setUp(self):
        self.cache = CentralizedCache(default_ttl=5, max_entries=50)

    def test_deterministic_key_generation(self):
        """Verifies that key generation is deterministic across varying argument orders."""
        k1 = self.cache.build_key("search", q="batman", limit=10, active=True)
        k2 = self.cache.build_key("search", active=True, limit=10, q="batman")
        self.assertEqual(k1, k2, "Keys must match regardless of keyword argument order")

        # Different prefixes or arguments must yield different keys (no collision)
        k3 = self.cache.build_key("search", q="batman", limit=20, active=True)
        self.assertNotEqual(k1, k3)

        k4 = self.cache.build_key("news", q="batman", limit=10, active=True)
        self.assertNotEqual(k1, k4)

    def test_cache_set_get_hit_miss(self):
        """Tests basic cache-aside hit and miss lifecycle."""
        key = self.cache.build_key("telemetry", node="alpha")
        self.assertIsNone(self.cache.get(key), "Unset key must return None (miss)")

        self.cache.set(key, {"status": "ONLINE", "ping_ms": 12}, ttl=10)
        cached = self.cache.get(key)
        self.assertIsNotNone(cached, "Set key must return value (hit)")
        self.assertEqual(cached["status"], "ONLINE")
        self.assertEqual(cached["ping_ms"], 12)

    def test_ttl_expiration(self):
        """Verifies that entries expire after their TTL has elapsed."""
        key = self.cache.build_key("test_ttl", item=1)
        self.cache.set(key, "ephemeral_data", ttl=1)

        # Immediate check: hit
        self.assertEqual(self.cache.get(key), "ephemeral_data")

        # Wait for TTL expiry
        time.sleep(1.1)
        self.assertIsNone(self.cache.get(key), "Expired key must return None")

    def test_invalidate_prefix(self):
        """Tests prefix-based bulk invalidation for mutation hooks."""
        self.cache.set(self.cache.build_key("weather", city="gotham"), "Cold, 5C", ttl=60)
        self.cache.set(self.cache.build_key("weather", city="metropolis"), "Sunny, 22C", ttl=60)
        self.cache.set(self.cache.build_key("daily_brief", type="morning"), "Briefing content", ttl=60)
        self.cache.set(self.cache.build_key("unrelated", id=1), "Keep this", ttl=60)

        purged = self.cache.invalidate_prefix("weather:")
        self.assertEqual(purged, 2)

        # Weather keys are gone
        self.assertIsNone(self.cache.get(self.cache.build_key("weather", city="gotham")))
        self.assertIsNone(self.cache.get(self.cache.build_key("weather", city="metropolis")))

        # Other keys remain untouched
        self.assertIsNotNone(self.cache.get(self.cache.build_key("daily_brief", type="morning")))
        self.assertIsNotNone(self.cache.get(self.cache.build_key("unrelated", id=1)))

    def test_lru_capacity_eviction(self):
        """Verifies that exceeding max_entries triggers eviction without unbounded growth."""
        small_cache = CentralizedCache(default_ttl=100, max_entries=5)
        for i in range(10):
            small_cache.set(f"key_{i}", f"val_{i}")

        self.assertLessEqual(len(small_cache._memory_store), 5)

    def test_cached_decorator(self):
        """Tests @cached decorator with automatic cache-aside resolution."""
        call_count = 0

        @self.cache.cached(prefix="heavy_calc", ttl=10)
        def expensive_computation(x: int, y: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * y + 42

        # 1st call -> executed (miss)
        res1 = expensive_computation(5, 10)
        self.assertEqual(res1, 92)
        self.assertEqual(call_count, 1)

        # 2nd call with identical args -> returns cached without executing
        res2 = expensive_computation(5, 10)
        self.assertEqual(res2, 92)
        self.assertEqual(call_count, 1, "Cache hit must not re-execute underlying function")

        # 3rd call with different args -> executes (miss)
        res3 = expensive_computation(3, 3)
        self.assertEqual(res3, 51)
        self.assertEqual(call_count, 2)

    def test_graceful_fail_open(self):
        """Verifies that cache errors do not crash callers."""
        broken_cache = CentralizedCache()
        broken_cache._memory_store = None  # Force AttributeError on access

        # Calling get/set should fail open without raising uncaught exceptions
        val = broken_cache.get("test_key")
        self.assertIsNone(val)


class TestCacheIntegrationHooks(unittest.TestCase):

    def setUp(self):
        self.cache = get_cache()
        self.cache.clear()

    @patch("urllib.request.urlopen")
    def test_weather_cache_and_mutation_invalidation(self, mock_urlopen):
        """Tests that weather queries are cached and subsequently invalidated by update_daily_briefing."""
        # Mock weather HTTP response
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"Clear and 20 C"
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        # 1. First call -> executes HTTP fetch
        res1 = _get_live_weather(city="Bludhaven")
        self.assertIn("Currently in Bludhaven", res1)
        self.assertEqual(mock_urlopen.call_count, 1)

        # 2. Second call -> served from cache, zero additional HTTP calls
        res2 = _get_live_weather(city="Bludhaven")
        self.assertEqual(res1, res2)
        self.assertEqual(mock_urlopen.call_count, 1, "Second weather call must be served from cache")

        # 3. Mutation: User updates city via update_daily_briefing
        with patch("actions.update_daily_briefing.update_memory"):
            update_daily_briefing({"city": "Gotham City"})

        # 4. Cache check: Bludhaven weather key has been invalidated by prefix hook
        cached_val = self.cache.get(self.cache.build_key("weather", city="bludhaven"))
        self.assertIsNone(cached_val, "Weather cache must be purged on city update mutation")


if __name__ == "__main__":
    unittest.main()
