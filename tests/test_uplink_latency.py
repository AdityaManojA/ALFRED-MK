"""
tests/test_uplink_latency.py — Unit tests for uplink timeout and reconnect backoff bounds.
"""

from __future__ import annotations

import unittest

from dashboard.server import (
    UPLINK_TIMEOUT_S,
    RECONNECT_BASE_S,
    RECONNECT_MAX_S,
    UPLINK_HISTORY_N,
)
from main import (
    RECONNECT_BASE_S as MAIN_RECONNECT_BASE,
    RECONNECT_MAX_S as MAIN_RECONNECT_MAX,
    UPLINK_TIMEOUT_S as MAIN_UPLINK_TIMEOUT,
)


class TestUplinkLatency(unittest.TestCase):

    def test_constants_defined(self):
        self.assertEqual(UPLINK_TIMEOUT_S, 5.0)
        self.assertEqual(RECONNECT_BASE_S, 0.5)
        self.assertEqual(RECONNECT_MAX_S, 5.0)
        self.assertEqual(UPLINK_HISTORY_N, 100)

        self.assertEqual(MAIN_RECONNECT_BASE, 0.5)
        self.assertEqual(MAIN_RECONNECT_MAX, 5.0)
        self.assertEqual(MAIN_UPLINK_TIMEOUT, 5.0)

    def test_backoff_growth_bounded_by_max(self):
        backoff = RECONNECT_BASE_S
        for _ in range(10):
            backoff = min(backoff * 2, RECONNECT_MAX_S)
        self.assertEqual(backoff, 5.0)


if __name__ == "__main__":
    unittest.main()
