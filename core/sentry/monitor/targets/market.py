"""
core/sentry/monitor/targets/market.py — Market monitoring target for Sentry MONITOR.
Integrates with MarketProvider and AlertRule to watch tickers and trigger spoken alerts.
"""
from __future__ import annotations

import time
from typing import Optional

from core.market.provider import (
    MARKET_OFFHOURS_POLL_INTERVAL_S,
    MARKET_POLL_INTERVAL_S,
    MarketProvider,
    Quote,
)
from core.market.rules import AlertRule, RuleType
from core.sentry.monitor.targets.base import MonitorTarget, TargetStatus


class MarketTarget(MonitorTarget):
    """
    Sentry MONITOR target for watching stock, ETF, crypto, or index prices.
    Off-thread polling, rate-limit tolerant, and hysteresis-backed.
    """

    def __init__(
        self,
        target_id: str,
        symbol: str,
        rule: AlertRule,
        name: str | None = None,
        provider: MarketProvider | None = None,
    ) -> None:
        self.symbol = MarketProvider.normalize_symbol(symbol)
        display_name = name or f"Market {self.symbol}"
        super().__init__(target_id=target_id, name=display_name, interval_s=MARKET_POLL_INTERVAL_S)

        self.rule = rule
        self.provider = provider or MarketProvider.instance()
        self.last_quote: Quote | None = None
        self._prev_price: float | None = None

    def describe(self) -> str:
        r_type = self.rule.rule_type
        sym = self.symbol.replace("-USD", "")
        if r_type == RuleType.THRESHOLD_ABOVE:
            return f"{sym} > ${self.rule.threshold_value:,.2f}"
        elif r_type == RuleType.THRESHOLD_BELOW:
            return f"{sym} < ${self.rule.threshold_value:,.2f}"
        elif r_type == RuleType.PCT_DELTA:
            return f"{sym} ±{abs(self.rule.threshold_value):.1f}%"
        return f"Watch {sym}"

    def poll(self) -> TargetStatus:
        """Fetch current quote and evaluate alert rules."""
        now = time.monotonic()
        self.last_poll_t = now

        quote = self.provider.get_quote(self.symbol)
        if not quote:
            if self.provider.status == "RATE_LIMITED":
                self.status = TargetStatus.ERROR
            return self.status

        # Dynamic interval adjustment based on market state
        if quote.market_state in ("REGULAR", "PRE_MARKET", "POST_MARKET"):
            self.interval_s = MARKET_POLL_INTERVAL_S
        else:
            self.interval_s = MARKET_OFFHOURS_POLL_INTERVAL_S

        should_alert, alert_msg = self.rule.evaluate(quote, self._prev_price)
        self._prev_price = quote.price
        self.last_quote = quote

        if should_alert:
            self._pending_alert = alert_msg
            self.status = TargetStatus.ALERTED
            # If threshold alert fired, mark finished or keep armed per rule config
            if self.rule.rule_type in (RuleType.THRESHOLD_ABOVE, RuleType.THRESHOLD_BELOW):
                # Target remains active but armed becomes False until hysteresis resets
                self.status = TargetStatus.RUNNING
        else:
            self.status = TargetStatus.RUNNING

        return self.status
