import time
import unittest
from unittest.mock import MagicMock

from PyQt6.QtWidgets import QApplication

# Ensure QApplication exists for Qt signals
_APP = QApplication.instance() or QApplication([])

from core.sentry.mode_manager import (
    FocusState,
    MonitorState,
    SentryModeManager,
    SentrySnapshot,
    get_sentry_mode_manager,
)


class TestSentryModeManager(unittest.TestCase):
    def setUp(self):
        SentryModeManager.reset_instance()
        self.mgr = SentryModeManager.instance()

    def tearDown(self):
        SentryModeManager.reset_instance()

    def test_singleton_identity(self):
        m1 = SentryModeManager.instance()
        m2 = get_sentry_mode_manager()
        self.assertIs(m1, m2)
        self.assertIs(m1, self.mgr)

    def test_initial_state_is_inactive(self):
        snap = self.mgr.get_snapshot()
        self.assertFalse(snap.monitor.active)
        self.assertEqual(snap.monitor.target_count, 0)
        self.assertFalse(snap.focus.active)
        self.assertEqual(snap.focus.planned_s, 0)

    def test_independent_mode_toggling(self):
        # Start MONITOR alone
        mock_mon_start = MagicMock(return_value={"active": True, "label": "Testing Terminal", "target_count": 1})
        mock_mon_stop = MagicMock(return_value={"active": False})
        self.mgr.register_monitor_handlers(mock_mon_start, mock_mon_stop)

        res = self.mgr.start_monitor("Terminal Build", 5.0)
        self.assertTrue(res["active"])
        mock_mon_start.assert_called_once_with("Terminal Build", 5.0)

        # Monitor is active, Focus remains inactive
        snap = self.mgr.get_snapshot()
        self.assertTrue(snap.monitor.active)
        self.assertEqual(snap.monitor.label, "Testing Terminal")
        self.assertEqual(snap.monitor.target_count, 1)
        self.assertFalse(snap.focus.active)

        # Now start FOCUS concurrently
        mock_foc_start = MagicMock(return_value={"active": True, "deferred_lock": True})
        mock_foc_stop = MagicMock(return_value={"active": False})
        self.mgr.register_focus_handlers(mock_foc_start, mock_foc_stop)

        foc_res = self.mgr.start_focus(duration_minutes=25, intent="Finish Sentry v2")
        self.assertTrue(foc_res["active"])
        mock_foc_start.assert_called_once_with(25, "Finish Sentry v2")

        # Both modes are now active simultaneously
        snap2 = self.mgr.get_snapshot()
        self.assertTrue(snap2.monitor.active)
        self.assertTrue(snap2.focus.active)
        self.assertEqual(snap2.focus.planned_s, 1500)
        self.assertTrue(snap2.focus.intent_set)

        # Stop MONITOR, FOCUS remains running
        self.mgr.stop_monitor("Build finished")
        snap3 = self.mgr.get_snapshot()
        self.assertFalse(snap3.monitor.active)
        self.assertTrue(snap3.focus.active)

        # Stop FOCUS
        self.mgr.stop_focus("Session complete")
        snap4 = self.mgr.get_snapshot()
        self.assertFalse(snap4.monitor.active)
        self.assertFalse(snap4.focus.active)

    def test_whitelist_fields_only(self):
        # Verify no extraneous private state leaks into the snapshot
        snap = self.mgr.get_snapshot()
        mon_fields = set(MonitorState.__dataclass_fields__.keys())
        foc_fields = set(FocusState.__dataclass_fields__.keys())

        expected_mon = {"active", "target_count", "last_alert_s", "label"}
        expected_foc = {
            "active", "paused", "deferred_lock", "locked_app", "locked_tab",
            "planned_s", "elapsed_s", "on_target_s", "remaining_s",
            "drifting", "drift_count", "current_drift_s", "tier",
            "snoozed_until_s", "excused", "nag_interval_s", "intent_set"
        }
        self.assertEqual(mon_fields, expected_mon)
        self.assertEqual(foc_fields, expected_foc)

    def test_state_change_rate_limit(self):
        emitted_snapshots = []
        self.mgr.state_changed.connect(lambda s: emitted_snapshots.append(s))

        # First emit happens immediately
        self.mgr._emit_state_change(force=True)
        self.assertEqual(len(emitted_snapshots), 1)

        # Rapid updates within 1 second do not emit duplicate signals
        self.mgr.update_focus_state(elapsed_s=1)
        self.mgr.update_focus_state(elapsed_s=2)
        self.assertEqual(len(emitted_snapshots), 1)

        # Force emit bypasses throttle for critical mode state transitions
        self.mgr._emit_state_change(force=True)
        self.assertEqual(len(emitted_snapshots), 2)


if __name__ == "__main__":
    unittest.main()
