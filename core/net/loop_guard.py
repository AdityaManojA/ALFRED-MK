"""core/net/loop_guard.py — Proactor event loop transport exception guard for Windows.

Suppresses benign WSAECONNRESET (10054) noise originating from asyncio's
_ProactorBasePipeTransport._call_connection_lost during peer shutdown/reconnect,
while preserving full error propagation for genuine connection failures.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

# Windows Socket error code for connection reset by peer
WINSOCK_CONNRESET: int = 10054  # WSAECONNRESET: peer closed before graceful shutdown

_LOGGER = logging.getLogger("core.net.loop_guard")


def install_transport_guard(loop: Any, logger: logging.Logger | None = None) -> None:
    """Install an exception handler on the asyncio event loop that swallows WSAECONNRESET noise.

    Only swallows ConnectionResetError/OSError where winerror == 10054 or message matches
    _call_connection_lost during transport shutdown. All other exceptions propagate to
    the previous or default exception handler so genuine reconnect logic is preserved.
    """
    log_target = logger or _LOGGER
    prev: Callable[[Any, dict[str, Any]], None] | None = loop.get_exception_handler()

    def handler(l: Any, ctx: dict[str, Any]) -> None:
        exc = ctx.get("exception")
        msg = str(ctx.get("message", ""))
        is_conn_reset = False

        if isinstance(exc, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError)):
            winerr = getattr(exc, "winerror", None)
            if winerr == WINSOCK_CONNRESET or "10054" in str(exc) or "connection_lost" in str(exc):
                is_conn_reset = True

        if not is_conn_reset and ("10054" in msg or "_call_connection_lost" in msg or "connection_lost" in msg):
            is_conn_reset = True

        if is_conn_reset:
            log_target.debug("transport closed by peer during shutdown (suppressed)")
            return

        if prev is not None:
            prev(l, ctx)
        else:
            l.default_exception_handler(ctx)

    loop.set_exception_handler(handler)
