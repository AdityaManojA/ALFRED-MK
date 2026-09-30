"""
core/market/provider.py — Provider-agnostic market quote fetcher and cache.
Uses Yahoo Finance v8 chart API as default with zero extra pip dependencies.
Handles ticker normalization, in-memory TTL caching, and exponential rate-limit backoff.
"""
from __future__ import annotations

import json
import logging
import os
import random
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

# ── Named Constants ──────────────────────────────────────────────────────────
QUOTE_CACHE_TTL_S: float = 45.0
MARKET_POLL_INTERVAL_S: float = 60.0
MARKET_OFFHOURS_POLL_INTERVAL_S: float = 300.0
BACKOFF_BASE_S: float = 30.0
BACKOFF_MAX_S: float = 600.0
HTTP_TIMEOUT_S: float = 6.0

_USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0",
)

_COMMON_NAME_MAP = {
    "APPLE": "AAPL",
    "NVIDIA": "NVDA",
    "MICROSOFT": "MSFT",
    "TESLA": "TSLA",
    "AMAZON": "AMZN",
    "GOOGLE": "GOOGL",
    "ALPHABET": "GOOGL",
    "META": "META",
    "FACEBOOK": "META",
    "BITCOIN": "BTC-USD",
    "BTC": "BTC-USD",
    "ETHEREUM": "ETH-USD",
    "ETH": "ETH-USD",
    "SOLANA": "SOL-USD",
    "SOL": "SOL-USD",
    "S&P 500": "^GSPC",
    "S&P": "^GSPC",
    "SP500": "^GSPC",
    "SPY": "SPY",
    "NASDAQ": "^IXIC",
    "QQQ": "QQQ",
    "DOW": "^DJI",
    "DOW JONES": "^DJI",
    "GOLD": "GC=F",
    "OIL": "CL=F",
    "CRUDE": "CL=F",
    "SILVER": "SI=F",
}

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Quote:
    """Standardized financial market quote."""
    symbol: str
    price: float
    change_pct: float
    currency: str = "USD"
    market_state: str = "REGULAR"  # PRE | REGULAR | POST | CLOSED
    timestamp: float = 0.0
    display_name: str = ""


class MarketProvider:
    """
    Market quote provider with TTL caching, ticker normalization,
    and adaptive backoff on rate limits.
    """
    _instance: Optional[MarketProvider] = None

    @classmethod
    def instance(cls) -> MarketProvider:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, Quote]] = {}
        self._backoff_until: float = 0.0
        self._backoff_step: int = 0
        self._status: str = "OK"  # "OK" | "DEGRADED" | "RATE_LIMITED"

    @property
    def status(self) -> str:
        return self._status

    @staticmethod
    def normalize_symbol(raw_symbol: str) -> str:
        """Normalize conversational name or ticker to Yahoo Finance symbol."""
        cleaned = (raw_symbol or "").strip().upper()
        if not cleaned:
            return "^GSPC"
        if cleaned in _COMMON_NAME_MAP:
            return _COMMON_NAME_MAP[cleaned]
        # Common crypto ticker missing -USD
        if cleaned in ("BTC", "ETH", "SOL", "DOGE", "XRP", "ADA"):
            return f"{cleaned}-USD"
        return cleaned

    def get_quote(self, symbol: str, force_refresh: bool = False) -> Quote | None:
        """Fetch quote for symbol with TTL caching and rate limit protection."""
        sym = self.normalize_symbol(symbol)
        now = time.monotonic()

        # Check in-memory cache
        if not force_refresh and sym in self._cache:
            ts, cached_quote = self._cache[sym]
            if now - ts < QUOTE_CACHE_TTL_S:
                return cached_quote

        # Check backoff gate
        if now < self._backoff_until:
            _LOGGER.debug("[MarketProvider] In backoff window (%.1fs left); skipping fetch for %s",
                          self._backoff_until - now, sym)
            # Return stale cache if available
            if sym in self._cache:
                return self._cache[sym][1]
            return None

        # Fetch from Yahoo Finance chart v8 API
        try:
            quote = self._fetch_yahoo_quote(sym)
            if quote:
                self._cache[sym] = (now, quote)
                # Successful response resets backoff
                self._backoff_step = 0
                self._status = "OK"
                return quote
        except Exception as e:
            self._handle_error(e)
            if sym in self._cache:
                return self._cache[sym][1]

        return None

    def _fetch_yahoo_quote(self, symbol: str) -> Quote | None:
        """Fetch quote from public Yahoo Finance v8 chart API."""
        encoded_sym = urllib.parse.quote(symbol)
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_sym}?interval=1d&range=1d"
        headers = {
            "User-Agent": random.choice(_USER_AGENTS),
            "Accept": "application/json",
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))

        chart = data.get("chart", {})
        results = chart.get("result")
        if not results:
            error = chart.get("error", {})
            _LOGGER.warning("[MarketProvider] Yahoo chart returned error for %s: %s", symbol, error)
            return None

        meta = results[0].get("meta", {})
        price = float(meta.get("regularMarketPrice") or 0.0)
        prev_close = float(meta.get("chartPreviousClose") or meta.get("previousClose") or price)
        change_pct = ((price - prev_close) / prev_close * 100.0) if prev_close > 0 else 0.0
        currency = str(meta.get("currency") or "USD")
        market_state = str(meta.get("tradingPeriod", "REGULAR")).upper()
        if "REGULAR" in market_state:
            market_state = "REGULAR"
        elif "PRE" in market_state:
            market_state = "PRE_MARKET"
        elif "POST" in market_state:
            market_state = "POST_MARKET"
        else:
            market_state = "CLOSED"

        display_name = str(meta.get("shortName") or meta.get("symbol") or symbol)

        return Quote(
            symbol=symbol,
            price=round(price, 4 if price < 1.0 else 2),
            change_pct=round(change_pct, 2),
            currency=currency,
            market_state=market_state,
            timestamp=time.time(),
            display_name=display_name,
        )

    def _handle_error(self, exc: Exception) -> None:
        """Exponential backoff on 429 / network errors."""
        now = time.monotonic()
        is_rate_limit = "429" in str(exc) or (hasattr(exc, "code") and exc.code == 429)
        if is_rate_limit:
            self._backoff_step = min(5, self._backoff_step + 1)
            backoff_duration = min(BACKOFF_MAX_S, BACKOFF_BASE_S * (2 ** (self._backoff_step - 1)))
            self._backoff_until = now + backoff_duration
            self._status = "RATE_LIMITED"
            _LOGGER.warning("[MarketProvider] HTTP 429 Rate Limit encountered. Backing off for %.0fs", backoff_duration)
        else:
            self._status = "DEGRADED"
            _LOGGER.debug("[MarketProvider] Quote fetch error: %s", exc)

    def clear_cache(self) -> None:
        """Clear memory cache for testing or manual reset."""
        self._cache.clear()
        self._backoff_until = 0.0
        self._backoff_step = 0
        self._status = "OK"
