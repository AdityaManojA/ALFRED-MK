"""
tests/test_tactical_controls_drawer.py — Unit tests verifying Tactical Controls Quick Drawer.

Tests:
1. Cross-platform window flags (Tool on Windows, Dialog on Linux/macOS)
2. Translucent background configuration and paintEvent
3. Draggability and mouse event handling (drag, move, release, double-click reset)
4. Keyboard navigation (Escape closes drawer)
5. Tactical header with close button (✕) synchronizing with _drawer_btn state
6. Positioning logic relative to _drawer_btn and preserving custom dragged positions
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint, QPointF, Qt, QTimer
from PyQt6.QtGui import QKeyEvent, QMouseEvent
from PyQt6.QtWidgets import QApplication, QPushButton, QWidget

# Ensure app instance exists
_app = QApplication.instance()
if _app is None:
    _app = QApplication(["test", "-platform", "offscreen"])

from ui import MainWindow, TacticalControlsDrawer, C


class TestTacticalControlsDrawer(unittest.TestCase):

    def test_window_flags_and_translucent_attributes(self):
        """Verify window flags and translucent background attributes across platforms."""
        parent = QWidget()
        drawer = TacticalControlsDrawer(parent=parent)
        drawer_standalone = TacticalControlsDrawer()
        try:
            if sys.platform == "win32":
                self.assertTrue(bool(drawer.windowFlags() & Qt.WindowType.FramelessWindowHint))
                self.assertTrue(bool(drawer.windowFlags() & Qt.WindowType.Tool))
                self.assertTrue(drawer.isWindow())
            else:
                self.assertFalse(drawer.isWindow())

            self.assertTrue(bool(drawer_standalone.windowFlags() & Qt.WindowType.FramelessWindowHint))
            self.assertTrue(drawer_standalone.isWindow())

            self.assertTrue(drawer.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))
            self.assertTrue(drawer.testAttribute(Qt.WidgetAttribute.WA_StyledBackground))
        finally:
            drawer.close()
            drawer_standalone.close()
            parent.close()

    def test_paint_event_runs_cleanly(self):
        """Verify paintEvent executes and paints translucent tactical background without errors."""
        drawer = TacticalControlsDrawer()
        drawer.resize(286, 400)
        try:
            # Trigger paintEvent directly via repaint / render
            drawer.repaint()
        finally:
            drawer.close()

    def test_draggability_and_mouse_events(self):
        """Verify dragging updates the drawer's position and sets _user_moved flag."""
        parent = QWidget()
        parent.setGeometry(100, 100, 800, 600)
        drawer = TacticalControlsDrawer(parent=parent)
        drawer.setGeometry(120, 150, 286, 350)
        try:
            self.assertFalse(drawer._is_dragging)
            self.assertFalse(drawer._user_moved)

            # 1. Simulate mouse press on header (at local 50, 10)
            press_ev = QMouseEvent(
                QMouseEvent.Type.MouseButtonPress,
                QPointF(50, 10),
                QPointF(170, 160),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            drawer.mousePressEvent(press_ev)
            self.assertTrue(drawer._is_dragging)
            self.assertEqual(drawer._drag_window_pos, QPoint(120, 150))

            # 2. Simulate mouse move (delta +50, +30)
            move_ev = QMouseEvent(
                QMouseEvent.Type.MouseMove,
                QPointF(100, 40),
                QPointF(220, 190),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            drawer.mouseMoveEvent(move_ev)
            self.assertTrue(drawer._user_moved)
            self.assertEqual(drawer.pos(), QPoint(170, 180))
            self.assertIsNotNone(drawer._relative_offset)

            # 3. Simulate mouse release
            release_ev = QMouseEvent(
                QMouseEvent.Type.MouseButtonRelease,
                QPointF(100, 40),
                QPointF(220, 190),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier,
            )
            drawer.mouseReleaseEvent(release_ev)
            self.assertFalse(drawer._is_dragging)

            # 4. Double click should reset _user_moved to False
            dbl_ev = QMouseEvent(
                QMouseEvent.Type.MouseButtonDblClick,
                QPointF(50, 10),
                QPointF(220, 190),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            drawer.mouseDoubleClickEvent(dbl_ev)
            self.assertFalse(drawer._user_moved)
            self.assertIsNone(drawer._relative_offset)
        finally:
            drawer.close()
            parent.close()

    def test_key_press_escape_closes_drawer(self):
        """Verify pressing Escape emits closed signal and hides drawer."""
        drawer = TacticalControlsDrawer()
        drawer.show()
        closed_emitted = []
        drawer.closed.connect(lambda: closed_emitted.append(True))
        try:
            esc_ev = QKeyEvent(
                QKeyEvent.Type.KeyPress,
                Qt.Key.Key_Escape,
                Qt.KeyboardModifier.NoModifier,
            )
            drawer.keyPressEvent(esc_ev)
            self.assertFalse(drawer.isVisible())
            self.assertEqual(closed_emitted, [True])
        finally:
            drawer.close()

    def test_close_button_synchronizes_with_main_window_drawer_btn(self):
        """Verify clicking close button on header unchecks MainWindow._drawer_btn."""
        window = MainWindow("")
        try:
            window.show()
            window._drawer_btn.setChecked(True)
            window._toggle_drawer(True)
            self.assertTrue(window._quick_drawer.isVisible())

            # Find the close button inside drawer header
            close_buttons = [b for b in window._quick_drawer.findChildren(QPushButton) if b.text() == "✕"]
            self.assertEqual(len(close_buttons), 1)
            close_btn = close_buttons[0]

            # Click close button
            close_btn.click()
            self.assertFalse(window._quick_drawer.isVisible())
            self.assertFalse(window._drawer_btn.isChecked())
        finally:
            window.close()

    def test_position_quick_drawer_default_and_dragged(self):
        """Verify positioning defaults under _drawer_btn and preserves offset when moved."""
        window = MainWindow("")
        try:
            window.setGeometry(100, 100, 1000, 700)
            window.show()
            drawer = window._quick_drawer

            # Default positioning
            window._position_quick_drawer()
            if drawer.isWindow():
                btn_pos = window._drawer_btn.mapToGlobal(QPoint(0, window._drawer_btn.height() + 4))
                self.assertEqual(drawer.x(), btn_pos.x())
                self.assertEqual(drawer.y(), btn_pos.y())

                # Mark user moved with offset
                drawer._user_moved = True
                drawer._relative_offset = QPoint(300, 200)
                window._position_quick_drawer()
                self.assertEqual(drawer.pos(), window.pos() + QPoint(300, 200))
            else:
                parent_w = drawer.parentWidget() or window.centralWidget() or window
                btn_pos = window._drawer_btn.mapTo(parent_w, QPoint(0, window._drawer_btn.height() + 4))
                self.assertEqual(drawer.x(), btn_pos.x())
                self.assertEqual(drawer.y(), btn_pos.y())

                # Mark user moved with offset
                drawer._user_moved = True
                drawer._relative_offset = QPoint(150, 120)
                window._position_quick_drawer()
                self.assertEqual(drawer.pos(), QPoint(150, 120))
        finally:
            window.close()

    def test_linux_in_window_child_anchoring_and_no_center_overlap(self):
        """Verify on Linux (non-Windows) drawer is an in-window child overlay anchored directly under button."""
        with patch("sys.platform", "linux"):
            window = MainWindow("")
            try:
                window.setGeometry(200, 100, 1120, 720)
                window.show()
                drawer = window._quick_drawer

                # On Linux, drawer MUST NOT be a top-level window (which Mutter/Wayland centers)
                self.assertFalse(drawer.isWindow())
                self.assertIsNotNone(drawer.parentWidget())

                # Default positioning must anchor directly underneath _drawer_btn
                window._position_quick_drawer()
                parent_w = drawer.parentWidget() or window.centralWidget() or window
                expected_anchor = window._drawer_btn.mapTo(parent_w, QPoint(0, window._drawer_btn.height() + 4))

                self.assertEqual(drawer.x(), expected_anchor.x())
                self.assertEqual(drawer.y(), expected_anchor.y())

                # Verify it does NOT center or overlap the middle HUD
                # On an 1120x720 window, middle X is 560, middle Y is 360
                self.assertLess(drawer.x(), 100)  # Near the left margin (~14px)
                self.assertLess(drawer.y(), 100)  # Just under header bar (~34-40px)

                # Simulate dragging within window bounds
                drawer._is_dragging = True
                drawer._drag_start_pos = QPoint(50, 50)
                drawer._drag_window_pos = drawer.pos()
                move_ev = QMouseEvent(
                    QMouseEvent.Type.MouseMove,
                    QPointF(90, 80),
                    QPointF(90, 80),
                    Qt.MouseButton.LeftButton,
                    Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.NoModifier,
                )
                drawer.mouseMoveEvent(move_ev)
                self.assertTrue(drawer._user_moved)
                self.assertEqual(drawer.pos(), drawer._drag_window_pos + QPoint(40, 30))

                # Double-click must reset directly back under _drawer_btn
                dbl_ev = QMouseEvent(
                    QMouseEvent.Type.MouseButtonDblClick,
                    QPointF(10, 10),
                    QPointF(10, 10),
                    Qt.MouseButton.LeftButton,
                    Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.NoModifier,
                )
                drawer.mouseDoubleClickEvent(dbl_ev)
                self.assertFalse(drawer._user_moved)
                self.assertEqual(drawer.x(), expected_anchor.x())
                self.assertEqual(drawer.y(), expected_anchor.y())
            finally:
                window.close()


if __name__ == "__main__":
    unittest.main()
