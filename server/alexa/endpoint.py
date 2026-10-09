"""
server/alexa/endpoint.py — FastAPI/Starlette router & endpoints for Alexa Webhooks and Desktop Relay.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, Optional

from core.integrations.alexa.protocol import (
    AlexaCommandEnvelope,
    AlexaResultEnvelope,
    parse_inbound_message,
)
from server.alexa.relay import DesktopRelayBridge
from server.alexa.verification import AlexaRequestVerifier

logger = logging.getLogger("AlexaEndpoint")


def create_alexa_app(
    skill_id: str = "",
    skip_signature_verification: bool = False,
    bridge: Optional[DesktopRelayBridge] = None,
    linking_manager: Optional[Any] = None,
):
    """
    Factory creating a FastAPI app for the Alexa Skills Kit relay server.
    """
    from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
    from fastapi.responses import JSONResponse

    app = FastAPI(title="ALFRED Alexa Relay", version="1.0.0")
    relay_bridge = bridge or DesktopRelayBridge()
    verifier = AlexaRequestVerifier(
        expected_skill_id=skill_id,
        skip_signature_for_dev=skip_signature_verification,
    )

    @app.get("/health")
    async def health_check():
        return {"status": "ok", "service": "alfred-alexa-relay"}

    @app.post("/api/alexa/link")
    async def account_link(request: Request):
        """Link an Amazon user ID to an ALFRED desktop device."""
        try:
            payload = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body.")

        amazon_user_id = str(payload.get("amazon_user_id") or "").strip()
        device_id = str(payload.get("device_id") or "").strip()
        state_token = str(payload.get("state_token") or "").strip()

        if not amazon_user_id:
            raise HTTPException(status_code=400, detail="Missing amazon_user_id.")

        # If linking manager is active, validate and atomically consume state token
        if linking_manager is not None:
            if not state_token:
                raise HTTPException(status_code=400, detail="Missing state_token.")
            consumed_state = linking_manager.consume_linking_state(state_token)
            if consumed_state is None:
                raise HTTPException(status_code=403, detail="Invalid, expired, or already-used state_token.")
            # Use device ID registered on state token if provided
            if consumed_state.device_id:
                device_id = consumed_state.device_id

        if not device_id:
            raise HTTPException(status_code=400, detail="Missing device_id.")

        relay_bridge.link_user_to_device(amazon_user_id, device_id)
        return {"status": "ok", "linked": True, "device_id": device_id}

    @app.post("/api/alexa/unlink")
    async def account_unlink(request: Request):
        """Unlink an ALFRED desktop installation."""
        try:
            payload = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body.")

        device_id = str(payload.get("device_id") or "").strip()
        if not device_id:
            raise HTTPException(status_code=400, detail="Missing device_id.")

        count = relay_bridge.unlink_device(device_id)
        return {"status": "ok", "unlinked_count": count}

    @app.post("/api/alexa/skill")
    async def alexa_skill_webhook(request: Request):
        """Incoming Alexa Skills Kit webhook endpoint."""
        raw_body = await request.body()
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception:
            raise HTTPException(status_code=400, detail="Malformed JSON body.")

        # 1. Verification
        is_valid, status_code, err_cat = verifier.verify_request(
            headers=dict(request.headers),
            raw_body=raw_body,
            parsed_payload=payload,
        )
        if not is_valid:
            raise HTTPException(status_code=status_code, detail=f"Request verification failed: {err_cat}")

        # 2. Extract Intent & Arguments
        req_obj = payload.get("request", {})
        req_type = req_obj.get("type", "")
        req_id = req_obj.get("requestId", str(uuid.uuid4()))

        # Amazon User ID
        user_id = (
            payload.get("session", {})
            .get("user", {})
            .get("userId", "")
        )
        if not user_id:
            user_id = (
                payload.get("context", {})
                .get("System", {})
                .get("user", {})
                .get("userId", "")
            )

        # Handle built-in Alexa lifecycle requests
        if req_type == "LaunchRequest":
            return relay_bridge.format_alexa_response(
                "ALFRED systems online, sir. What directive would you like to issue?",
                should_end_session=False,
            )
        elif req_type == "SessionEndedRequest":
            return relay_bridge.format_alexa_response("", should_end_session=True)
        elif req_type != "IntentRequest":
            return relay_bridge.format_alexa_response("Unsupported request type, sir.")

        intent_obj = req_obj.get("intent", {})
        intent_name = intent_obj.get("name", "")

        # Built-in stop / cancel
        if intent_name in ("AMAZON.StopIntent", "AMAZON.CancelIntent"):
            return relay_bridge.format_alexa_response("Understood, sir.", should_end_session=True)
        elif intent_name == "AMAZON.HelpIntent":
            return relay_bridge.format_alexa_response(
                "You can ask ALFRED for system status, to start focus mode, control media, or run an internet speed test.",
                should_end_session=False,
            )

        # Extract slots
        slots = intent_obj.get("slots", {})
        arguments = {}
        for sname, sinfo in slots.items():
            if isinstance(sinfo, dict) and "value" in sinfo:
                arguments[sname] = sinfo["value"]

        # Resolve device ID
        device_id = relay_bridge._user_device_map.get(user_id)
        if not device_id:
            # Fallback if only 1 device connected
            if len(relay_bridge._connected_devices) == 1:
                device_id = next(iter(relay_bridge._connected_devices.keys()))
            else:
                return relay_bridge.format_alexa_response(
                    "Your Echo account is not linked to an active ALFRED installation, sir. Please link your account in the ALFRED settings."
                )

        # 3. Create command envelope and dispatch to desktop
        cmd = AlexaCommandEnvelope(
            version=1,
            type="command",
            request_id=req_id,
            intent=intent_name,
            arguments=arguments,
        )

        result_envelope = await relay_bridge.dispatch_command_to_device(device_id, cmd)
        return relay_bridge.format_alexa_response(result_envelope.speech)

    @app.websocket("/ws/desktop")
    async def desktop_ws(websocket: WebSocket, device_id: str = "default_device"):
        """Outbound WebSocket from desktop ALFRED client."""
        await websocket.accept()
        relay_bridge.register_device(device_id, websocket)

        try:
            while True:
                msg_text = await websocket.receive_text()
                try:
                    payload = json.loads(msg_text)
                    if payload.get("type") == "result":
                        res_env = AlexaResultEnvelope.from_dict(payload)
                        relay_bridge.handle_result_from_desktop(res_env)
                except Exception as ex:
                    logger.warning(f"Error handling desktop message: {ex}")
        except WebSocketDisconnect:
            pass
        finally:
            relay_bridge.unregister_device(device_id)

    return app
