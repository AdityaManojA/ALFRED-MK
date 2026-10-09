"""
core/integrations/alexa/client.py — Outbound WebSocket client for desktop ALFRED relay connection.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from typing import Any, Callable, Coroutine, Dict, Optional, Set

from core.integrations.alexa.config import (
    ALEXA_COMMAND_TIMEOUT_S,
    ALEXA_RECONNECT_BASE_S,
    ALEXA_RECONNECT_MAX_S,
    ALEXA_RELAY_CONNECT_TIMEOUT_S,
    AlexaConfig,
)
from core.integrations.alexa.policy import AlexaActionPolicy, AlexaContext
from core.integrations.alexa.protocol import (
    AlexaCommandEnvelope,
    AlexaResultEnvelope,
    parse_inbound_message,
)
from core.integrations.alexa.state import AlexaStateManager

logger = logging.getLogger("AlexaRelayClient")


class AlexaRelayClient:
    """
    Persistent outbound WebSocket client connecting Desktop ALFRED to the Alexa Relay.
    Never opens an inbound listener on the desktop.
    """

    def __init__(
        self,
        config: AlexaConfig,
        state_manager: AlexaStateManager,
        policy: AlexaActionPolicy,
        command_handler: Callable[[str, dict[str, Any]], Coroutine[Any, Any, str]],
        device_token: str = "",
    ) -> None:
        self.config = config
        self.state_manager = state_manager
        self.policy = policy
        self.command_handler = command_handler
        self.device_token = device_token

        self._running = False
        self._ws = None
        self._task: Optional[asyncio.Task] = None
        self._processed_request_ids: dict[str, float] = {}  # request_id -> processed_at
        self._idempotency_ttl_s = 300.0

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        """Start the background connection task."""
        if self._running:
            return
        self._running = True
        current_loop = loop or asyncio.get_event_loop()
        self._task = current_loop.create_task(self._run_loop())

    async def stop(self) -> None:
        """Gracefully stop the client."""
        self._running = False
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self.state_manager.set_relay_connected(False)

    async def _run_loop(self) -> None:
        """Exponential backoff connection loop."""
        reconnect_delay = ALEXA_RECONNECT_BASE_S

        while self._running:
            if not self.config.relay_ws_url:
                # Idle wait if not configured
                await asyncio.sleep(5.0)
                continue

            try:
                await self._connect_and_listen()
                # On clean disconnect, reset backoff
                reconnect_delay = ALEXA_RECONNECT_BASE_S
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Alexa relay connection error: {e}")
                self.state_manager.set_relay_connected(False)

            if not self._running:
                break

            # Add jitter
            jitter = random.uniform(0.1, 0.5) * reconnect_delay
            sleep_time = min(ALEXA_RECONNECT_MAX_S, reconnect_delay + jitter)
            logger.info(f"Reconnecting to Alexa relay in {sleep_time:.1f}s...")
            await asyncio.sleep(sleep_time)
            reconnect_delay = min(ALEXA_RECONNECT_MAX_S, reconnect_delay * 2)

    async def _connect_and_listen(self) -> None:
        """Connect to relay WebSocket endpoint and process incoming envelopes."""
        import websockets

        headers = {}
        if self.device_token:
            headers["Authorization"] = f"Bearer {self.device_token}"

        url = self.config.relay_ws_url
        logger.info(f"Connecting to Alexa relay: {url}")

        async with websockets.connect(
            url,
            additional_headers=headers,
            open_timeout=ALEXA_RELAY_CONNECT_TIMEOUT_S,
            ping_interval=20,
            ping_timeout=10,
        ) as ws:
            self._ws = ws
            self.state_manager.set_relay_connected(True)
            logger.info("Connected to Alexa relay successfully.")

            while self._running:
                raw_msg = await ws.recv()
                asyncio.create_task(self._handle_inbound_message(raw_msg))

    async def _handle_inbound_message(self, raw_msg: str | bytes) -> None:
        """Process an incoming message from the relay."""
        self._purge_idempotency_cache()

        try:
            parsed = parse_inbound_message(raw_msg)
        except Exception as err:
            logger.warning(f"Discarding invalid relay payload: {err}")
            return

        if isinstance(parsed, dict):
            mtype = parsed.get("type")
            if mtype == "ping":
                if self._ws:
                    await self._ws.send(json.dumps({"type": "pong", "ts": time.time()}))
            elif mtype == "linked":
                self.state_manager.set_linked(True)
            elif mtype == "unlinked":
                self.state_manager.set_linked(False)
            return

        if isinstance(parsed, AlexaCommandEnvelope):
            await self._process_command(parsed)

    async def _process_command(self, cmd: AlexaCommandEnvelope) -> None:
        """Authorize and execute incoming Alexa command envelope with deadline enforcement."""
        req_id = cmd.request_id

        # Idempotency check: execute each request ID at most once
        if req_id in self._processed_request_ids:
            logger.info(f"Ignoring duplicate request ID: {req_id}")
            return
        self._processed_request_ids[req_id] = time.time()

        # 1. Policy authorization
        ctx = AlexaContext(request_id=req_id, timestamp=cmd.timestamp)
        decision = self.policy.authorize(cmd.intent, cmd.arguments, ctx)

        if not decision.allowed:
            logger.warning(f"Alexa command '{cmd.intent}' rejected by policy: {decision.reason}")
            resp = AlexaResultEnvelope(
                version=1,
                type="result",
                request_id=req_id,
                status="denied",
                speech="I am not permitted to perform that action through Alexa, sir.",
                error=decision.reason,
            )
            await self._send_result(resp)
            self.state_manager.record_request_result(False)
            return

        # 2. Execution with deadline enforcement
        timeout_s = min(float(cmd.deadline_ms) / 1000.0, ALEXA_COMMAND_TIMEOUT_S)
        try:
            speech_result = await asyncio.wait_for(
                self.command_handler(cmd.intent, cmd.arguments),
                timeout=timeout_s,
            )
            resp = AlexaResultEnvelope(
                version=1,
                type="result",
                request_id=req_id,
                status="ok",
                speech=speech_result or "Command executed successfully, sir.",
            )
            await self._send_result(resp)
            self.state_manager.record_request_result(True)

        except asyncio.TimeoutError:
            logger.error(f"Command execution timed out after {timeout_s}s: {cmd.intent}")
            resp = AlexaResultEnvelope(
                version=1,
                type="result",
                request_id=req_id,
                status="error",
                speech="I’ve asked ALFRED to handle that, sir.",
                error="Command execution timed out before response deadline.",
            )
            await self._send_result(resp)
            self.state_manager.record_request_result(False)

        except Exception as exc:
            logger.exception(f"Error handling Alexa command {cmd.intent}: {exc}")
            resp = AlexaResultEnvelope(
                version=1,
                type="result",
                request_id=req_id,
                status="error",
                speech="An error occurred while executing the directive, sir.",
                error=str(exc),
            )
            await self._send_result(resp)
            self.state_manager.record_request_result(False)

    async def _send_result(self, result: AlexaResultEnvelope) -> None:
        """Send result envelope back over the WebSocket."""
        if self._ws:
            try:
                await self._ws.send(result.to_json())
            except Exception as e:
                logger.warning(f"Failed to send result back to relay: {e}")

    def _purge_idempotency_cache(self) -> None:
        """Purge stale request IDs."""
        now = time.time()
        stale = [rid for rid, ts in self._processed_request_ids.items() if now - ts > self._idempotency_ttl_s]
        for rid in stale:
            del self._processed_request_ids[rid]
