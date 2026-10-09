"""
core/integrations/alexa/protocol.py — Versioned envelope protocols for Alexa relay messaging.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional

from core.integrations.alexa.config import (
    ALEXA_COMMAND_TIMEOUT_S,
    ALEXA_MAX_RESPONSE_CHARS,
)

PROTOCOL_VERSION: int = 1
MAX_PAYLOAD_SIZE_BYTES: int = 65536  # 64 KB limit for inbound message


@dataclass(frozen=True)
class AlexaCommandEnvelope:
    """Inbound command envelope received from Alexa Relay."""
    version: int
    type: str  # "command"
    request_id: str
    intent: str
    arguments: dict[str, Any] = field(default_factory=dict)
    deadline_ms: int = int(ALEXA_COMMAND_TIMEOUT_S * 1000)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AlexaCommandEnvelope:
        if not isinstance(data, dict):
            raise ValueError("Payload must be a dictionary.")
        if data.get("version") != PROTOCOL_VERSION:
            raise ValueError(f"Unsupported protocol version: {data.get('version')}")
        if data.get("type") != "command":
            raise ValueError(f"Invalid message type for command: {data.get('type')}")
        req_id = str(data.get("request_id") or "").strip()
        if not req_id:
            raise ValueError("request_id is required.")
        intent = str(data.get("intent") or "").strip()
        if not intent:
            raise ValueError("intent is required.")
        args = data.get("arguments")
        if not isinstance(args, dict):
            args = {}
        deadline_ms = int(data.get("deadline_ms", ALEXA_COMMAND_TIMEOUT_S * 1000))
        ts = float(data.get("timestamp", time.time()))
        return cls(
            version=PROTOCOL_VERSION,
            type="command",
            request_id=req_id,
            intent=intent,
            arguments=args,
            deadline_ms=deadline_ms,
            timestamp=ts,
        )


@dataclass(frozen=True)
class AlexaResultEnvelope:
    """Outbound result envelope sent back to Alexa Relay."""
    version: int
    type: str  # "result"
    request_id: str
    status: str  # "ok", "error", "denied"
    speech: str
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        res = asdict(self)
        if self.error is None:
            res.pop("error", None)
        return res

    def to_json(self) -> str:
        # Enforce MAX_RESPONSE_CHARS limit
        speech_truncated = self.speech[:ALEXA_MAX_RESPONSE_CHARS] if self.speech else ""
        d = self.to_dict()
        d["speech"] = speech_truncated
        return json.dumps(d)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AlexaResultEnvelope:
        if not isinstance(data, dict):
            raise ValueError("Payload must be a dictionary.")
        if data.get("version") != PROTOCOL_VERSION:
            raise ValueError(f"Unsupported protocol version: {data.get('version')}")
        if data.get("type") != "result":
            raise ValueError(f"Invalid message type for result: {data.get('type')}")
        req_id = str(data.get("request_id") or "").strip()
        if not req_id:
            raise ValueError("request_id is required.")
        status = str(data.get("status") or "ok").strip()
        speech = str(data.get("speech") or "")[:ALEXA_MAX_RESPONSE_CHARS]
        error = data.get("error")
        return cls(
            version=PROTOCOL_VERSION,
            type="result",
            request_id=req_id,
            status=status,
            speech=speech,
            error=str(error) if error else None,
        )


def parse_inbound_message(raw_data: str | bytes) -> AlexaCommandEnvelope | dict[str, Any]:
    """Parse and validate incoming envelope with size guards."""
    if isinstance(raw_data, bytes):
        if len(raw_data) > MAX_PAYLOAD_SIZE_BYTES:
            raise ValueError("Message exceeds maximum payload limit.")
        raw_text = raw_data.decode("utf-8")
    else:
        if len(raw_data.encode("utf-8")) > MAX_PAYLOAD_SIZE_BYTES:
            raise ValueError("Message exceeds maximum payload limit.")
        raw_text = raw_data

    payload = json.loads(raw_text)
    if not isinstance(payload, dict):
        raise ValueError("Invalid JSON message root.")

    mtype = payload.get("type")
    if mtype == "command":
        return AlexaCommandEnvelope.from_dict(payload)
    elif mtype in ("ping", "pong", "handshake_ok", "error", "linked", "unlinked"):
        return payload
    else:
        raise ValueError(f"Unrecognized message type: {mtype}")
