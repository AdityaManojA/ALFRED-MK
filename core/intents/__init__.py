"""core/intents/__init__.py — Intent routing subsystem package.

Exports IntentRouter, SpeculativePrefetcher, and intent records.
"""

from __future__ import annotations

from core.intents.fastpath import (
    MAX_PREFETCH_ENTRIES,
    PREFETCH_TIMEOUT_S,
    PREFETCH_TTL_S,
    PrefetchRecord,
    SpeculativePrefetcher,
)
from core.intents.router import (
    INTENT_PARSE_TIMEOUT_MS,
    INTENT_PARSE_TIMEOUT_S,
    PHRASE_CACHE_SIZE,
    IntentMatch,
    IntentMetrics,
    IntentRouter,
)

__all__ = [
    "IntentRouter",
    "IntentMatch",
    "IntentMetrics",
    "INTENT_PARSE_TIMEOUT_S",
    "INTENT_PARSE_TIMEOUT_MS",
    "PHRASE_CACHE_SIZE",
    "SpeculativePrefetcher",
    "PrefetchRecord",
    "PREFETCH_TTL_S",
    "MAX_PREFETCH_ENTRIES",
    "PREFETCH_TIMEOUT_S",
]
