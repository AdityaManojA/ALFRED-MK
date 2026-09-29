"""
tests/market/test_market_sentry.py — Comprehensive test suite for Market Sentry.
Covers:
  - Provider quote parsing and normalizations
  - In-memory TTL caching and rate-limit backoff logic
  - Alert rules (threshold above/below with hysteresis, percentage delta cooling)
  - Sentry MONITOR parser integration for market clauses
  - Watchlist store atomic persistence
  - market_sentry action handler execution
"""
import json
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from actions.market_sentry import market_sentry
from core.market.provider import MarketProvider, Quote
from core.market.rules import AlertRule, RuleType
from core.market.watchlist import WatchItem, WatchlistManager
from core.sentry.monitor.parser import parse_monitoring_request
from core.sentry.monitor.targets.market import MarketTarget


class TestMarketSentryCore(unittest.TestCase):
    def setUp(self):
        self.provider = MarketProvider()
        self.provider.clear_cache()
        self.test_watchlist_path = Path("data/test_watchlist.json")
        if self.test_watchlist_path.exists():
            self.test_watchlist_path.unlink()
        self.watchlist_mgr = WatchlistManager(path=self.test_watchlist_path)

    def tearDown(self):
        if self.test_watchlist_path.exists():
            self.test_watchlist_path.unlink()

    def test_symbol_normalization(self):
        """Conversational names and crypto tickers normalize to Yahoo symbols."""
        self.assertEqual(MarketProvider.normalize_symbol("Apple"), "AAPL")
        self.assertEqual(MarketProvider.normalize_symbol("Nvidia"), "NVDA")
        self.assertEqual(MarketProvider.normalize_symbol("Bitcoin"), "BTC-USD")
        self.assertEqual(MarketProvider.normalize_symbol("BTC"), "BTC-USD")
        self.assertEqual(MarketProvider.normalize_symbol("S&P 500"), "^GSPC")
        self.assertEqual(MarketProvider.normalize_symbol("Gold"), "GC=F")

    def test_quote_caching(self):
        """Provider returns cached quote within TTL without issuing network requests."""
        mock_quote = Quote(symbol="NVDA", price=142.50, change_pct=2.1, currency="USD")
        self.provider._cache["NVDA"] = (time.monotonic(), mock_quote)

        q = self.provider.get_quote("NVDA")
        self.assertIsNotNone(q)
        self.assertEqual(q.price, 142.50)
        self.assertEqual(q.change_pct, 2.1)

    def test_rate_limit_backoff(self):
        """Encountering HTTP 429 engages exponential backoff."""
        exc = Exception("HTTP Error 429: Too Many Requests")
        self.provider._handle_error(exc)
        self.assertEqual(self.provider.status, "RATE_LIMITED")
        self.assertGreater(self.provider._backoff_until, time.monotonic())

    def test_threshold_alert_with_hysteresis(self):
        """Threshold rule fires once and resets only after price falls below hysteresis margin."""
        rule = AlertRule(rule_type=RuleType.THRESHOLD_ABOVE, threshold_value=140.0)

        # 1. Price at 138 (Below threshold) -> No alert
        q1 = Quote(symbol="NVDA", price=138.0, change_pct=-0.5, display_name="Nvidia")
        alert, msg = rule.evaluate(q1)
        self.assertFalse(alert)

        # 2. Price at 140.5 (Crosses above) -> Alert fires!
        q2 = Quote(symbol="NVDA", price=140.5, change_pct=1.8, display_name="Nvidia")
        alert, msg = rule.evaluate(q2)
        self.assertTrue(alert)
        self.assertIn("crossed above 140.00", msg)

        # 3. Price still above threshold (141.0) -> Does not double-alert
        q3 = Quote(symbol="NVDA", price=141.0, change_pct=2.2, display_name="Nvidia")
        alert, msg = rule.evaluate(q3)
        self.assertFalse(alert)

        # 4. Price dips slightly to 139.8 (within 0.5% hysteresis band) -> Still disarmed
        q4 = Quote(symbol="NVDA", price=139.8, change_pct=1.2, display_name="Nvidia")
        alert, msg = rule.evaluate(q4)
        self.assertFalse(alert)

        # 5. Price dips to 138.0 (below 140 * 0.995 = 139.3) -> Re-arms
        q5 = Quote(symbol="NVDA", price=138.0, change_pct=-0.2, display_name="Nvidia")
        alert, msg = rule.evaluate(q5)
        self.assertFalse(alert)
        self.assertTrue(rule.armed)

    def test_watchlist_store_atomic_persistence(self):
        """Watchlist items save and load from disk atomically."""
        ok, msg, item = self.watchlist_mgr.add_watch("AAPL", RuleType.THRESHOLD_ABOVE, 230.0)
        self.assertTrue(ok)
        self.assertIsNotNone(item)

        loaded = self.watchlist_mgr.load_all()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].symbol, "AAPL")
        self.assertEqual(loaded[0].threshold_value, 230.0)

        ok_rm, msg_rm = self.watchlist_mgr.remove_watch("AAPL")
        self.assertTrue(ok_rm)
        self.assertEqual(len(self.watchlist_mgr.load_all()), 0)

    def test_sentry_monitor_parser_market_clause(self):
        """Natural language clauses for market watches instantiate MarketTarget."""
        targets = parse_monitoring_request("watch NVDA above 145 and tell me if BTC drops 5 percent")
        self.assertEqual(len(targets), 2)
        self.assertIsInstance(targets[0], MarketTarget)
        self.assertEqual(targets[0].symbol, "NVDA")
        self.assertEqual(targets[0].rule.threshold_value, 145.0)

        self.assertIsInstance(targets[1], MarketTarget)
        self.assertEqual(targets[1].symbol, "BTC-USD")
        self.assertEqual(targets[1].rule.threshold_value, 5.0)

    def test_market_sentry_action_summary_and_quote(self):
        """market_sentry action returns formatted responses."""
        with patch.object(MarketProvider, "get_quote") as mock_get:
            mock_get.return_value = Quote(
                symbol="NVDA",
                price=141.25,
                change_pct=2.4,
                currency="USD",
                display_name="Nvidia",
            )
            res = market_sentry({"action": "quote", "symbol": "NVDA"})
            self.assertIn("Nvidia is at $141.25", res)
            self.assertIn("up 2.4%", res)


if __name__ == "__main__":
    unittest.main()
