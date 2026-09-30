"""
tests/test_tool_runner.py — Unit tests for tool timeout bounds, fallbacks, and client cache.
"""

from __future__ import annotations

import asyncio
import unittest

from core.tools.runner import (
    execute_bounded_tool,
    CLIENT_CACHE,
    TOOL_TIMEOUT_S,
    TOOL_INIT_CACHE_TTL_S,
    FAST_TOOL_PLACEHOLDERS,
)


class TestToolRunner(unittest.TestCase):

    def test_constants_defined(self):
        self.assertEqual(TOOL_TIMEOUT_S, 3.0)
        self.assertEqual(TOOL_INIT_CACHE_TTL_S, 3600)

    def test_client_cache_ttl(self):
        CLIENT_CACHE.clear()
        CLIENT_CACHE.set("dummy", {"client": 123})
        self.assertEqual(CLIENT_CACHE.get("dummy"), {"client": 123})
        self.assertIsNone(CLIENT_CACHE.get("nonexistent"))

    def test_fast_tool_success(self):
        async def mock_fast_tool():
            await asyncio.sleep(0.01)
            return "weather is sunny"

        result, metrics = asyncio.run(
            execute_bounded_tool("weather_report", mock_fast_tool(), timeout_s=1.0)
        )
        self.assertEqual(result, "weather is sunny")
        self.assertFalse(metrics.timed_out)
        self.assertLess(metrics.total_ms, 500.0)

    def test_slow_tool_fallback_placeholder(self):
        async def mock_slow_tool():
            await asyncio.sleep(0.5)
            return "completed after 500ms"

        # Set tight timeout to trigger fallback placeholder
        result, metrics = asyncio.run(
            execute_bounded_tool("weather_report", mock_slow_tool(), timeout_s=0.05)
        )
        self.assertEqual(result, FAST_TOOL_PLACEHOLDERS["weather_report"])
        self.assertTrue(metrics.timed_out)


if __name__ == "__main__":
    unittest.main()
