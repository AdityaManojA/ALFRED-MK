"""
tests/test_alexa_dispatcher.py — Unit tests for typed Alexa intent dispatch, safe command policy, and long-running command handling.
"""
import asyncio
import unittest
from unittest.mock import MagicMock

from core.integrations.alexa.client import AlexaRelayClient
from core.integrations.alexa.config import AlexaConfig
from core.integrations.alexa.dispatcher import AlexaTypedDispatcher
from core.integrations.alexa.policy import (
    AlexaActionPolicy,
    AlexaContext,
    AlexaRiskLevel,
)
from core.integrations.alexa.protocol import AlexaCommandEnvelope
from core.integrations.alexa.state import AlexaStateManager


class TestAlexaDispatcherAndPolicy(unittest.IsolatedAsyncioTestCase):
    """Test suite validating safe dispatch, policy enforcement, and background execution."""

    async def asyncSetUp(self):
        self.policy = AlexaActionPolicy()
        self.hud_logs: list[str] = []
        self.dispatcher = AlexaTypedDispatcher(
            policy=self.policy,
            hud_logger=lambda msg: self.hud_logs.append(msg),
        )

    async def test_safe_telemetry_dispatch(self):
        ctx = AlexaContext(request_id="test-req-1")
        speech = await self.dispatcher.dispatch("AlfredStatusIntent", {}, ctx)
        self.assertIn("systems", speech.lower())
        self.assertTrue(any("status" in log.lower() for log in self.hud_logs))

    async def test_focus_mode_dispatch(self):
        ctx = AlexaContext(request_id="test-req-2")
        speech = await self.dispatcher.dispatch("StartFocusIntent", {"duration": "PT30M"}, ctx)
        self.assertIn("30 minutes", speech)

        stop_speech = await self.dispatcher.dispatch("StopFocusIntent", {}, ctx)
        self.assertIn("concluded", stop_speech.lower())

    async def test_denied_command_dispatch(self):
        ctx = AlexaContext(request_id="test-req-3")
        # Direct attempt to invoke a shell / destructive command
        speech = await self.dispatcher.dispatch("shell", {"cmd": "dir"}, ctx)
        self.assertEqual(speech, "I am not permitted to perform that action through Alexa, sir.")

        speech2 = await self.dispatcher.dispatch("screenshot", {}, ctx)
        self.assertEqual(speech2, "I am not permitted to perform that action through Alexa, sir.")

    async def test_argument_injection_denial(self):
        ctx = AlexaContext(request_id="test-req-4")
        # Even with an allowed intent name, dangerous arguments are blocked
        speech = await self.dispatcher.dispatch(
            "AlfredStatusIntent",
            {"flag": "rmdir /s /q c:\\"},
            ctx,
        )
        self.assertEqual(speech, "I am not permitted to perform that action through Alexa, sir.")

    async def test_long_running_speed_test_immediate_ack(self):
        """Phase 8 compliance: speed test must return immediately without blocking Alexa deadline."""
        ctx = AlexaContext(request_id="test-req-5")
        t0 = asyncio.get_event_loop().time()
        speech = await self.dispatcher.dispatch("InternetSpeedIntent", {}, ctx)
        t1 = asyncio.get_event_loop().time()

        # Immediate return (< 0.1s)
        self.assertLess(t1 - t0, 0.1)
        self.assertIn("speed test is running", speech)
        self.assertIn("I’ll put the result in ALFRED", speech)

    async def test_dynamic_permission_toggle(self):
        """Phase 9 compliance: changing capability toggle immediately stops execution without reconnect."""
        ctx = AlexaContext(request_id="test-req-6")

        # Media enabled by default
        self.assertTrue(self.policy.is_capability_enabled("media_playback"))
        speech_ok = await self.dispatcher.dispatch("PauseMediaIntent", {}, ctx)
        self.assertIn("paused", speech_ok.lower())

        # Disable media playback
        self.policy.set_capability_enabled("media_playback", False)
        speech_blocked = await self.dispatcher.dispatch("PauseMediaIntent", {}, ctx)
        self.assertEqual(speech_blocked, "I am not permitted to perform that action through Alexa, sir.")


class TestAlexaRelayClientIdempotency(unittest.IsolatedAsyncioTestCase):
    """Test suite validating client-side idempotency and duplicate request rejection."""

    async def test_duplicate_request_idempotency(self):
        config = AlexaConfig(relay_ws_url="ws://localhost:9999/ws/desktop")
        state_mgr = AlexaStateManager()
        policy = AlexaActionPolicy()

        executed_count = 0

        async def dummy_handler(intent: str, args: dict) -> str:
            nonlocal executed_count
            executed_count += 1
            return "Executed"

        client = AlexaRelayClient(
            config=config,
            state_manager=state_mgr,
            policy=policy,
            command_handler=dummy_handler,
        )

        cmd = AlexaCommandEnvelope(
            version=1,
            type="command",
            request_id="unique-cmd-id-42",
            intent="AlfredStatusIntent",
            arguments={},
            deadline_ms=8000,
        )

        # First execution
        await client._process_command(cmd)
        self.assertEqual(executed_count, 1)

        # Duplicate execution with same request_id must be ignored
        await client._process_command(cmd)
        self.assertEqual(executed_count, 1)


if __name__ == "__main__":
    unittest.main()
