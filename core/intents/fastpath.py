"""core/intents/fastpath.py — Speculative Intent Prefetch & Resource Pre-warming.

Guarantees & Invariants:
- Absolute Purity (Zero Side Effects):
    Speculative prefetch executes ONLY idempotent, read-only queries (DNS warming,
    app path resolution, system telemetry snapshot, time/date formatting).
    NEVER launches processes, clicks windows, sends messages, or mutates persistent state.
- Bounded Cache with TTL:
    Prefetched results expire after PREFETCH_TTL_S (10 seconds) to ensure freshness.
- Non-blocking:
    Prefetch operations execute asynchronously in a 2-worker background pool.
"""

from __future__ import annotations

import collections
import concurrent.futures
import dataclasses
import datetime
import logging
import re
import socket
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

# ── Prefetch Configuration Constants ─────────────────────────────────────────
PREFETCH_TTL_S: float = 10.0             # Prefetch result Time-To-Live in seconds
MAX_PREFETCH_ENTRIES: int = 64           # Maximum cached prefetch records
PREFETCH_TIMEOUT_S: float = 2.0          # Max latency budget for speculative worker
PREFETCH_MAX_WORKERS: int = 2            # Thread pool limit for speculative warmup

_LOGGER = logging.getLogger("core.intents.fastpath")


@dataclasses.dataclass
class PrefetchRecord:
    """Cached result of a speculative read-only computation."""

    intent_type: str
    query_key: str
    result: Any
    created_at: float

    def is_expired(self, ttl_s: float = PREFETCH_TTL_S) -> bool:
        return (time.monotonic() - self.created_at) > ttl_s


class SpeculativePrefetcher:
    """Off-thread speculative intent warm-up engine with strict read-only purity."""

    def __init__(
        self,
        ttl_s: float = PREFETCH_TTL_S,
        max_entries: int = MAX_PREFETCH_ENTRIES,
        max_workers: int = PREFETCH_MAX_WORKERS,
    ) -> None:
        self.ttl_s = ttl_s
        self.max_entries = max_entries
        self._cache: collections.OrderedDict[str, PrefetchRecord] = collections.OrderedDict()
        self._cache_lock = threading.Lock()

        self._pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="speculative-prefetch",
        )
        self._inflight: set[str] = set()

    # ── Read-Only Pure Resolver Implementations ───────────────────────────────

    @staticmethod
    def _pure_time_date() -> Dict[str, str]:
        """Read-only resolution of current wall clock and date strings."""
        now = datetime.datetime.now()
        return {
            "time": now.strftime("%I:%M %p"),
            "date": now.strftime("%A, %B %d, %Y"),
            "timestamp": now.timestamp(),
        }

    @staticmethod
    def _pure_app_lookup(app_name: str) -> Optional[str]:
        """Read-only path resolution for common executable targets."""
        import shutil
        clean = app_name.strip().lower()
        aliases = {
            "chrome": ["chrome", "google-chrome"],
            "spotify": ["spotify"],
            "calc": ["calc", "calculator"],
            "notepad": ["notepad"],
            "terminal": ["wt", "cmd", "powershell"],
            "code": ["code", "vscode"],
        }
        candidates = aliases.get(clean, [clean])
        for c in candidates:
            resolved = shutil.which(c)
            if resolved:
                return resolved
        return None

    @staticmethod
    def _pure_dns_warm(hostname: str) -> Optional[str]:
        """Read-only DNS resolution and socket pre-warming."""
        try:
            addr = socket.gethostbyname(hostname)
            return addr
        except Exception:
            return None

    @staticmethod
    def _pure_system_telemetry() -> Dict[str, Any]:
        """Read-only CPU, Memory, and Battery telemetry snapshot."""
        try:
            import psutil
            return {
                "cpu_percent": psutil.cpu_percent(interval=None),
                "ram_percent": psutil.virtual_memory().percent,
            }
        except Exception:
            return {}

    # ── Speculative Routing & Execution ───────────────────────────────────────

    def inspect_partial(self, partial_text: str) -> None:
        """Inspect a speculative partial text token and trigger safe warmup jobs."""
        if not partial_text:
            return
        text = partial_text.lower().strip()

        # 1. Time / Date queries
        if any(p in text for p in ("time", "what time", "date", "today's date")):
            self._dispatch_async("time_date", "now", self._pure_time_date)

        # 2. System Status / Telemetry
        elif any(p in text for p in ("system status", "cpu", "memory usage", "battery")):
            self._dispatch_async("system", "telemetry", self._pure_system_telemetry)

        # 3. Application launches: "open <app>"
        elif "open " in text or "launch " in text:
            match = re.search(r"(?:open|launch)\s+([a-zA-Z0-9_\-]+)", text)
            if match:
                app = match.group(1).strip()
                self._dispatch_async("app_path", app, lambda: self._pure_app_lookup(app))

        # 4. Web queries: domain DNS warmup
        elif any(p in text for p in ("search ", "google ", "look up ")):
            self._dispatch_async("dns", "google.com", lambda: self._pure_dns_warm("www.google.com"))

    def _dispatch_async(self, intent_type: str, key: str, resolver_fn: Callable[[], Any]) -> None:
        cache_key = f"{intent_type}:{key}"
        with self._cache_lock:
            if cache_key in self._cache:
                rec = self._cache[cache_key]
                if not rec.is_expired(self.ttl_s):
                    return  # Fresh cached result already available
            if cache_key in self._inflight:
                return  # Resolution already in flight
            self._inflight.add(cache_key)

        def _task():
            try:
                res = resolver_fn()
                self.store(intent_type, key, res)
            except Exception as exc:
                _LOGGER.debug("[PREFETCH] Resolver failed for %s: %s", cache_key, exc)
            finally:
                with self._cache_lock:
                    self._inflight.discard(cache_key)

        self._pool.submit(_task)

    def store(self, intent_type: str, query_key: str, value: Any) -> None:
        """Store a precomputed speculative result."""
        cache_key = f"{intent_type}:{query_key}"
        record = PrefetchRecord(
            intent_type=intent_type,
            query_key=query_key,
            result=value,
            created_at=time.monotonic(),
        )
        with self._cache_lock:
            if len(self._cache) >= self.max_entries:
                self._cache.popitem(last=False)
            self._cache[cache_key] = record

    def get(self, intent_type: str, query_key: str) -> Optional[Any]:
        """Retrieve a fresh prefetched result if valid and unexpired."""
        cache_key = f"{intent_type}:{query_key}"
        with self._cache_lock:
            record = self._cache.get(cache_key)
            if record is None:
                return None
            if record.is_expired(self.ttl_s):
                self._cache.pop(cache_key, None)
                return None
            return record.result

    def shutdown(self) -> None:
        """Shutdown background worker pool."""
        self._pool.shutdown(wait=False)
