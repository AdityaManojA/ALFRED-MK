"""
core/market/rules.py — Alert rule definitions and evaluation logic for Market Sentry.
Supports price threshold crossing with hysteresis, percentage moves, and state changes.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from core.market.provider import Quote

# ── Named Constants ──────────────────────────────────────────────────────────
HYSTERESIS_PCT: float = 0.5        # 0.5% hysteresis band to prevent jitter alerts
ALERT_COOLDOWN_S: float = 1800.0   # 30-minute cooldown for percentage delta alerts


class RuleType(str, Enum):
    THRESHOLD_ABOVE = "threshold_above"
    THRESHOLD_BELOW = "threshold_below"
    PCT_DELTA = "pct_delta"
    STATUS_CHANGE = "status_change"


@dataclass
class AlertRule:
    """Configured market alert condition."""
    rule_type: RuleType
    threshold_value: float = 0.0
    active: bool = True
    last_triggered_t: float = 0.0
    armed: bool = True  # Used for hysteresis reset

    def evaluate(self, quote: Quote, previous_price: float | None = None) -> tuple[bool, str]:
        """
        Evaluate if quote triggers this alert rule.
        Returns (should_alert, spoken_message).
        """
        if not self.active:
            return False, ""

        now = time.monotonic()

        # 1. THRESHOLD ABOVE
        if self.rule_type == RuleType.THRESHOLD_ABOVE:
            if quote.price >= self.threshold_value:
                if self.armed:
                    self.armed = False
                    self.last_triggered_t = now
                    # Format clean currency representation
                    p_str = f"{quote.price:,.2f}" if quote.price >= 1.0 else f"{quote.price:,.4f}"
                    t_str = f"{self.threshold_value:,.2f}" if self.threshold_value >= 1.0 else f"{self.threshold_value:,.4f}"
                    name = quote.display_name or quote.symbol
                    msg = f"Sir, {name} crossed above {t_str} dollars, currently {p_str}."
                    return True, msg
            else:
                # Reset armed status if price falls below threshold by hysteresis margin
                reset_margin = self.threshold_value * (1.0 - HYSTERESIS_PCT / 100.0)
                if quote.price < reset_margin:
                    self.armed = True

        # 2. THRESHOLD BELOW
        elif self.rule_type == RuleType.THRESHOLD_BELOW:
            if quote.price <= self.threshold_value:
                if self.armed:
                    self.armed = False
                    self.last_triggered_t = now
                    p_str = f"{quote.price:,.2f}" if quote.price >= 1.0 else f"{quote.price:,.4f}"
                    t_str = f"{self.threshold_value:,.2f}" if self.threshold_value >= 1.0 else f"{self.threshold_value:,.4f}"
                    name = quote.display_name or quote.symbol
                    msg = f"Sir, {name} dropped below {t_str} dollars, currently {p_str}."
                    return True, msg
            else:
                # Reset armed status if price climbs above threshold by hysteresis margin
                reset_margin = self.threshold_value * (1.0 + HYSTERESIS_PCT / 100.0)
                if quote.price > reset_margin:
                    self.armed = True

        # 3. PERCENTAGE DELTA (Intraday or interval move)
        elif self.rule_type == RuleType.PCT_DELTA:
            if abs(quote.change_pct) >= abs(self.threshold_value):
                if now - self.last_triggered_t >= ALERT_COOLDOWN_S:
                    self.last_triggered_t = now
                    direction = "up" if quote.change_pct > 0 else "down"
                    abs_pct = abs(quote.change_pct)
                    name = quote.display_name or quote.symbol
                    msg = f"{name} is {direction} {abs_pct:.1f}% today, sir."
                    return True, msg

        return False, ""
