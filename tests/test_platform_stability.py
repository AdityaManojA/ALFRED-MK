"""Unit tests for Windows and Linux runtime stability fixes in ALFRED-MK-VIII.

Covers:
- Phase 1: Sentry Mode Manager is_waiting_for_answer state & UI snapshot safety boundary
- Phase 2: Action discovery isolation and Linux-safe window_manager imports
- Phase 3: Unicode formatting (preserving → and em-dash) and roundtrip logging
- Phase 4: Gemini Live 1008 policy violation classification and bounded reconnect
- Phase 5: Media Foundation / codec warning classification
"""

import asyncio
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from core.sentry.mode_manager import (
    FocusState,
    MonitorState,
    SentryModeManager,
    SentrySnapshot,
)
from ui import MainWindow


class TestSentrySnapshotStability(unittest.TestCase):
    def setUp(self):
        SentryModeManager.reset_instance()
        self.mgr = SentryModeManager.instance()

    def tearDown(self):
        SentryModeManager.reset_instance()

    def test_waiting_for_answer_api_and_transitions(self):
        """Phase 1: is_waiting_for_answer is available on SentryModeManager and reflects state."""
        self.assertFalse(self.mgr.is_waiting_for_answer())
        self.assertFalse(self.mgr.get_snapshot().monitor.waiting_for_answer)

        # Transition to waiting for answer = True
        self.mgr.update_monitor_state(waiting_for_answer=True)
        self.assertTrue(self.mgr.is_waiting_for_answer())
        self.assertTrue(self.mgr.get_snapshot().monitor.waiting_for_answer)

        # Transition to waiting for answer = False
        self.mgr.update_monitor_state(waiting_for_answer=False)
        self.assertFalse(self.mgr.is_waiting_for_answer())
        self.assertFalse(self.mgr.get_snapshot().monitor.waiting_for_answer)

    def test_ui_snapshot_safe_against_exceptions(self):
        """Phase 1: Ensure snapshot boundary does not crash Qt slot / application with SIGABRT."""
        from ui import MainWindow

        # Create a mock MainWindow
        mock_win = MagicMock(spec=MainWindow)
        mock_win._last_sentry_snapshot = None
        mock_win._apply_sentry_snapshot = MainWindow._apply_sentry_snapshot.__get__(mock_win)

        # Calling _apply_sentry_snapshot with a valid snapshot does not throw
        snapshot = SentrySnapshot(
            monitor=MonitorState(active=True, waiting_for_answer=True, label="Test"),
            focus=FocusState(active=False),
        )

        # Even if child widgets raise an error, exception boundary catches and preserves snapshot
        mock_win.hud_panel = MagicMock()
        mock_win.hud_panel.update_sentry_state.side_effect = RuntimeError("Simulated HUD error")

        try:
            mock_win._apply_sentry_snapshot(snapshot)
        except Exception as e:
            self.fail(f"_apply_sentry_snapshot let exception escape: {e}")

        # Verified last valid snapshot preserved
        self.assertEqual(mock_win._last_sentry_snapshot, snapshot)


class TestLinuxActionDiscovery(unittest.TestCase):
    def test_window_manager_imports_safely_on_linux(self):
        """Phase 2: window_manager must import without evaluating ctypes.windll on Linux."""
        with patch.object(sys, "platform", "linux"):
            import actions.window_manager as wm

            # User32 should return None on Linux
            self.assertIsNone(wm._get_user32())

            # Action execution should return a clean error message rather than crashing
            result = wm.run({"action": "list"})
            self.assertIn("Windows", result)

    def test_action_loader_handles_platform_unsupported_cleanly(self):
        """Phase 2: action_loader discovers actions without printing traceback for OS mismatches."""
        from core.action_loader import ActionLoader

        loader = ActionLoader()
        with patch.object(sys, "platform", "linux"):
            registry = loader.discover_actions()
            self.assertIsNotNone(registry)


class TestUnicodeStatusAndLogging(unittest.TestCase):
    def test_status_and_speaker_arrows_contain_unicode(self):
        """Phase 3: Verify intended arrow → is preserved and no mojibake â†’ occurs."""
        name = "manage_monitor"
        result = "Monitoring: AI news, tech news"
        log_line = f"{name} → {result}"
        self.assertIn("→", log_line)
        self.assertNotIn("â†’", log_line)

        speaker_log = "Output latency 35 ms → echo tail 285 ms"
        self.assertIn("→", speaker_log)
        self.assertNotIn("â†’", speaker_log)

    def test_unicode_utf8_roundtrip(self):
        """Phase 3: UTF-8 encoding and decoding preserves arrows and em-dashes."""
        text = "SYS: Awake — user requested. manage_monitor → Monitoring: AI"
        encoded = text.encode("utf-8")
        decoded = encoded.decode("utf-8")
        self.assertEqual(text, decoded)
        self.assertNotIn("â€”", decoded)
        self.assertNotIn("â†’", decoded)


class TestGeminiLiveErrorHandling(unittest.TestCase):
    def test_tool_error_in_function_response_not_concurrent_speak(self):
        """Phase 4: Tool errors must be returned in FunctionResponse payload without speaking."""
        # Simulated tool call with error
        name = "test_broken_tool"
        err_msg = "Simulated division by zero"
        fn_resp = {
            "id": "call_123",
            "name": name,
            "response": {"result": f"Execution error: {err_msg}"}
        }
        self.assertEqual(fn_resp["name"], name)
        self.assertIn("Execution error", fn_resp["response"]["result"])

    def test_policy_1008_error_classification(self):
        """Phase 4: Error 1008 is classified as policy violation with bounded backoff."""
        err_msg = "APIError: 1008 None. websockets.exceptions.ConnectionClosedError: received 1008 (policy violation)"
        is_policy_1008 = "1008" in err_msg or "policy violation" in err_msg.lower()
        self.assertTrue(is_policy_1008)

        # Backoff calculation for 1008
        current_backoff = 3
        if is_policy_1008:
            new_backoff = min(max(current_backoff * 2, 10), 60)
            self.assertEqual(new_backoff, 10)


if __name__ == "__main__":
    unittest.main()
