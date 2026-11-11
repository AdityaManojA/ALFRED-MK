"""
tests/test_alexa_endpoint.py — Unit tests for server/alexa/endpoint.py (Alexa relay FastAPI app).

Route handlers are invoked directly with fake Request/WebSocket objects, so no HTTP
client (httpx) or network socket is needed. Request verification is mocked.
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import HTTPException, WebSocketDisconnect  # noqa: E402

import server.alexa.endpoint as endpoint  # noqa: E402
from core.integrations.alexa.protocol import AlexaResultEnvelope  # noqa: E402
from server.alexa.relay import DesktopRelayBridge  # noqa: E402


class _FakeVerifier:
    result = (True, 200, "")
    init_kwargs: dict = {}

    def __init__(self, **kwargs):
        _FakeVerifier.init_kwargs = kwargs
        self.calls = []

    def verify_request(self, headers, raw_body, parsed_payload):
        self.calls.append((headers, raw_body, parsed_payload))
        return _FakeVerifier.result


class _Request:
    def __init__(self, payload=None, raw=None, headers=None):
        self._raw = raw if raw is not None else json.dumps(payload).encode()
        self.headers = headers or {"signature": "sig"}

    async def body(self):
        return self._raw

    async def json(self):
        return json.loads(self._raw)


class _Bridge(DesktopRelayBridge):
    def __init__(self):
        super().__init__()
        self.dispatched = []

    async def dispatch_command_to_device(self, device_id, command, timeout_s=0):
        self.dispatched.append((device_id, command))
        return AlexaResultEnvelope(version=1, type="result", request_id=command.request_id,
                                   status="ok", speech="Done, sir.")


@pytest.fixture
def make_app(monkeypatch):
    monkeypatch.setattr(endpoint, "AlexaRequestVerifier", _FakeVerifier)
    _FakeVerifier.result = (True, 200, "")

    def factory(**kwargs):
        bridge = kwargs.pop("bridge", None) or _Bridge()
        app = endpoint.create_alexa_app(bridge=bridge, **kwargs)
        routes = {r.path: r.endpoint for r in app.routes if hasattr(r, "endpoint")}
        return app, routes, bridge
    return factory


def _call(fn, *args, **kwargs):
    return asyncio.run(fn(*args, **kwargs))


def _speech(resp):
    return resp["response"]["outputSpeech"]["text"]


def _intent(name, slots=None, user="amzn1.user"):
    return {
        "session": {"user": {"userId": user}},
        "request": {"type": "IntentRequest", "requestId": "req-1",
                    "intent": {"name": name, "slots": slots or {}}},
    }


def test_app_wires_verifier_and_health(make_app):
    app, routes, _ = make_app(skill_id="amzn1.ask.skill.x", skip_signature_verification=True)
    assert app.title == "ALFRED Alexa Relay"
    assert _FakeVerifier.init_kwargs == {"expected_skill_id": "amzn1.ask.skill.x",
                                         "skip_signature_for_dev": True}
    assert _call(routes["/health"]) == {"status": "ok", "service": "alfred-alexa-relay"}


# ── /api/alexa/link & unlink ──────────────────────────────────────────────────

def test_link_success(make_app):
    _, routes, bridge = make_app()
    out = _call(routes["/api/alexa/link"], _Request({"amazon_user_id": " u1 ", "device_id": "pc"}))
    assert out == {"status": "ok", "linked": True, "device_id": "pc"}
    assert bridge._user_device_map == {"u1": "pc"}


@pytest.mark.parametrize("payload,raw,detail", [
    (None, b"not json", "Invalid JSON body."),
    ({"device_id": "pc"}, None, "Missing amazon_user_id."),
    ({"amazon_user_id": "u1"}, None, "Missing device_id."),
])
def test_link_validation_errors(make_app, payload, raw, detail):
    _, routes, _ = make_app()
    with pytest.raises(HTTPException) as ei:
        _call(routes["/api/alexa/link"], _Request(payload, raw=raw))
    assert ei.value.status_code == 400
    assert ei.value.detail == detail


def test_link_with_linking_manager_consumes_state(make_app):
    consumed = []

    class Manager:
        def consume_linking_state(self, token):
            consumed.append(token)
            return SimpleNamespace(device_id="state-device") if token == "good" else None

    _, routes, bridge = make_app(linking_manager=Manager())
    with pytest.raises(HTTPException) as missing:
        _call(routes["/api/alexa/link"], _Request({"amazon_user_id": "u1", "device_id": "pc"}))
    assert missing.value.status_code == 400 and "state_token" in missing.value.detail

    with pytest.raises(HTTPException) as bad:
        _call(routes["/api/alexa/link"],
              _Request({"amazon_user_id": "u1", "device_id": "pc", "state_token": "bad"}))
    assert bad.value.status_code == 403

    out = _call(routes["/api/alexa/link"],
                _Request({"amazon_user_id": "u1", "device_id": "pc", "state_token": "good"}))
    assert out["device_id"] == "state-device"
    assert bridge._user_device_map["u1"] == "state-device"
    assert consumed == ["bad", "good"]


def test_unlink(make_app):
    _, routes, bridge = make_app()
    bridge.link_user_to_device("a", "pc")
    bridge.link_user_to_device("b", "pc")
    bridge.link_user_to_device("c", "laptop")
    out = _call(routes["/api/alexa/unlink"], _Request({"device_id": "pc"}))
    assert out == {"status": "ok", "unlinked_count": 2}
    assert bridge._user_device_map == {"c": "laptop"}
    with pytest.raises(HTTPException) as ei:
        _call(routes["/api/alexa/unlink"], _Request({}))
    assert ei.value.detail == "Missing device_id."


# ── /api/alexa/skill webhook ──────────────────────────────────────────────────

def test_skill_malformed_json(make_app):
    _, routes, _ = make_app()
    with pytest.raises(HTTPException) as ei:
        _call(routes["/api/alexa/skill"], _Request(raw=b"{oops"))
    assert ei.value.status_code == 400


def test_skill_verification_failure(make_app):
    _, routes, _ = make_app()
    _FakeVerifier.result = (False, 401, "bad_signature")
    with pytest.raises(HTTPException) as ei:
        _call(routes["/api/alexa/skill"], _Request({"request": {"type": "LaunchRequest"}}))
    assert ei.value.status_code == 401
    assert "bad_signature" in ei.value.detail


@pytest.mark.parametrize("req_type,speech,ends", [
    ("LaunchRequest", "ALFRED systems online", False),
    ("SessionEndedRequest", "", True),
    ("CanFulfillIntentRequest", "Unsupported request type", True),
])
def test_skill_lifecycle_requests(make_app, req_type, speech, ends):
    _, routes, bridge = make_app()
    resp = _call(routes["/api/alexa/skill"], _Request({"request": {"type": req_type}}))
    assert _speech(resp).startswith(speech)
    assert resp["response"]["shouldEndSession"] is ends
    assert bridge.dispatched == []


@pytest.mark.parametrize("intent,speech,ends", [
    ("AMAZON.StopIntent", "Understood, sir.", True),
    ("AMAZON.CancelIntent", "Understood, sir.", True),
    ("AMAZON.HelpIntent", "You can ask ALFRED", False),
])
def test_skill_builtin_intents(make_app, intent, speech, ends):
    _, routes, bridge = make_app()
    resp = _call(routes["/api/alexa/skill"], _Request(_intent(intent)))
    assert _speech(resp).startswith(speech)
    assert resp["response"]["shouldEndSession"] is ends
    assert bridge.dispatched == []


def test_skill_dispatches_to_linked_device_with_slots(make_app):
    _, routes, bridge = make_app()
    bridge.link_user_to_device("amzn1.user", "pc")
    payload = _intent("FocusIntent", slots={"minutes": {"name": "minutes", "value": "25"},
                                            "task": {"name": "task"}})
    resp = _call(routes["/api/alexa/skill"], _Request(payload))
    assert _speech(resp) == "Done, sir."
    device, cmd = bridge.dispatched[0]
    assert device == "pc"
    assert cmd.intent == "FocusIntent"
    assert cmd.request_id == "req-1"
    assert cmd.arguments == {"minutes": "25"}


def test_skill_user_from_context_and_single_device_fallback(make_app):
    _, routes, bridge = make_app()
    bridge.register_device("only-pc", object())
    payload = _intent("StatusIntent", user="")
    payload["context"] = {"System": {"user": {"userId": "ctx-user"}}}
    _call(routes["/api/alexa/skill"], _Request(payload))
    assert bridge.dispatched[0][0] == "only-pc"


def test_skill_context_user_id_is_used_for_linking(make_app):
    _, routes, bridge = make_app()
    bridge.link_user_to_device("ctx-user", "linked-pc")
    bridge.register_device("a", object())
    bridge.register_device("b", object())
    payload = _intent("StatusIntent", user="")
    payload["context"] = {"System": {"user": {"userId": "ctx-user"}}}
    _call(routes["/api/alexa/skill"], _Request(payload))
    assert bridge.dispatched[0][0] == "linked-pc"


def test_skill_unlinked_with_multiple_devices(make_app):
    _, routes, bridge = make_app()
    bridge.register_device("a", object())
    bridge.register_device("b", object())
    resp = _call(routes["/api/alexa/skill"], _Request(_intent("StatusIntent")))
    assert "not linked" in _speech(resp)
    assert bridge.dispatched == []


# ── /ws/desktop ───────────────────────────────────────────────────────────────

class _FakeWS:
    def __init__(self, messages):
        self.messages = list(messages)
        self.accepted = False

    async def accept(self):
        self.accepted = True

    async def receive_text(self):
        if not self.messages:
            raise WebSocketDisconnect()
        return self.messages.pop(0)


def test_desktop_ws_routes_results_and_unregisters(make_app):
    _, routes, bridge = make_app()
    results = []
    bridge.handle_result_from_desktop = results.append
    seen_registered = []
    orig_register = bridge.register_device

    def register(device_id, ws):
        orig_register(device_id, ws)
        seen_registered.append(bridge.is_device_connected(device_id))
    bridge.register_device = register

    ws = _FakeWS([
        json.dumps({"version": 1, "type": "result", "request_id": "r1", "status": "ok", "speech": "hi"}),
        json.dumps({"type": "ping"}),
        "not json",
        json.dumps({"version": 99, "type": "result", "request_id": "r2"}),
    ])
    _call(routes["/ws/desktop"], ws, device_id="pc-1")

    assert ws.accepted
    assert seen_registered == [True]
    assert [r.request_id for r in results] == ["r1"]
    assert results[0].speech == "hi"
    assert not bridge.is_device_connected("pc-1")
