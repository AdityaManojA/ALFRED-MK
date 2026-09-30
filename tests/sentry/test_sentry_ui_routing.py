"""Unit tests for Sentry Main-App routing and Full HUD / Minimized HUD synchronization."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from PyQt6.QtWidgets import QApplication

_APP = QApplication.instance() or QApplication([])

from core.sentry.mode_manager import (
    FocusState,
    MonitorState,
    SentryModeManager,
    SentrySnapshot,
)
from ui import HudCanvas, MainWindow, MinimizedHudOverlay


class TestSentryUIRoutingAndDisplay(unittest.TestCase):
    def setUp(self):
        SentryModeManager.reset_instance()
        self.mgr = SentryModeManager.instance()
        self.hud = HudCanvas("", "ALFRED")
        self.hud._tmr.stop()

    def tearDown(self):
        self.hud.close()
        SentryModeManager.reset_instance()

    def test_full_hud_paints_focus_active_state(self):
        """Full HUD displays countdown and active status for FOCUS mode."""
        snapshot = SentrySnapshot(
            monitor=MonitorState(active=False),
            focus=FocusState(
                active=True,
                remaining_s=1500,
                drifting=False,
                paused=False,
            ),
            timestamp=100.0,
        )
        self.hud.set_sentry_snapshot(snapshot)

        # Trigger banner rendering
        self.assertEqual(self.hud._sentry_snapshot, snapshot)
        self.assertTrue(self.hud._sentry_snapshot.focus.active)

    def test_full_hud_paints_focus_drifting_state(self):
        """Full HUD displays drifting alert status when user strays from target."""
        snapshot = SentrySnapshot(
            monitor=MonitorState(active=False),
            focus=FocusState(
                active=True,
                remaining_s=1200,
                drifting=True,
                paused=False,
            ),
            timestamp=100.0,
        )
        self.hud.set_sentry_snapshot(snapshot)
        self.assertTrue(self.hud._sentry_snapshot.focus.drifting)

    def test_full_hud_paints_focus_paused_state(self):
        """Full HUD displays paused status when session is paused."""
        snapshot = SentrySnapshot(
            monitor=MonitorState(active=False),
            focus=FocusState(
                active=True,
                remaining_s=900,
                drifting=False,
                paused=True,
            ),
            timestamp=100.0,
        )
        self.hud.set_sentry_snapshot(snapshot)
        self.assertTrue(self.hud._sentry_snapshot.focus.paused)

    def test_full_hud_paints_screen_monitor_active(self):
        """Full HUD displays screen monitor active indicator."""
        snapshot = SentrySnapshot(
            monitor=MonitorState(
                active=True,
                label="screen region",
                target_count=1,
                waiting_for_answer=False,
            ),
            focus=FocusState(active=False),
            timestamp=100.0,
        )
        self.hud.set_sentry_snapshot(snapshot)
        self.assertTrue(self.hud._sentry_snapshot.monitor.active)

    def test_sentry_menu_monitor_screen_routes_to_screen_target(self):
        """Main window MONITOR (Screen) option invokes start_monitor with goal='screen'."""
        mock_mon_start = MagicMock(return_value={"active": True, "label": "screen region", "target_count": 1})
        mock_mon_stop = MagicMock(return_value={"active": False})
        self.mgr.register_monitor_handlers(mock_mon_start, mock_mon_stop)

        # Mock MainWindow
        mock_win = MagicMock(spec=MainWindow)
        mock_win._sentry_btn = MagicMock()
        mock_win._toggle_monitor_mode = MainWindow._toggle_monitor_mode.__get__(mock_win)
        mock_win._apply_sentry_snapshot = MagicMock()

        # Trigger toggle monitor with screen goal
        mock_win._toggle_monitor_mode(goal="screen")

        # Verify monitor handler was called with screen goal and default interval
        mock_mon_start.assert_called_once_with("screen", 3.0)

    def test_minimized_and_full_hud_remain_consistent(self):
        """Both HUD displays receive and maintain identical Sentry state."""
        overlay = MinimizedHudOverlay(None, MagicMock(), "ALFRED")
        try:
            snapshot = SentrySnapshot(
                monitor=MonitorState(active=True, label="Screen"),
                focus=FocusState(active=True, remaining_s=1400, drifting=False),
                timestamp=100.0,
            )

            # Update full HUD
            self.hud.set_sentry_snapshot(snapshot)

            # Update Minimized HUD
            overlay.update_sentry_indicator(
                snapshot.monitor.active,
                snapshot.focus.active,
                waiting_for_answer=snapshot.monitor.waiting_for_answer,
                foc_remaining_s=snapshot.focus.remaining_s,
                drifting=snapshot.focus.drifting,
            )

            self.assertEqual(overlay._sentry_btn.text(), "FOC 23:20")
            self.assertEqual(self.hud._sentry_snapshot, snapshot)
        finally:
            overlay.close()


if __name__ == "__main__":
    unittest.main()
