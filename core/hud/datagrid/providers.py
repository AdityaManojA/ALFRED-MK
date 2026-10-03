"""
core/hud/datagrid/providers.py — Off-thread shared sampling worker for developer data grid.
Manages GIT, PORTS, TOP PROC, and SESSION token counters with zero UI lag.
"""
from __future__ import annotations

import os
import platform
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import psutil

GIT_TIMEOUT_S: float = 2.0
GIT_INTERVAL_S: float = 15.0
PORTS_INTERVAL_S: float = 20.0
PROC_INTERVAL_S: float = 12.0
SESSION_INTERVAL_S: float = 1.0
PORTS_MAX_SHOWN: int = 4

_SESSION_START: float = time.monotonic()
_SESSION_TOKENS: int = 0


def add_session_tokens(count: int) -> None:
    """Thread-safe counter increment for LLM API token consumption."""
    global _SESSION_TOKENS
    if count > 0:
        _SESSION_TOKENS += count


@dataclass
class GridDataSnapshot:
    git_text: str = "—"
    git_state: str = "dim"       # "accent" | "warn" | "dim"
    ports_text: str = "—"
    ports_state: str = "dim"
    proc_text: str = "—"
    proc_state: str = "dim"
    session_text: str = "—"
    session_state: str = "accent"


class DataGridWorker:
    """
    Background worker thread polling system metrics on per-provider intervals.
    Never blocks GUI thread.
    """
    _instance: Optional[DataGridWorker] = None
    _lock = threading.Lock()

    def __init__(self, on_update: Optional[Callable[[GridDataSnapshot], None]] = None):
        self.on_update = on_update
        self.snapshot = GridDataSnapshot()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._last_git_t: float = 0.0
        self._last_ports_t: float = 0.0
        self._last_proc_t: float = 0.0
        self._last_session_t: float = 0.0

    @classmethod
    def instance(cls, on_update: Optional[Callable[[GridDataSnapshot], None]] = None) -> DataGridWorker:
        with cls._lock:
            if cls._instance is None:
                cls._instance = DataGridWorker(on_update)
            elif on_update is not None:
                cls._instance.on_update = on_update
            return cls._instance

    def start(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, daemon=True, name="hud-datagrid-worker")
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            now = time.monotonic()
            changed = False

            # 1. Session (every 1s)
            if now - self._last_session_t >= SESSION_INTERVAL_S:
                self._last_session_t = now
                elapsed = int(now - _SESSION_START)
                h, rem = divmod(elapsed, 3600)
                m, s = divmod(rem, 60)
                tok_str = f"{_SESSION_TOKENS/1000.0:.1f}k tok" if _SESSION_TOKENS >= 1000 else f"{_SESSION_TOKENS} tok"
                self.snapshot.session_text = f"{h:02d}:{m:02d}:{s:02d} • {tok_str}"
                self.snapshot.session_state = "accent"
                changed = True

            # 2. Top Process (every 5s)
            if now - self._last_proc_t >= PROC_INTERVAL_S:
                self._last_proc_t = now
                proc_str, state = self._sample_top_proc()
                if proc_str != self.snapshot.proc_text:
                    self.snapshot.proc_text = proc_str
                    self.snapshot.proc_state = state
                    changed = True

            # 3. Git Status (every 15s)
            if now - self._last_git_t >= GIT_INTERVAL_S:
                self._last_git_t = now
                git_str, state = self._sample_git()
                if git_str != self.snapshot.git_text:
                    self.snapshot.git_text = git_str
                    self.snapshot.git_state = state
                    changed = True

            # 4. Listening Ports / Market Ticker
            if now - self._last_ports_t >= PORTS_INTERVAL_S:
                self._last_ports_t = now
                mkt_str, state = self._sample_market_or_ports()
                if mkt_str != self.snapshot.ports_text:
                    self.snapshot.ports_text = mkt_str
                    self.snapshot.ports_state = state
                    changed = True

            if changed and self.on_update:
                try:
                    self.on_update(self.snapshot)
                except Exception:
                    pass

            self._stop_event.wait(0.5)

    def _sample_market_or_ports(self) -> tuple[str, str]:
        # If watchlist has items, cycle active tickers; otherwise show ports
        try:
            from core.market.watchlist import WatchlistManager
            from core.market.provider import MarketProvider
            mgr = WatchlistManager.instance()
            watches = mgr.list_active()
            if watches:
                provider = MarketProvider.instance()
                # Cycle through watched items
                idx = int(time.monotonic() / 8.0) % len(watches)
                w = watches[idx]
                q = provider.get_quote(w.symbol)
                if q:
                    arrow = "▲" if q.change_pct >= 0 else "▼"
                    state = "accent" if q.change_pct >= 0 else "warn"
                    sym_clean = q.symbol.replace("-USD", "")
                    p_str = f"{q.price/1000:.1f}k" if q.price >= 1000 else f"{q.price:.1f}"
                    return f"{sym_clean} {p_str} {arrow}{abs(q.change_pct):.1f}%", state
        except Exception:
            pass
        return self._sample_ports()

    def _sample_git(self) -> tuple[str, str]:
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        if not (repo_root / ".git").exists():
            return "no repo", "dim"
        try:
            # Branch name
            br_proc = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=GIT_TIMEOUT_S,
            )
            if br_proc.returncode != 0:
                return "—", "dim"
            branch = br_proc.stdout.strip() or "HEAD"

            # Dirty status count
            st_proc = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=GIT_TIMEOUT_S,
            )
            if st_proc.returncode == 0:
                lines = [l for l in st_proc.stdout.splitlines() if l.strip()]
                dirty_cnt = len(lines)
                if dirty_cnt == 0:
                    return f"{branch} • clean", "accent"
                return f"{branch} • {dirty_cnt} dirty", "warn"
            return branch, "accent"
        except Exception:
            return "—", "dim"

    def _sample_ports(self) -> tuple[str, str]:
        ports: list[int] = []
        try:
            conns = psutil.net_connections(kind="inet")
            for c in conns:
                if c.status == "LISTEN" and c.laddr:
                    ip = str(getattr(c.laddr, "ip", ""))
                    if ip in ("127.0.0.1", "0.0.0.0", "::1", "::", "localhost"):
                        p = int(getattr(c.laddr, "port", 0))
                        if p > 0 and p not in ports:
                            ports.append(p)
        except Exception:
            pass

        if not ports:
            return "none", "dim"
        ports.sort()
        shown = [str(p) for p in ports[:PORTS_MAX_SHOWN]]
        res = " · ".join(shown)
        overflow = len(ports) - PORTS_MAX_SHOWN
        if overflow > 0:
            res += f" +{overflow}"
        return res, "accent"

    def _sample_top_proc(self) -> tuple[str, str]:
        try:
            top_proc = None
            max_mem = 0
            for p in psutil.process_iter(["pid", "name", "memory_info"]):
                try:
                    name = p.info.get("name") or "proc"
                    if name.lower() in ("system", "idle", "registry"):
                        continue
                    mem = p.info.get("memory_info")
                    rss = mem.rss if mem else 0
                    if rss > max_mem:
                        max_mem = rss
                        top_proc = (name, rss)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if top_proc:
                name, rss = top_proc
                gb = rss / (1024.0 ** 3)
                if gb >= 1.0:
                    return f"{name} • {gb:.1f} GB", "accent"
                mb = rss / (1024.0 ** 2)
                return f"{name} • {mb:.0f} MB", "accent"
        except Exception:
            pass
        return "—", "dim"
