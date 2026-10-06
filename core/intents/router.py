"""
core/intents/router.py — High-speed intent router with regex fast-path and phrase caching.

Target: Intent parse latency < 200 ms (fast path < 5 ms).
Prompt Requirements:
- Add entry/exit timestamps.
- Measure: phrase matching, entity extraction, tool lookup, signal emission.
- Fast path (regex trie / exact match) for common commands before LLM fallback.
- LRU phrase cache for tool lookups.
- Named constants at top of file: INTENT_PARSE_TIMEOUT_S, PHRASE_CACHE_SIZE.
"""

from __future__ import annotations

import collections
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

# ── Configuration Constants ──────────────────────────────────────────────────
INTENT_PARSE_TIMEOUT_S: float = 0.5         # 500 ms parse budget
INTENT_PARSE_TIMEOUT_MS: float = 500.0      # Alternate millisecond representation
PHRASE_CACHE_SIZE: int = 256                # LRU cache entries for routed phrases

logger = logging.getLogger("core.intents.router")


@dataclass
class IntentMetrics:
    """Latency metrics recorded during intent resolution."""
    phrase_matching_ms: float = 0.0
    entity_extraction_ms: float = 0.0
    tool_lookup_ms: float = 0.0
    signal_emission_ms: float = 0.0
    total_ms: float = 0.0


@dataclass
class IntentMatch:
    """Resolved intent ready for execution."""
    intent_name: str
    action_name: str
    entities: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    metrics: IntentMetrics = field(default_factory=IntentMetrics)
    source: str = "fast_path"               # "fast_path", "cache", or "llm"


class IntentRouter:
    """Fast-path deterministic router with LRU caching and regex matching."""

    # Common voice commands mapped directly to action names
    FAST_PATTERNS: List[Tuple[re.Pattern, str, str]] = [
        (re.compile(r"^(what('s| is) the time|what time is it|time check)\b", re.I), "get_time", "system_status"),
        (re.compile(r"^(what('s| is) the date|today'?s date)\b", re.I), "get_date", "system_status"),
        (re.compile(r"^(what('s| is) the weather|weather forecast|how'?s the weather)\b", re.I), "get_weather", "weather_report"),
        (re.compile(r"^(mute me|mute my mic|mute( the)? microphone)\b", re.I), "mute_me", "mute_system_microphone"),
        (re.compile(r"^(mute|silence|quiet)\b", re.I), "mute", "media_control"),
        (re.compile(r"^(unmute|speak)\b", re.I), "unmute", "media_control"),
        (re.compile(r"^(pause|stop playback)\b", re.I), "pause", "media_control"),
        (re.compile(r"^(resume|play|unpause)\b", re.I), "resume", "media_control"),
        (re.compile(r"^(close( this| active)? tab|shut this tab|kill tab)\b", re.I), "close_tab", "browser_control"),
        (re.compile(r"^open netflix\b", re.I), "open_netflix", "netflix_pilot"),
        (re.compile(r"^search netflix for\s+(?P<query>.+)", re.I), "search_netflix", "netflix_pilot"),
        (re.compile(r"^play\s+(?P<query>.+)\s+on netflix\b", re.I), "play_netflix", "netflix_pilot"),
        (re.compile(r"^(open|launch)\s+(?P<app>[a-zA-Z0-9_\- ]+)\b", re.I), "open_app", "computer_control"),
        (re.compile(r"^(turn (on|off) dark mode|toggle dark mode)\b", re.I), "toggle_dark_mode", "computer_settings"),
    ]

    def __init__(self, cache_size: int = PHRASE_CACHE_SIZE):
        self.cache_size = cache_size
        self._cache: collections.OrderedDict[str, IntentMatch] = collections.OrderedDict()
        self._listeners: List[Callable[[IntentMatch], None]] = []

    def add_listener(self, callback: Callable[[IntentMatch], None]) -> None:
        """Register a callback for signal emission."""
        self._listeners.append(callback)

    def route(self, utterance: str) -> Optional[IntentMatch]:
        """Route an utterance with sub-millisecond fast-path and full latency breakdown."""
        t_entry = time.perf_counter()
        metrics = IntentMetrics()
        cleaned = utterance.strip().lower()

        # Check LRU cache first
        if cleaned in self._cache:
            match = self._cache[cleaned]
            self._cache.move_to_end(cleaned)
            metrics.total_ms = (time.perf_counter() - t_entry) * 1000.0
            match.metrics = metrics
            return match

        # 1. Fast-path pattern matching
        t_match_start = time.perf_counter()
        matched_tuple = None
        match_obj = None

        for pattern, intent, action in self.FAST_PATTERNS:
            m = pattern.search(cleaned)
            if m:
                matched_tuple = (intent, action)
                match_obj = m
                break

        metrics.phrase_matching_ms = (time.perf_counter() - t_match_start) * 1000.0

        if not matched_tuple:
            # No fast-path match; fall through to caller's LLM fallback
            metrics.total_ms = (time.perf_counter() - t_entry) * 1000.0
            return None

        intent_name, action_name = matched_tuple

        # 2. Entity extraction
        t_entity_start = time.perf_counter()
        entities = match_obj.groupdict() if match_obj else {}
        metrics.entity_extraction_ms = (time.perf_counter() - t_entity_start) * 1000.0

        # 3. Tool lookup
        t_lookup_start = time.perf_counter()
        # Fast path maps directly to verified action name
        resolved_action = action_name
        metrics.tool_lookup_ms = (time.perf_counter() - t_lookup_start) * 1000.0

        # 4. Signal emission
        t_signal_start = time.perf_counter()
        intent_match = IntentMatch(
            intent_name=intent_name,
            action_name=resolved_action,
            entities=entities,
            confidence=0.99,
            metrics=metrics,
            source="fast_path",
        )
        for listener in self._listeners:
            try:
                listener(intent_match)
            except Exception as e:
                logger.warning(f"[IntentRouter] Listener error: {e}")
        metrics.signal_emission_ms = (time.perf_counter() - t_signal_start) * 1000.0

        # Total resolution time
        metrics.total_ms = (time.perf_counter() - t_entry) * 1000.0

        # Update LRU cache
        if len(self._cache) >= self.cache_size:
            self._cache.popitem(last=False)
        self._cache[cleaned] = intent_match

        if metrics.total_ms > 50.0:
            logger.info(
                f"[IntentRouter] utterance='{utterance[:30]}' total={metrics.total_ms:.1f}ms "
                f"match={metrics.phrase_matching_ms:.1f}ms entities={metrics.entity_extraction_ms:.1f}ms"
            )

        return intent_match
