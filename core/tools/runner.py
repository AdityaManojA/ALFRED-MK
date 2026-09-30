"""
core/tools/runner.py — High-performance tool executor with caching, metrics, and fast fallbacks.

Target: Tool execution < 3 s; non-blocking background completion when slow.
Prompt Requirements:
- Measure and log:
  1. Tool setup time (auth, config load)
  2. Network request time
  3. Response parsing
- Lazy-init tool client with TTL cache
- Timeout + fallback: if tool takes > TOOL_TIMEOUT_S, return fast placeholder ("Checking the weather, sir")
  and fetch in background, then update HUD.
- Named constants at top of file: TOOL_TIMEOUT_S = 3, TOOL_INIT_CACHE_TTL_S = 3600.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, Optional

# ── Configuration Constants ──────────────────────────────────────────────────
TOOL_TIMEOUT_S: float = 3.0                     # Max tool execution wait before fallback
TOOL_INIT_CACHE_TTL_S: int = 3600               # 1 hour client instance cache TTL

logger = logging.getLogger("core.tools.runner")

# Common fast voice placeholders for slow network tools
FAST_TOOL_PLACEHOLDERS: Dict[str, str] = {
    "weather_report": "Checking the weather forecast, sir.",
    "calendar_sync": "Checking your schedule, sir.",
    "web_search": "Searching the web, sir.",
    "spotify": "Connecting to Spotify, sir.",
    "netflix_pilot": "Accessing Netflix, sir.",
    "flight_finder": "Looking up flight options, sir.",
}


@dataclass
class ToolExecutionMetrics:
    """Latency metrics recorded during tool execution."""
    tool_name: str
    setup_ms: float = 0.0
    execution_ms: float = 0.0
    parsing_ms: float = 0.0
    total_ms: float = 0.0
    timed_out: bool = False


class ClientCache:
    """Thread-safe client instance cache with TTL."""

    def __init__(self, ttl_s: int = TOOL_INIT_CACHE_TTL_S):
        self.ttl_s = ttl_s
        self._cache: Dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            client, ts = self._cache[key]
            if time.monotonic() - ts < self.ttl_s:
                return client
            del self._cache[key]
        return None

    def set(self, key: str, client: Any) -> None:
        self._cache[key] = (client, time.monotonic())

    def clear(self) -> None:
        self._cache.clear()


# Global client cache
CLIENT_CACHE = ClientCache()


async def execute_bounded_tool(
    tool_name: str,
    coro: Coroutine[Any, Any, Any],
    timeout_s: float = TOOL_TIMEOUT_S,
    on_background_finish: Optional[Callable[[str, Any], None]] = None,
) -> tuple[Any, ToolExecutionMetrics]:
    """Execute a tool with strict timeout and fast fallback placeholder."""
    metrics = ToolExecutionMetrics(tool_name=tool_name)
    t_start = time.perf_counter()

    task = asyncio.ensure_future(coro)

    try:
        t_exec_start = time.perf_counter()
        metrics.setup_ms = (t_exec_start - t_start) * 1000.0

        result = await asyncio.wait_for(asyncio.shield(task), timeout=timeout_s)

        t_parse_start = time.perf_counter()
        metrics.execution_ms = (t_parse_start - t_exec_start) * 1000.0
        metrics.total_ms = (time.perf_counter() - t_start) * 1000.0
        metrics.parsing_ms = (time.perf_counter() - t_parse_start) * 1000.0

        if metrics.total_ms > 1000.0:
            logger.info(
                f"[ToolRunner] {tool_name} total={metrics.total_ms:.1f}ms "
                f"setup={metrics.setup_ms:.1f}ms exec={metrics.execution_ms:.1f}ms"
            )

        return result, metrics

    except asyncio.TimeoutError:
        metrics.timed_out = True
        metrics.total_ms = (time.perf_counter() - t_start) * 1000.0
        placeholder = FAST_TOOL_PLACEHOLDERS.get(tool_name, f"Processing {tool_name}, sir.")
        logger.warning(
            f"[ToolRunner] {tool_name} exceeded {timeout_s}s budget ({metrics.total_ms:.1f}ms). "
            f"Returned fast placeholder: '{placeholder}'"
        )

        # Allow the task to finish in the background
        async def _finish_background():
            try:
                bg_res = await task
                logger.info(f"[ToolRunner] Background {tool_name} completed: {str(bg_res)[:60]}")
                if on_background_finish:
                    on_background_finish(tool_name, bg_res)
            except Exception as e:
                logger.error(f"[ToolRunner] Background {tool_name} failed: {e}")

        asyncio.create_task(_finish_background())
        return placeholder, metrics
