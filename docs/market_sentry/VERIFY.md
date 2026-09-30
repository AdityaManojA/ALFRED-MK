# Market Sentry (TICKER + THRESHOLD + BRIEF) — Verification & Acceptance Report

## 1. Scope & Implementation Overview
- **Market Data Provider (`core/market/provider.py`)**:
  - Yahoo Finance v8 chart API backend with user-agent rotation and zero extra third-party pip dependencies.
  - In-memory TTL caching (`QUOTE_CACHE_TTL_S = 45.0`) to avoid duplicate requests.
  - Adaptive exponential backoff on HTTP 429 rate limits (`BACKOFF_BASE_S = 30.0`, `BACKOFF_MAX_S = 600.0`).
  - Conversational ticker normalization (`Apple` $\rightarrow$ `AAPL`, `Bitcoin` $\rightarrow$ `BTC-USD`, `Gold` $\rightarrow$ `GC=F`, `S&P 500` $\rightarrow$ `^GSPC`).
- **Sentry MONITOR Integration (`core/sentry/monitor/targets/market.py` & `core/market/rules.py`)**:
  - Pluggable `MarketTarget` inheriting `MonitorTarget`.
  - Alert rules: `THRESHOLD_ABOVE`, `THRESHOLD_BELOW` with 0.5% hysteresis (`HYSTERESIS_PCT = 0.5`) to eliminate noisy re-alerts, and `PCT_DELTA` with 30-minute cooling (`ALERT_COOLDOWN_S = 1800.0`).
  - Sentry monitor clause parser (`core/sentry/monitor/parser.py`) converts natural voice prompts like `"watch NVDA above 140"` directly into active `MarketTarget`s.
- **Watchlist Store & Scheduled Daily Brief**:
  - `WatchlistManager` (`core/market/watchlist.py`) saves watches to `data/watchlist.json` using atomic replace writes with `MAX_WATCHES = 15`.
  - Integrated market summary seamlessly into `daily_brief` (`actions/daily_brief.py`) without blocking other brief subroutines.
- **HUD Presence**:
  - `DataGridWorker` in `core/hud/datagrid/providers.py` dynamically cycles through active market watchlist items (`HUD_CYCLE_S = 8`) in place of ports when watches exist.
- **Voice Routing & Action Tool**:
  - `market_sentry` action tool in `actions/market_sentry.py` handles `summary`, `quote`, `watch`, `unwatch`, and `list`.
  - Voice routing rules wired into `core/prompt.txt`.

---

## 2. Automated Test Results
- Test suite: `tests/market/test_market_sentry.py` (7 tests, 100% pass):
  - `test_symbol_normalization`: PASS (Normalizes common names, crypto, and commodity futures)
  - `test_quote_caching`: PASS (Serves quotes within TTL without network requests)
  - `test_rate_limit_backoff`: PASS (HTTP 429 engages exponential backoff and DEGRADED state)
  - `test_threshold_alert_with_hysteresis`: PASS (Fires once on threshold crossing, stays disarmed within 0.5% hysteresis, resets when price dips below margin)
  - `test_watchlist_store_atomic_persistence`: PASS (Atomic file writes to `data/watchlist.json`)
  - `test_sentry_monitor_parser_market_clause`: PASS (Extracts symbols and thresholds from natural language)
  - `test_market_sentry_action_summary_and_quote`: PASS (Formats human-readable, rounded voice summaries)
