"""
server/alexa/relay.py — WebSocket relay bridge linking Alexa HTTP Skill webhooks to desktop ALFRED.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional

from core.integrations.alexa.config import (
    ALEXA_COMMAND_TIMEOUT_S,
    ALEXA_MAX_RESPONSE_CHARS,
)
from core.integrations.alexa.protocol import (
    AlexaCommandEnvelope,
    AlexaResultEnvelope,
)

logger = logging.getLogger("AlexaRelay")


class DesktopRelayBridge:
    """Manages active desktop client connections and routes Skill requests to connected installations."""

    def __init__(self) -> None:
        """Initialise empty device, pending-request and user-to-device maps."""
        # device_id -> active WebSocket connection object
        self._connected_devices: dict[str, Any] = {}
        # request_id -> asyncio.Future[AlexaResultEnvelope]
        self._pending_requests: dict[str, asyncio.Future] = {}
        # amazon_user_id -> linked device_id
        self._user_device_map: dict[str, str] = {}

    def link_user_to_device(self, amazon_user_id: str, device_id: str) -> None:
        """Map an Amazon user ID to a registered ALFRED desktop device ID."""
        if amazon_user_id and device_id:
            self._user_device_map[amazon_user_id] = device_id

    def unlink_user(self, amazon_user_id: str) -> bool:
        """Unlink an Amazon user ID."""
        return self._user_device_map.pop(amazon_user_id, None) is not None

    def unlink_device(self, device_id: str) -> int:
        """Unlink all Amazon user IDs mapped to this device ID."""
        unlinked = 0
        for uid, dev in list(self._user_device_map.items()):
            if dev == device_id:
                del self._user_device_map[uid]
                unlinked += 1
        return unlinked

    def register_device(self, device_id: str, websocket: Any) -> None:
        """Register an active desktop WebSocket connection."""
        self._connected_devices[device_id] = websocket
        logger.info(f"Registered desktop device: {device_id}")

    def unregister_device(self, device_id: str) -> None:
        """Unregister a desktop WebSocket connection."""
        self._connected_devices.pop(device_id, None)
        logger.info(f"Unregistered desktop device: {device_id}")

    def is_device_connected(self, device_id: str) -> bool:
        """Return True if the device has an active WebSocket connection."""
        return device_id in self._connected_devices

    def handle_result_from_desktop(self, result: AlexaResultEnvelope) -> None:
        """Called when a desktop client returns an AlexaResultEnvelope."""
        fut = self._pending_requests.pop(result.request_id, None)
        if fut and not fut.done():
            fut.set_result(result)

    async def dispatch_command_to_device(
        self,
        device_id: str,
        command: AlexaCommandEnvelope,
        timeout_s: float = ALEXA_COMMAND_TIMEOUT_S,
    ) -> AlexaResultEnvelope:
        """Send a command envelope to a connected desktop and await its result envelope."""
        ws = self._connected_devices.get(device_id)
        if not ws:
            return AlexaResultEnvelope(
                version=1,
                type="result",
                request_id=command.request_id,
                status="error",
                speech="ALFRED is currently offline on your desktop, sir.",
                error="Desktop device is not connected to the relay.",
            )

        loop = asyncio.get_event_loop()
        fut: asyncio.Future[AlexaResultEnvelope] = loop.create_future()
        self._pending_requests[command.request_id] = fut

        try:
            # Send command envelope JSON to desktop
            await ws.send_text(command.to_json())
            result = await asyncio.wait_for(fut, timeout=timeout_s)
            return result
        except asyncio.TimeoutError:
            self._pending_requests.pop(command.request_id, None)
            return AlexaResultEnvelope(
                version=1,
                type="result",
                request_id=command.request_id,
                status="error",
                speech="I’ve asked ALFRED to handle that, sir.",
                error="Desktop did not respond before deadline.",
            )
        except Exception as e:
            self._pending_requests.pop(command.request_id, None)
            return AlexaResultEnvelope(
                version=1,
                type="result",
                request_id=command.request_id,
                status="error",
                speech="An internal relay error occurred, sir.",
                error=str(e),
            )

    def format_alexa_response(self, speech_text: str, should_end_session: bool = True) -> dict[str, Any]:
        """Format an Alexa Skills Kit response object."""
        clean_text = (speech_text or "")[:ALEXA_MAX_RESPONSE_CHARS]
        return {
            "version": "1.0",
            "response": {
                "outputSpeech": {
                    "type": "PlainText",
                    "text": clean_text,
                },
                "shouldEndSession": should_end_session,
            },
        }
