# PHASE 0 RECONNAISSANCE NOTES — MARKET SENTRY

## 1. Sentry Monitor Target Interface
- `MonitorTarget` abstract base class is defined in [`core/sentry/monitor/targets/base.py`](file:///d:/Projects/Alfred-Mark-V/core/sentry/monitor/targets/base.py) (AST nodes: `MonitorTarget`, `TargetStatus`, `AlertSeverity`, `TargetAlert`).
- Target interface methods:
  - `describe() -> str`: Terse human-readable representation of the target.
  - `poll() -> TargetStatus`: Execution on target's cadence; updates internal state and `self.status`.
  - `should_alert() -> tuple[bool, str]`: Checks `self._pending_alert`, returns alert flag and speech prompt, and resets `_pending_alert`.
  - `close() -> None`: Cleans up handles and sockets.
- Sentry Monitor Controller & Parser:
  - [`core/sentry/monitor/controller.py`](file:///d:/Projects/Alfred-Mark-V/core/sentry/monitor/controller.py): Coordinates scheduler, speech announcements, and status updates.
  - [`core/sentry/monitor/parser.py`](file:///d:/Projects/Alfred-Mark-V/core/sentry/monitor/parser.py): Converts natural language clauses into `MonitorTarget` instances (`WindowTitleTarget`, `FileLogTarget`, `ProcessTarget`, `CommandTarget`, etc.).

## 2. Persistence Layer
- Sentry/Scheduler persistence uses atomic JSON write patterns via [`core/scheduler/ledger.py`](file:///d:/Projects/Alfred-Mark-V/core/scheduler/ledger.py) (`Ledger` class): writes to `.tmp` file, then invokes `os.replace` under an `RLock`.
- For Market Sentry, `WatchlistManager` will manage [`data/watchlist.json`](file:///d:/Projects/Alfred-Mark-V/data/watchlist.json) using the exact same atomic write pattern (`MAX_WATCHES = 15`).

## 3. Daily Brief & Market Bell Integration
- `daily_brief` action is implemented in [`actions/daily_brief.py`](file:///d:/Projects/Alfred-Mark-V/actions/daily_brief.py) (`daily_brief()` function).
- The daily brief collects greeting, weather, unread Gmails, scheduled tasks, and system metrics. A market summary section can cleanly slot into `daily_brief()` right alongside the news and reminders.
- Market Bell brief: Scheduled for 09:30 ET and 16:00 ET via the scheduler or direct bell hooks.

## 4. HUD Integration (Data Grid & Status Line)
- The 2x2 developer data grid is implemented in [`core/hud/datagrid/grid.py`](file:///d:/Projects/Alfred-Mark-V/core/hud/datagrid/grid.py) (`DeveloperDataGridWidget`) and sampled off-thread via [`core/hud/datagrid/providers.py`](file:///d:/Projects/Alfred-Mark-V/core/hud/datagrid/providers.py) (`DataGridWorker`).
- We can add a market ticker provider cycling through watched symbols (`HUD_CYCLE_S = 8`) or swapping with listening ports / telemetry cells based on active watchlist state.

## 5. Intent Routing & Conflict Prevention
- Natural language routing lives in [`core/prompt.txt`](file:///d:/Projects/Alfred-Mark-V/core/prompt.txt) and [`core/sentry/monitor/parser.py`](file:///d:/Projects/Alfred-Mark-V/core/sentry/monitor/parser.py).
- Clashes avoided:
  - `"watch process <name>"` vs `"watch <ticker> above <price>"`: Checked with ticker patterns and price comparison keywords (`above`, `below`, `drops`, `rises`, `target`).
  - Numbers in Visual HUD ("at 2:35" or "seek 30s") require player locus or video player keywords, whereas market thresholds bind to symbols (`NVDA`, `BTC`, `Apple`, `Gold`).

## 6. HTTP Provider Dependencies
- Standard library `urllib.request` is already cleanly used in [`actions/daily_brief.py`](file:///d:/Projects/Alfred-Mark-V/actions/daily_brief.py) and across the repo.
- We will use `urllib.request` with a rotating User-Agent to query Yahoo Finance v8 chart API (`https://query1.finance.yahoo.com/v8/finance/chart/{symbol}`) with fallback to Finnhub if API keys are configured in environment / `config/api_keys.json`. Zero new external package dependencies required.

---

## Proposed Package Layout
```
core/
├── market/
│   ├── __init__.py
│   ├── provider.py      # Quote fetcher, normalization, rate-limit backoff & TTL cache
│   ├── rules.py         # Threshold, Pct Delta, Status Change alert rules
│   └── watchlist.py     # WatchlistManager with atomic data/watchlist.json persistence
└── sentry/
    └── monitor/
        └── targets/
            └── market.py # MarketTarget implementing MonitorTarget
```
