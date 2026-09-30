"""
core/market/watchlist.py — Atomic persistence and management for market watchlist.
Saves watches to data/watchlist.json (symbol, rule, created_at, active).
Caps active items to MAX_WATCHES = 15.
"""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, List, Optional

from core.market.provider import MarketProvider
from core.market.rules import AlertRule, RuleType

MAX_WATCHES: int = 15
DEFAULT_WATCHLIST_PATH = Path("data/watchlist.json")


@dataclass
class WatchItem:
    watch_id: str
    symbol: str
    rule_type: str
    threshold_value: float
    created_at: float
    active: bool = True
    display_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WatchItem:
        return cls(
            watch_id=str(data.get("watch_id", "")),
            symbol=str(data.get("symbol", "")),
            rule_type=str(data.get("rule_type", "threshold_above")),
            threshold_value=float(data.get("threshold_value", 0.0)),
            created_at=float(data.get("created_at", time.time())),
            active=bool(data.get("active", True)),
            display_name=str(data.get("display_name", "")),
        )


class WatchlistManager:
    """Manages persistent watchlist store with atomic file writes."""

    _instance: Optional[WatchlistManager] = None
    _instance_lock = threading.Lock()

    @classmethod
    def instance(cls, path: Path | str = DEFAULT_WATCHLIST_PATH) -> WatchlistManager:
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls(path)
            return cls._instance

    def __init__(self, path: Path | str = DEFAULT_WATCHLIST_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def load_all(self) -> list[WatchItem]:
        """Load all watchlist items from disk."""
        with self._lock:
            if not self.path.exists():
                return []
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return [WatchItem.from_dict(d) for d in data if isinstance(d, dict)]
            except Exception as e:
                print(f"[WatchlistManager] Failed to load {self.path}: {e}")
            return []

    def save_all(self, items: list[WatchItem]) -> None:
        """Atomically persist items to disk."""
        with self._lock:
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            payload = [item.to_dict() for item in items]
            temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(temporary, self.path)

    def add_watch(
        self,
        symbol: str,
        rule_type: RuleType | str,
        threshold_value: float,
        display_name: str = "",
    ) -> tuple[bool, str, WatchItem | None]:
        """Add a ticker watch to the persistent list."""
        with self._lock:
            items = self.load_all()
            norm_sym = MarketProvider.normalize_symbol(symbol)

            # Check capacity
            active_items = [i for i in items if i.active]
            if len(active_items) >= MAX_WATCHES:
                return False, f"Watchlist is at maximum capacity ({MAX_WATCHES} items), sir.", None

            # Check if identical watch already active
            r_str = rule_type.value if isinstance(rule_type, RuleType) else str(rule_type)
            for it in active_items:
                if it.symbol == norm_sym and it.rule_type == r_str and abs(it.threshold_value - threshold_value) < 1e-4:
                    return False, f"Watch for {norm_sym} is already active, sir.", it

            import uuid
            watch_id = f"mkt_{uuid.uuid4().hex[:8]}"
            new_item = WatchItem(
                watch_id=watch_id,
                symbol=norm_sym,
                rule_type=r_str,
                threshold_value=threshold_value,
                created_at=time.time(),
                active=True,
                display_name=display_name or norm_sym,
            )
            items.append(new_item)
            self.save_all(items)
            return True, f"Watching {norm_sym}, sir.", new_item

    def remove_watch(self, symbol_or_id: str) -> tuple[bool, str]:
        """Remove a watch by symbol or watch_id."""
        with self._lock:
            items = self.load_all()
            target = (symbol_or_id or "").strip().upper()
            norm_sym = MarketProvider.normalize_symbol(target)

            updated = []
            removed_count = 0
            for it in items:
                if it.watch_id == symbol_or_id or it.symbol == norm_sym or it.symbol == target:
                    removed_count += 1
                else:
                    updated.append(it)

            if removed_count > 0:
                self.save_all(updated)
                return True, f"Removed {symbol_or_id} from your watchlist, sir."
            return False, f"Could not find {symbol_or_id} in your active watchlist, sir."

    def list_active(self) -> list[WatchItem]:
        """Return list of all currently active watches."""
        return [it for it in self.load_all() if it.active]
