"""
tests/intents/test_speculative_prefetch.py — Purity and latency tests for SpeculativePrefetcher.
"""

from __future__ import annotations

import os
import sys
import time
import unittest

from core.intents.fastpath import (
    SpeculativePrefetcher,
    PrefetchRecord,
    PREFETCH_TTL_S,
    MAX_PREFETCH_ENTRIES,
    PREFETCH_TIMEOUT_S,
)


class TestSpeculativePrefetch(unittest.TestCase):

    def setUp(self):
        self.prefetcher = SpeculativePrefetcher(ttl_s=0.2, max_entries=10)

    def tearDown(self):
        self.prefetcher.shutdown()

    def test_constants_defined(self):
        self.assertEqual(PREFETCH_TTL_S, 10.0)
        self.assertEqual(MAX_PREFETCH_ENTRIES, 64)
        self.assertEqual(PREFETCH_TIMEOUT_S, 2.0)

    def test_ttl_expiry(self):
        self.prefetcher.store("test", "key1", "val1")
        self.assertEqual(self.prefetcher.get("test", "key1"), "val1")

        # Sleep past TTL (0.2s)
        time.sleep(0.25)
        self.assertIsNone(self.prefetcher.get("test", "key1"))

    def test_pure_resolvers_have_zero_side_effects(self):
        """Purity Guarantee: Resolvers must not mutate file system, environment, or system state."""
        env_before = dict(os.environ)
        cwd_before = os.getcwd()

        time_res = SpeculativePrefetcher._pure_time_date()
        self.assertIn("time", time_res)
        self.assertIn("date", time_res)

        app_res = SpeculativePrefetcher._pure_app_lookup("notepad")
        # May be str path on Windows or None elsewhere, but must not launch
        self.assertTrue(app_res is None or isinstance(app_res, str))

        telemetry = SpeculativePrefetcher._pure_system_telemetry()
        self.assertIsInstance(telemetry, dict)

        dns_res = SpeculativePrefetcher._pure_dns_warm("localhost")
        self.assertIn(dns_res, ("127.0.0.1", "::1", None))

        # Assert no environment or cwd mutations
        self.assertEqual(os.environ, env_before)
        self.assertEqual(os.getcwd(), cwd_before)

    def test_inspect_partial_triggers_async_resolution(self):
        self.prefetcher.inspect_partial("what time is it right now?")
        # Wait brief moment for worker thread
        time.sleep(0.08)

        cached_time = self.prefetcher.get("time_date", "now")
        self.assertIsNotNone(cached_time)
        self.assertIn("time", cached_time)


if __name__ == "__main__":
    unittest.main()
