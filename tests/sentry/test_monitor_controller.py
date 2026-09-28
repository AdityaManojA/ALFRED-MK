"""Unit and integration tests for MonitorController and actions/sentry_monitor.py."""
import asyncio
import time
import unittest
from unittest.mock import MagicMock, patch

from core.sentry.mode_manager import get_sentry_mode_manager
from core.sentry.monitor.controller import MonitorController, get_monitor_controller
from core.sentry.monitor.targets.terminal import TerminalTarget
from core.sentry.monitor.targets.window_title import WindowTitleTarget
from actions.sentry_monitor import sentry_monitor_action


class TestMonitorController(unittest.TestCase):
    def setUp(self):
        self.mgr = get_sentry_mode_manager()
        self.spoken = []
        self.status_logs = []
        self.un_gated_calls = []

        self.controller = get_monitor_controller()
        self.controller.set_callbacks(
            speak_fn=lambda txt: self.spoken.append(txt),
            un_gate_fn=lambda active: self.un_gated_calls.append(active),
            status_fn=lambda txt: self.status_logs.append(txt),
        )
        self.mgr.register_monitor_handlers(
            on_start=self.controller.start,
            on_stop=self.controller.stop,
        )

    def tearDown(self):
        self.controller.stop("Tear down")

    def test_voice_prompt_and_answer_flow(self):
        """Verify flow: start() with no target asks question, receives answer via submit_answer(), parses both targets."""
        # 1. Start without goal -> triggers prompt flow
        res = self.controller.start()
        self.assertTrue(res["active"])
        self.assertEqual(res["target_count"], 0)

        # Give the worker thread a moment to open the answer window
        for _ in range(20):
            if self.controller.is_waiting_for_answer:
                break
            time.sleep(0.05)

        self.assertTrue(self.controller.is_waiting_for_answer)
        self.assertTrue(any("What shall I keep an eye on" in s for s in self.spoken))

        # 2. User answers the exact prompt requirement
        user_answer = "watch the build in the terminal and tell me when Chrome's title says Deployed"
        accepted = self.controller.submit_answer(user_answer)
        self.assertTrue(accepted)

        # Wait for targets to be parsed and added to scheduler
        for _ in range(20):
            if self.controller.scheduler.target_count == 2:
                break
            time.sleep(0.05)

        self.assertEqual(self.controller.scheduler.target_count, 2)
        self.assertTrue(self.controller.scheduler.is_running)
        self.assertFalse(self.controller.is_waiting_for_answer)

        # 3. Mode manager state reflects the new targets
        snap = self.mgr.get_snapshot()
        self.assertTrue(snap.monitor.active)
        self.assertEqual(snap.monitor.target_count, 2)

        # 4. Spoken confirmation was issued
        self.assertTrue(any("Understood, sir" in s for s in self.spoken))

    def test_action_tool_invocations(self):
        """Test sentry_monitor_action dispatching."""
        # Start with explicit target
        out = sentry_monitor_action("start", target="watch process python.exe")
        self.assertIn("activated", out)
        self.assertEqual(self.controller.scheduler.target_count, 1)

        # Query status
        status_str = sentry_monitor_action("status")
        self.assertIn("process", status_str.lower())

        # Tune cooldown
        q_out = sentry_monitor_action("quieter")
        self.assertIn("increased", q_out.lower())

        l_out = sentry_monitor_action("louder")
        self.assertIn("decreased", l_out.lower())

        # Stop
        stop_out = sentry_monitor_action("stop")
        self.assertIn("stopped", stop_out.lower())
        self.assertFalse(self.controller.scheduler.is_running)


if __name__ == "__main__":
    unittest.main()
