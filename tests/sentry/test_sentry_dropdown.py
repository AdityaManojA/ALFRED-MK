"""Tests for Phase 1 Sentry dropdown menu and dual mode controls."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from PyQt6.QtWidgets import QApplication

_APP = QApplication.instance() or QApplication([])

from core.sentry.mode_manager import (
    FocusState,
    MonitorState,
    SentryModeManager,
    SentrySnapshot,
    get_sentry_mode_manager,
)
from ui import MainWindow, MinimizedHudOverlay


class _FakeButton:
    def __init__(self) -> None:
        self.checked = False
        self.text = ""
        self.tooltip = ""

    def setChecked(self, value: bool) -> None:
        self.checked = value

    def isChecked(self) -> bool:
        return self.checked

    def setText(self, value: str) -> None:
        self.text = value

    def setToolTip(self, value: str) -> None:
        self.tooltip = value


class TestSentryDropdownIntegration(unittest.TestCase):
    def setUp(self):
        SentryModeManager.reset_instance()
        self.mgr = SentryModeManager.instance()

    def tearDown(self):
        SentryModeManager.reset_instance()

    def _make_window_shim(self):
        window = SimpleNamespace(
            _sentry_btn=_FakeButton(),
        )
        window._apply_sentry_snapshot = lambda snap: MainWindow._apply_sentry_snapshot(window, snap)
        window._toggle_monitor_mode = lambda: MainWindow._toggle_monitor_mode(window)
        window._toggle_focus_mode = lambda: MainWindow._toggle_focus_mode(window)
        return window

    def test_sentry_menu_actions_and_labels(self):
        window = self._make_window_shim()
        menu = MainWindow._create_sentry_menu(window)
        actions = [a for a in menu.actions() if not a.isSeparator()]
        self.assertGreaterEqual(len(actions), 2)
        self.assertTrue(any("MONITOR" in a.text() for a in actions))
        self.assertTrue(any("FOCUS" in a.text() for a in actions))

        # Now start monitor and re-verify action labels
        self.mgr.start_monitor("Test Monitor")
        menu2 = MainWindow._create_sentry_menu(window)
        actions2 = [a for a in menu2.actions() if not a.isSeparator()]
        self.assertTrue(any("MONITOR (ON)" in a.text() for a in actions2))
        self.assertTrue(any("FOCUS (OFF)" in a.text() for a in actions2))

    def test_dropdown_toggles_modes_independently(self):
        window = self._make_window_shim()

        # Toggle monitor via menu
        MainWindow._toggle_monitor_mode(window)
        snap = self.mgr.get_snapshot()
        self.assertTrue(snap.monitor.active)
        self.assertFalse(snap.focus.active)
        self.assertEqual(window._sentry_btn.text, "[ ◈ ]  SCREEN MONITORING")
        self.assertTrue(window._sentry_btn.checked)

        # Toggle focus via menu
        MainWindow._toggle_focus_mode(window)
        snap2 = self.mgr.get_snapshot()
        self.assertTrue(snap2.monitor.active)
        self.assertTrue(snap2.focus.active)
        self.assertEqual(window._sentry_btn.text, "[ ◈◉ ] SENTRY (2)")
        self.assertTrue(window._sentry_btn.checked)

        # Toggle monitor off
        MainWindow._toggle_monitor_mode(window)
        snap3 = self.mgr.get_snapshot()
        self.assertFalse(snap3.monitor.active)
        self.assertTrue(snap3.focus.active)
        self.assertEqual(window._sentry_btn.text, "[ ◉ ]  FOCUS MODE")

        # Toggle focus off
        MainWindow._toggle_focus_mode(window)
        snap4 = self.mgr.get_snapshot()
        self.assertFalse(snap4.monitor.active)
        self.assertFalse(snap4.focus.active)
        self.assertEqual(window._sentry_btn.text, "[ ▣ ]  SENTRY MODE")
        self.assertFalse(window._sentry_btn.checked)

    def test_minimized_overlay_has_sentry_button_and_indicator(self):
        source = SimpleNamespace(connect=MagicMock())
        main = SimpleNamespace(_show_sentry_menu=MagicMock())
        overlay = MinimizedHudOverlay(main, source, "Alfred")
        try:
            self.assertTrue(hasattr(overlay, "_sentry_btn"))
            self.assertEqual(overlay._sentry_btn.text(), "S")

            overlay.update_sentry_indicator(mon_active=True, foc_active=False)
            self.assertIn("MON", overlay._sentry_btn.text())

            overlay.update_sentry_indicator(mon_active=False, foc_active=True)
            self.assertIn("FOC", overlay._sentry_btn.text())

            overlay.update_sentry_indicator(mon_active=False, foc_active=False)
            self.assertEqual(overlay._sentry_btn.text(), "S")
        finally:
            overlay.close()


if __name__ == "__main__":
    unittest.main()
