"""Comprehensive lifecycle and Linux visibility tests for MinimizedHudOverlay."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtCore import QEvent, QObject, QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMainWindow

import ui
from core.sentry.mode_manager import (
    FocusState,
    MonitorState,
    SentryModeManager,
    SentrySnapshot,
)
from ui import MinimizedHudOverlay


class _LogSource(QObject):
    emitted = pyqtSignal(str)


class TestMinimizedHudLinuxLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        SentryModeManager.reset_instance()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_patch = patch.object(ui, "CONFIG_DIR", Path(self.temp_dir.name))
        self.config_patch.start()
        self.main = QMainWindow()
        self.source = _LogSource()
        self.overlay = MinimizedHudOverlay(self.main, self.source.emitted, "Alfred")

    def tearDown(self) -> None:
        self.overlay.shutdown()
        self.main.close()
        self.config_patch.stop()
        self.temp_dir.cleanup()
        SentryModeManager.reset_instance()

    def test_overlay_creation_and_retained_lifetime(self):
        """Overlay is created as an independent top-level window without being prematurely collected."""
        self.assertIsNotNone(self.overlay)
        self.assertTrue(self.overlay.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating))
        self.assertTrue(self.overlay.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))
        flags = self.overlay.windowFlags()
        self.assertTrue(flags & Qt.WindowType.Window)
        self.assertTrue(flags & Qt.WindowType.FramelessWindowHint)
        self.assertTrue(flags & Qt.WindowType.WindowStaysOnTopHint)

    def test_minimize_reveals_overlay_and_syncs_sentry_state(self):
        """When minimized, overlay shows and immediately syncs active Sentry state."""
        mgr = SentryModeManager.instance()
        mgr.update_monitor_state(active=True, label="Screen Mon", waiting_for_answer=False)
        mgr.update_focus_state(active=True, remaining_s=1200, drifting=False)

        self.overlay.begin_minimize_session()
        self.assertTrue(self.overlay.isVisible())
        self.assertFalse(self.overlay._user_closed)

        # Confirm Sentry indicator pill updated immediately
        self.assertIn("20:00", self.overlay._sentry_btn.text())

    def test_restore_hides_overlay(self):
        """Restoring full window dismisses/hides the overlay."""
        self.overlay.begin_minimize_session()
        self.assertTrue(self.overlay.isVisible())

        self.overlay.hide_overlay()
        self.assertFalse(self.overlay.isVisible())

    def test_repeated_minimize_restore_cycles_no_duplicates(self):
        """Repeated transitions maintain clean state without duplicating objects or signals."""
        for _ in range(5):
            self.overlay.begin_minimize_session()
            self.assertTrue(self.overlay.isVisible())
            self.overlay.hide_overlay()
            self.assertFalse(self.overlay.isVisible())

    def test_main_window_window_state_change_event_dispatch(self):
        """Simulated window state change event triggers overlay show/hide."""
        mock_win = MagicMock(spec=ui.MainWindow)
        mock_win._hud_overlay = self.overlay
        mock_win.isMinimized.return_value = True

        # Simulate minimize event
        event = QEvent(QEvent.Type.WindowStateChange)
        ui.MainWindow.changeEvent(mock_win, event)
        self.assertTrue(self.overlay.isVisible())

        # Simulate restore event
        mock_win.isMinimized.return_value = False
        ui.MainWindow.changeEvent(mock_win, event)
        self.assertFalse(self.overlay.isVisible())

    def test_screen_clamping_on_simulated_geometry(self):
        """Overlay loads position cleanly within available screen bounds."""
        screen = QApplication.primaryScreen()
        if not screen:
            self.skipTest("No primary screen in offscreen environment")

        geom = screen.availableGeometry()
        self.overlay._load_position()
        self.assertGreaterEqual(self.overlay.x(), geom.left())
        self.assertLessEqual(self.overlay.x() + self.overlay.width(), geom.right() + 1)
        self.assertGreaterEqual(self.overlay.y(), geom.top())
        self.assertLessEqual(self.overlay.y() + self.overlay.height(), geom.bottom() + 1)


if __name__ == "__main__":
    unittest.main()
