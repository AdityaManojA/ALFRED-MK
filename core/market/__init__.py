"""
core/market — Financial market tracking, quotes, alert rules, and watchlist management.
"""
from core.market.provider import MarketProvider, Quote
from core.market.rules import AlertRule, RuleType
from core.market.watchlist import WatchItem, WatchlistManager

__all__ = [
    "AlertRule",
    "MarketProvider",
    "Quote",
    "RuleType",
    "WatchItem",
    "WatchlistManager",
]
