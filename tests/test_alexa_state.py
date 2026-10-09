"""
tests/test_alexa_state.py — Unit tests for Alexa connection state, constants, snapshot privacy, and protocol envelopes.
"""
import unittest

from core.integrations.alexa.config import (
    ALEXA_CLOCK_SKEW_S,
    ALEXA_COMMAND_TIMEOUT_S,
    ALEXA_MAX_RESPONSE_CHARS,
    ALEXA_RECONNECT_BASE_S,
    ALEXA_RECONNECT_MAX_S,
    ALEXA_RELAY_CONNECT_TIMEOUT_S,
    ALEXA_REQUEST_MAX_AGE_S,
    AlexaConfig,
)
from core.integrations.alexa.account_link import AccountLinkingManager
from core.integrations.alexa.protocol import (
    AlexaCommandEnvelope,
    AlexaResultEnvelope,
    parse_inbound_message,
)
from core.integrations.alexa.state import (
    AlexaConnectionStatus,
    AlexaSnapshot,
    AlexaStateManager,
)


class TestAlexaConstants(unittest.TestCase):
    """Validate all named constants match the platform directive."""

    def test_constants_match_directive(self):
        self.assertEqual(ALEXA_RELAY_CONNECT_TIMEOUT_S, 10.0)
        self.assertEqual(ALEXA_RECONNECT_BASE_S, 1.0)
        self.assertEqual(ALEXA_RECONNECT_MAX_S, 30.0)
        self.assertEqual(ALEXA_REQUEST_MAX_AGE_S, 150.0)
        self.assertEqual(ALEXA_COMMAND_TIMEOUT_S, 8.0)
        self.assertEqual(ALEXA_MAX_RESPONSE_CHARS, 700)
        self.assertEqual(ALEXA_CLOCK_SKEW_S, 30.0)


class TestAlexaStateTransitions(unittest.TestCase):
    """Validate state transitions and listener notifications."""

    def test_initial_state(self):
        mgr = AlexaStateManager()
        snap = mgr.get_snapshot()
        self.assertEqual(snap.status, AlexaConnectionStatus.NOT_CONFIGURED)
        self.assertFalse(snap.configured)
        self.assertFalse(snap.linked)
        self.assertFalse(snap.relay_connected)
        self.assertTrue(snap.last_request_ok)
        self.assertEqual(snap.allowed_intent_count, 0)

    def test_configured_transition(self):
        mgr = AlexaStateManager()
        mgr.set_configured(True)
        self.assertEqual(mgr.get_snapshot().status, AlexaConnectionStatus.READY_TO_LINK)

    def test_linking_pending_transition(self):
        mgr = AlexaStateManager()
        mgr.set_configured(True)
        mgr.set_linking_pending()
        self.assertEqual(mgr.get_snapshot().status, AlexaConnectionStatus.LINK_PENDING)

    def test_linked_without_relay_is_offline(self):
        mgr = AlexaStateManager()
        mgr.set_configured(True)
        mgr.set_linked(True)
        self.assertEqual(mgr.get_snapshot().status, AlexaConnectionStatus.OFFLINE)

    def test_linked_with_relay_is_connected(self):
        mgr = AlexaStateManager()
        mgr.set_configured(True)
        mgr.set_linked(True)
        mgr.set_relay_connected(True)
        self.assertEqual(mgr.get_snapshot().status, AlexaConnectionStatus.CONNECTED)

    def test_relay_disconnect_drops_to_offline(self):
        mgr = AlexaStateManager()
        mgr.set_configured(True)
        mgr.set_linked(True)
        mgr.set_relay_connected(True)
        self.assertEqual(mgr.get_snapshot().status, AlexaConnectionStatus.CONNECTED)

        mgr.set_relay_connected(False)
        self.assertEqual(mgr.get_snapshot().status, AlexaConnectionStatus.OFFLINE)

    def test_error_transition(self):
        mgr = AlexaStateManager()
        mgr.set_configured(True)
        mgr.set_error()
        snap = mgr.get_snapshot()
        self.assertEqual(snap.status, AlexaConnectionStatus.ERROR)
        self.assertFalse(snap.last_request_ok)

    def test_reset(self):
        mgr = AlexaStateManager()
        mgr.set_configured(True)
        mgr.set_linked(True)
        mgr.set_relay_connected(True)
        mgr.reset()
        snap = mgr.get_snapshot()
        self.assertEqual(snap.status, AlexaConnectionStatus.NOT_CONFIGURED)
        self.assertFalse(snap.configured)
        self.assertFalse(snap.linked)
        self.assertFalse(snap.relay_connected)

    def test_listener_notification(self):
        mgr = AlexaStateManager()
        events = []
        mgr.add_listener(lambda s: events.append(s.status))
        mgr.set_configured(True)
        mgr.set_linking_pending()
        mgr.set_linked(True)
        self.assertEqual(events, [
            AlexaConnectionStatus.READY_TO_LINK,
            AlexaConnectionStatus.LINK_PENDING,
            AlexaConnectionStatus.OFFLINE,
        ])


class TestSnapshotPrivacyWhitelist(unittest.TestCase):
    """Verify that AlexaSnapshot contains ONLY whitelisted fields and zero secret material."""

    def test_snapshot_fields_whitelist(self):
        expected_fields = {
            "status",
            "configured",
            "linked",
            "relay_connected",
            "last_request_ok",
            "allowed_intent_count",
        }
        actual_fields = set(AlexaSnapshot.__dataclass_fields__.keys())
        self.assertEqual(actual_fields, expected_fields, f"Unexpected fields in AlexaSnapshot: {actual_fields - expected_fields}")

        # Assert no forbidden terms in field names
        forbidden_substrings = ["token", "secret", "user", "device", "echo", "utterance", "url", "id", "password"]
        for f in actual_fields:
            if f == "allowed_intent_count":
                continue
            for sub in forbidden_substrings:
                self.assertNotIn(sub, f.lower(), f"Forbidden substring '{sub}' found in snapshot field '{f}'")


class TestAlexaProtocolAndLinking(unittest.TestCase):
    """Test protocol serialization, response truncation, and one-time linking token consumption."""

    def test_command_envelope_serialization(self):
        cmd = AlexaCommandEnvelope(
            version=1,
            type="command",
            request_id="test-req-123",
            intent="start_focus",
            arguments={"duration_s": 1500},
        )
        data = cmd.to_dict()
        self.assertEqual(data["version"], 1)
        self.assertEqual(data["type"], "command")
        self.assertEqual(data["intent"], "start_focus")

        parsed = parse_inbound_message(cmd.to_json())
        self.assertIsInstance(parsed, AlexaCommandEnvelope)
        self.assertEqual(parsed.request_id, "test-req-123")

    def test_result_envelope_truncation(self):
        long_speech = "A" * 1000
        res = AlexaResultEnvelope(
            version=1,
            type="result",
            request_id="test-req-123",
            status="ok",
            speech=long_speech,
        )
        json_str = res.to_json()
        import json
        payload = json.loads(json_str)
        self.assertEqual(len(payload["speech"]), ALEXA_MAX_RESPONSE_CHARS)

    def test_account_linking_one_time_consumption(self):
        alm = AccountLinkingManager(ttl_s=10.0)
        token = alm.create_linking_state("device-abc")
        self.assertTrue(alm.is_state_valid(token))

        # First consumption succeeds
        state = alm.consume_linking_state(token)
        self.assertIsNotNone(state)
        self.assertEqual(state.device_id, "device-abc")

        # Second consumption fails (one-time use)
        self.assertIsNone(alm.consume_linking_state(token))
        self.assertFalse(alm.is_state_valid(token))


if __name__ == "__main__":
    unittest.main()
