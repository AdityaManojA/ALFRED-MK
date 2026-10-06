"""
tests/test_linux_hud_drag.py — Tests for cross-platform drag handler, Linux HUD visibility, and coordinate persistence.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QGuiApplication, QMouseEvent
from PyQt6.QtWidgets import QApplication, QWidget

# Ensure headless test environment has QApplication
app = QApplication.instance() or QApplication([])

from ui.drag_handler import (
    DRAG_THRESHOLD_PX,
    MAX_HEADER_DRAG_Y_PX,
    CrossPlatformDragHandler,
    calculate_top_right_quadrant,
    is_tiling_wm,
    is_wayland,
    load_window_position,
    save_window_position,
)


class TestUiStatePersistence(unittest.TestCase):
    """Test saving and loading window positions to data/ui_state.json."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.tmp_dir.name) / "ui_state.json"

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_save_and_load_window_position(self):
        with patch("ui.drag_handler.UI_STATE_FILE", self.state_file):
            with patch("ui.drag_handler.DATA_DIR", Path(self.tmp_dir.name)):
                save_window_position("bat_globe", 200, 120)
                save_window_position("mini_hud", 150, 100)

                self.assertTrue(self.state_file.exists())
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                self.assertEqual(data["bat_globe"], {"x": 200, "y": 120})
                self.assertEqual(data["mini_hud"], {"x": 150, "y": 100})

                pos_globe = load_window_position("bat_globe", 260, 260)
                self.assertEqual(pos_globe.x(), 200)
                self.assertEqual(pos_globe.y(), 120)

                pos_hud = load_window_position("mini_hud", 420, 230)
                self.assertEqual(pos_hud.x(), 150)
                self.assertEqual(pos_hud.y(), 100)

    def test_first_boot_top_right_quadrant_default(self):
        """When no state file exists, calculate position in top-right quadrant."""
        empty_file = Path(self.tmp_dir.name) / "nonexistent.json"
        with patch("ui.drag_handler.UI_STATE_FILE", empty_file):
            pos = load_window_position("bat_globe", 260, 260)
            primary_screen = QGuiApplication.primaryScreen()
            if primary_screen:
                bounds = primary_screen.availableGeometry()
                expected_x = max(bounds.left(), bounds.right() - 260 - 24)
                expected_y = max(bounds.top(), bounds.top() + 48)
                self.assertEqual(pos.x(), expected_x)
                self.assertEqual(pos.y(), expected_y)


class TestCrossPlatformDragHandler(unittest.TestCase):
    """Test platform branching: Wayland startSystemMove vs X11/Win32 move math."""

    def test_wayland_detection(self):
        with patch("PyQt6.QtGui.QGuiApplication.platformName", return_value="wayland"):
            self.assertTrue(is_wayland())

        with patch("PyQt6.QtGui.QGuiApplication.platformName", return_value="xcb"):
            with patch.dict(os.environ, {"XDG_SESSION_TYPE": "x11", "WAYLAND_DISPLAY": ""}, clear=True):
                self.assertFalse(is_wayland())

        with patch("PyQt6.QtGui.QGuiApplication.platformName", return_value="windows"):
            with patch.dict(os.environ, {}, clear=True):
                self.assertFalse(is_wayland())

    def test_tiling_wm_detection(self):
        with patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "i3"}, clear=True):
            self.assertTrue(is_tiling_wm())

        with patch.dict(os.environ, {"DESKTOP_SESSION": "sway"}, clear=True):
            self.assertTrue(is_tiling_wm())

        with patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "GNOME"}, clear=True):
            self.assertFalse(is_tiling_wm())

    def test_wayland_delegates_to_start_system_move(self):
        """On Wayland, exceeding threshold triggers windowHandle().startSystemMove()."""
        handler = CrossPlatformDragHandler(threshold_px=DRAG_THRESHOLD_PX)
        mock_widget = MagicMock(spec=QWidget)
        mock_widget.pos.return_value = QPoint(100, 100)
        mock_widget.frameGeometry.return_value.topLeft.return_value = QPoint(100, 100)

        mock_window_handle = MagicMock()
        mock_widget.windowHandle.return_value = mock_window_handle

        press_event = MagicMock(spec=QMouseEvent)
        press_event.button.return_value = Qt.MouseButton.LeftButton
        press_event.position.return_value = QPointF(50, 20)
        press_event.globalPosition.return_value = QPointF(150, 120)

        # 1. Press
        handled_press = handler.handle_mouse_press(mock_widget, press_event)
        self.assertTrue(handled_press)
        self.assertFalse(handler.is_dragging)

        # 2. Move past threshold on Wayland
        move_event = MagicMock(spec=QMouseEvent)
        move_event.buttons.return_value = Qt.MouseButton.LeftButton
        move_event.globalPosition.return_value = QPointF(150 + DRAG_THRESHOLD_PX + 2, 120)

        with patch("ui.drag_handler.is_wayland", return_value=True):
            handled_move = handler.handle_mouse_move(mock_widget, move_event)
            self.assertTrue(handled_move)
            self.assertTrue(handler.is_dragging)
            mock_window_handle.startSystemMove.assert_called_once()
            mock_widget.move.assert_not_called()

    def test_xcb_x11_applies_move_math(self):
        """On X11 (xcb), exceeding threshold applies widget.move(new_pos)."""
        handler = CrossPlatformDragHandler(threshold_px=DRAG_THRESHOLD_PX)
        mock_widget = MagicMock(spec=QWidget)
        mock_widget.pos.return_value = QPoint(100, 100)
        mock_widget.frameGeometry.return_value.topLeft.return_value = QPoint(100, 100)

        press_event = MagicMock(spec=QMouseEvent)
        press_event.button.return_value = Qt.MouseButton.LeftButton
        press_event.position.return_value = QPointF(50, 20)
        press_event.globalPosition.return_value = QPointF(150, 120)

        # 1. Press
        handler.handle_mouse_press(mock_widget, press_event)

        # 2. Move past threshold on X11
        delta_x, delta_y = 30, 20
        move_event = MagicMock(spec=QMouseEvent)
        move_event.buttons.return_value = Qt.MouseButton.LeftButton
        move_event.globalPosition.return_value = QPointF(150 + delta_x, 120 + delta_y)

        with patch("ui.drag_handler.is_wayland", return_value=False):
            handled_move = handler.handle_mouse_move(mock_widget, move_event)
            self.assertTrue(handled_move)
            self.assertTrue(handler.is_dragging)
            # Should move by offset
            mock_widget.move.assert_called_once_with(QPoint(100 + delta_x, 100 + delta_y))

    def test_drag_threshold_prevents_accidental_click_drag(self):
        """Move smaller than DRAG_THRESHOLD_PX does not initiate drag."""
        handler = CrossPlatformDragHandler(threshold_px=DRAG_THRESHOLD_PX)
        mock_widget = MagicMock(spec=QWidget)
        mock_widget.pos.return_value = QPoint(100, 100)
        mock_widget.frameGeometry.return_value.topLeft.return_value = QPoint(100, 100)

        press_event = MagicMock(spec=QMouseEvent)
        press_event.button.return_value = Qt.MouseButton.LeftButton
        press_event.position.return_value = QPointF(50, 20)
        press_event.globalPosition.return_value = QPointF(150, 120)
        handler.handle_mouse_press(mock_widget, press_event)

        # Small 2px jitter
        move_event = MagicMock(spec=QMouseEvent)
        move_event.buttons.return_value = Qt.MouseButton.LeftButton
        move_event.globalPosition.return_value = QPointF(152, 120)

        with patch("ui.drag_handler.is_wayland", return_value=False):
            handled_move = handler.handle_mouse_move(mock_widget, move_event)
            self.assertFalse(handled_move)
            self.assertFalse(handler.is_dragging)
            mock_widget.move.assert_not_called()

        # Release should report was_dragging = False (normal click)
        release_event = MagicMock(spec=QMouseEvent)
        was_dragging = handler.handle_mouse_release(mock_widget, release_event)
        self.assertFalse(was_dragging)


class TestWidgetWindowProperties(unittest.TestCase):
    """Test window flags and attributes on MinimizedHudOverlay and BatGlobeOrb."""

    def test_minimized_hud_overlay_flags_and_properties(self):
        from ui import MinimizedHudOverlay
        mock_main = MagicMock()
        mock_sig = MagicMock()

        overlay = MinimizedHudOverlay(mock_main, mock_sig, "ALFRED")
        flags = overlay.windowFlags()

        # Must have Frameless and StaysOnTop
        self.assertTrue(bool(flags & Qt.WindowType.FramelessWindowHint))
        self.assertTrue(bool(flags & Qt.WindowType.WindowStaysOnTopHint))
        # Must NOT be Tool window type (Linux compositors demote or hide Tool windows)
        self.assertFalse((flags & Qt.WindowType.WindowType_Mask) == Qt.WindowType.Tool)
        # Fixed size 420x230
        self.assertEqual(overlay.width(), 420)
        self.assertEqual(overlay.height(), 230)
        overlay.close()

    def test_bat_globe_orb_flags_and_properties(self):
        from ui import BatGlobeOrb
        mock_main = MagicMock()

        orb = BatGlobeOrb(mock_main, "ALFRED")
        flags = orb.windowFlags()

        # Must have Frameless and StaysOnTop
        self.assertTrue(bool(flags & Qt.WindowType.FramelessWindowHint))
        self.assertTrue(bool(flags & Qt.WindowType.WindowStaysOnTopHint))
        # Must NOT be Tool window type
        self.assertFalse((flags & Qt.WindowType.WindowType_Mask) == Qt.WindowType.Tool)
        # Fixed size 260x260
        self.assertEqual(orb.width(), 260)
        self.assertEqual(orb.height(), 260)
        orb.close()


if __name__ == "__main__":
    unittest.main()
