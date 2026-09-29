"""
actions/market_sentry.py — Action handler for financial market queries, watchlist, and alerts.
Auto-discovered by core/action_loader.py as 'market_sentry'.
"""
from __future__ import annotations

from core.market.provider import MarketProvider, Quote
from core.market.rules import AlertRule, RuleType
from core.market.watchlist import WatchlistManager
from core.sentry.mode_manager import get_sentry_mode_manager
from core.sentry.monitor.controller import MonitorController
from core.sentry.monitor.targets.market import MarketTarget


def market_sentry(
    parameters: dict,
    player=None,
    speak=None,
    session_memory=None,
) -> str:
    """Executes market action (quote, watch, unwatch, list, summary)."""
    action = str(parameters.get("action", "summary")).lower().strip()
    symbol = str(parameters.get("symbol", "")).strip()
    threshold = parameters.get("threshold")
    pct_delta = parameters.get("pct_delta")

    provider = MarketProvider.instance()
    watchlist_mgr = WatchlistManager.instance()

    # 1. MARKET SUMMARY / INDICES UPDATE
    if action in ("summary", "overview", "indices"):
        sp = provider.get_quote("^GSPC")
        nasdaq = provider.get_quote("^IXIC")
        btc = provider.get_quote("BTC-USD")

        parts = []
        if sp:
            s_dir = "up" if sp.change_pct >= 0 else "down"
            parts.append(f"S&P 500 is {s_dir} {abs(sp.change_pct):.1f}% at {sp.price:,.0f}")
        if nasdaq:
            n_dir = "up" if nasdaq.change_pct >= 0 else "down"
            parts.append(f"Nasdaq is {n_dir} {abs(nasdaq.change_pct):.1f}%")
        if btc:
            b_dir = "up" if btc.change_pct >= 0 else "down"
            b_p = f"${btc.price/1000.0:.1f}k" if btc.price >= 1000 else f"${btc.price:.0f}"
            parts.append(f"Bitcoin is {b_dir} {abs(btc.change_pct):.1f}% at {b_p}")

        if parts:
            return f"Markets today, sir: {', '.join(parts)}."
        return "Market data is currently unavailable, sir."

    # 2. GET SINGLE QUOTE
    if action in ("quote", "check", "price"):
        if not symbol:
            return "Which stock or crypto would you like me to check, sir?"
        quote = provider.get_quote(symbol)
        if not quote:
            return f"Could not retrieve quote for '{symbol}', sir."

        direction = "up" if quote.change_pct >= 0 else "down"
        name = quote.display_name or quote.symbol
        if quote.price >= 1000.0 and "BTC" in quote.symbol:
            p_str = f"${quote.price/1000.0:.1f}k"
        elif quote.price >= 1.0:
            p_str = f"${quote.price:,.2f}"
        else:
            p_str = f"${quote.price:,.4f}"

        return f"{name} is at {p_str}, {direction} {abs(quote.change_pct):.1f}% today, sir."

    # 3. WATCH TICKER / SET ALERT
    if action in ("watch", "alert", "add"):
        if not symbol:
            return "Please specify a ticker symbol to watch, sir."

        # Rule resolution
        norm_sym = MarketProvider.normalize_symbol(symbol)
        quote = provider.get_quote(norm_sym)
        curr_price = quote.price if quote else 0.0

        if threshold is not None:
            thresh_val = float(threshold)
            r_type = RuleType.THRESHOLD_ABOVE if thresh_val >= curr_price else RuleType.THRESHOLD_BELOW
        elif pct_delta is not None:
            thresh_val = float(pct_delta)
            r_type = RuleType.PCT_DELTA
        else:
            # Default to ±5% intraday move alert
            thresh_val = 5.0
            r_type = RuleType.PCT_DELTA

        rule = AlertRule(rule_type=r_type, threshold_value=thresh_val)
        ok, msg, item = watchlist_mgr.add_watch(symbol, r_type, thresh_val, display_name=quote.display_name if quote else symbol)

        if ok and item:
            # Also register live target under Sentry MONITOR
            target = MarketTarget(target_id=item.watch_id, symbol=item.symbol, rule=rule, name=item.display_name)
            ctrl = MonitorController.instance()
            ctrl.scheduler.add_target(target)
            get_sentry_mode_manager().request_mode("MONITOR")

        return msg

    # 4. UNWATCH / REMOVE
    if action in ("unwatch", "remove", "stop"):
        if not symbol:
            return "Which ticker shall I remove from your watchlist, sir?"
        ok, msg = watchlist_mgr.remove_watch(symbol)
        ctrl = MonitorController.instance()
        # Remove matching target from active scheduler
        for t in ctrl.scheduler.list_targets():
            if getattr(t, "symbol", "") == MarketProvider.normalize_symbol(symbol) or t.name == symbol:
                ctrl.scheduler.remove_target(t.target_id)
        return msg

    # 5. LIST WATCHLIST
    if action in ("list", "watchlist", "status"):
        watches = watchlist_mgr.list_active()
        if not watches:
            return "Your market watchlist is currently empty, sir."

        lines = []
        for w in watches:
            q = provider.get_quote(w.symbol)
            p_str = f"${q.price:,.2f}" if q else "—"
            c_str = f"({q.change_pct:+.1f}%)" if q else ""
            lines.append(f"{w.symbol}: {p_str} {c_str}")

        return f"Currently watching {len(watches)} assets, sir: " + ", ".join(lines) + "."

    return f"Unknown market action '{action}'. Options: summary, quote, watch, unwatch, list."


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "market_sentry",
    "description": (
        "Tracks financial markets, stock quotes, crypto prices, major indices (S&P 500, Nasdaq, Bitcoin), "
        "and manages price threshold/delta alerts under Sentry MONITOR. "
        "Use when the user asks: 'market update', 'how are markets doing', 'how is NVDA doing', 'check Apple price', "
        "'watch NVDA above 140', 'alert me if TSLA drops 5 percent', 'stop watching BTC', or 'what am I watching'."
    ),
    "scheduling": "WHEN_IDLE",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "summary | quote | watch | unwatch | list (default: summary)",
            },
            "symbol": {
                "type": "STRING",
                "description": "Ticker symbol or asset name (e.g. 'NVDA', 'AAPL', 'BTC', 'TSLA', 'SPY', 'Gold').",
            },
            "threshold": {
                "type": "NUMBER",
                "description": "Target price threshold for crossing alerts (e.g. 140.0).",
            },
            "pct_delta": {
                "type": "NUMBER",
                "description": "Percentage move threshold for delta alerts (e.g. 5.0 for ±5%).",
            },
        },
        "required": [],
    },
    "handler": market_sentry,
}
