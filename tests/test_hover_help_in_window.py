"""
tests/test_hover_help_in_window.py — Unit tests verifying that hover help popups
stay strictly inside the application window and never escape to the desktop / homescreen.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, QPoint, QRect, Qt
from PyQt6.QtWidgets import QApplication, QPushButton, QWidget

_app = QApplication.instance()
if _app is None:
    _app = QApplication(["test", "-platform", "offscreen"])
_app.setQuitOnLastWindowClosed(False)

from ui import (
    TacticalHoverHelpManager,
    TacticalInWindowTooltip,
    attach_hover_help,
)


class TestHoverHelpInWindow(unittest.TestCase):

    def setUp(self):
        self.window = QWidget()
        self.window.resize(800, 600)
        self.window.show()
        self.btn = QPushButton("Test Button", self.window)
        self.btn.setGeometry(20, 20, 150, 30)
        self.manager = TacticalHoverHelpManager.instance()

    def tearDown(self):
        self.manager.dismiss()
        self.manager._help_map.clear()
        self.window.close()

    def test_native_set_tooltip_is_suppressed(self):
        """Verify attach_hover_help clears native Qt tooltip to prevent OS desktop popups."""
        help_text = "Toggle the tactical controls panel for quick access to system settings and tools."
        attach_hover_help(self.btn, help_text)

        # Native setToolTip must be empty so Qt's C++ core never spawns an OS desktop tooltip window
        self.assertEqual(self.btn.toolTip(), "")
        # Accessible description retains the help text for screen readers
        self.assertEqual(self.btn.accessibleDescription(), help_text)

    def test_tooltip_is_strictly_child_of_window(self):
        """Verify TacticalInWindowTooltip is a child of the top-level window, not a top-level desktop window."""
        help_text = "In-window tactical help."
        self.manager._show_for_widget(self.btn, help_text)

        tooltip = self.manager._active_tooltip
        self.assertIsNotNone(tooltip)
        self.assertEqual(tooltip.parent(), self.window)
        self.assertFalse(tooltip.isWindow())
        self.assertTrue(tooltip.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents))

    def test_tooltip_coordinates_clamped_within_window(self):
        """Verify tooltip geometry stays completely within the window boundaries even for edge widgets."""
        edge_btn = QPushButton("Right Edge", self.window)
        edge_btn.setGeometry(750, 10, 40, 30)  # Near right edge
        help_text = "A very long descriptive help text that would overflow the right edge of the screen."

        self.manager._show_for_widget(edge_btn, help_text)
        tooltip = self.manager._active_tooltip
        self.assertIsNotNone(tooltip)

        geom = tooltip.geometry()
        # Must not overflow right boundary
        self.assertLessEqual(geom.right(), self.window.width() - 8)
        # Must not overflow left boundary
        self.assertGreaterEqual(geom.left(), 8)
        # Must be below or above target, inside window top and bottom
        self.assertGreaterEqual(geom.top(), 8)
        self.assertLessEqual(geom.bottom(), self.window.height() - 8)

    def test_bottom_edge_widget_flips_above(self):
        """Verify widgets near bottom edge place tooltip above target rather than overflowing."""
        bottom_btn = QPushButton("Bottom Edge", self.window)
        bottom_btn.setGeometry(100, 580, 150, 20)  # Near bottom edge

        self.manager._show_for_widget(bottom_btn, "Bottom help text.")
        tooltip = self.manager._active_tooltip
        self.assertIsNotNone(tooltip)

        geom = tooltip.geometry()
        # Should be placed above the button
        self.assertLess(geom.bottom(), bottom_btn.geometry().top())
        self.assertGreaterEqual(geom.top(), 8)

    def test_tooltip_event_suppressed_globally(self):
        """Verify QEvent.Type.ToolTip is intercepted and consumed (returns True) so Qt desktop popup never shows."""
        event = QEvent(QEvent.Type.ToolTip)
        consumed = self.manager.eventFilter(self.btn, event)
        self.assertTrue(consumed, "QEvent.Type.ToolTip must be consumed to block native desktop QToolTip")

    def test_dismiss_on_mouse_leave_or_click(self):
        """Verify tooltip dismisses immediately on mouse leave or mouse click."""
        self.manager._show_for_widget(self.btn, "Help text")
        tooltip = self.manager._active_tooltip
        self.assertTrue(tooltip.isVisible())

        # Simulate mouse leave
        leave_event = QEvent(QEvent.Type.Leave)
        self.manager.eventFilter(self.btn, leave_event)
        self.assertFalse(tooltip.isVisible())

        # Re-show and simulate mouse press
        self.manager._show_for_widget(self.btn, "Help text")
        self.assertTrue(tooltip.isVisible())
        click_event = QEvent(QEvent.Type.MouseButtonPress)
        self.manager.eventFilter(self.btn, click_event)
        self.assertFalse(tooltip.isVisible())


if __name__ == "__main__":
    unittest.main()
