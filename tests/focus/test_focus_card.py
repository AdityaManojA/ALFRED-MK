import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtWidgets import QApplication

from core.sentry.focus.card import FloatingFocusCard
from core.sentry.focus.state import FocusState
from ui import MinimizedHudOverlay, C


class TestFocusCard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.card = FloatingFocusCard()

    def tearDown(self):
        self.card.close()

    def test_card_does_not_spawn_when_inactive(self):
        """Card must remain hidden when FocusState is inactive."""
        state = FocusState(active=False)
        self.card.update_state(state)
        self.assertFalse(self.card.isVisible())

    def test_card_shows_and_formats_countdown_when_active(self):
        """Card shows when active and calculates mm:ss countdown and progress."""
        state = FocusState(
            active=True,
            planned_s=1500,
            remaining_s=1471, # 24 min 31 sec
            paused=False,
            drifting=False,
        )
        self.card.update_state(state)
        self.assertTrue(self.card.isVisible())
        self.assertEqual(self.card._countdown_text, "24:31")
        self.assertAlmostEqual(self.card._progress, 1471 / 1500, places=3)
        self.assertFalse(self.card._drifting)

    def test_card_drift_warning_state(self):
        """Card reflects drifting state with red styling and label."""
        state = FocusState(
            active=True,
            planned_s=1500,
            remaining_s=1200,
            drifting=True,
        )
        self.card.update_state(state)
        self.assertTrue(self.card.isVisible())
        self.assertTrue(self.card._drifting)

    def test_clamp_to_screen_boundaries(self):
        """Card repositioning respects desktop screen boundaries."""
        screen = QApplication.primaryScreen()
        if not screen:
            self.skipTest("No primary screen in offscreen environment")

        geom = screen.availableGeometry()

        # Try positioning way outside screen on the right/bottom
        extreme_point = QPoint(geom.right() + 500, geom.bottom() + 500)
        clamped = self.card.clamp_to_screen(extreme_point)
        self.assertLessEqual(clamped.x() + self.card.width(), geom.right() + 1)
        self.assertLessEqual(clamped.y() + self.card.height(), geom.bottom() + 1)

        # Try positioning negative coordinates on top/left
        negative_point = QPoint(geom.left() - 500, geom.top() - 500)
        clamped_neg = self.card.clamp_to_screen(negative_point)
        self.assertGreaterEqual(clamped_neg.x(), geom.left())
        self.assertGreaterEqual(clamped_neg.y(), geom.top())


class TestMinimizedHudOverlayIndicators(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_indicator_pill_states(self):
        """Verify MinimizedHudOverlay displays MON and FOC pills with accurate styling."""
        mock_log_sig = MagicMock()
        overlay = MinimizedHudOverlay(None, mock_log_sig, "Alfred")

        # 1. Idle state
        overlay.update_sentry_indicator(mon_active=False, foc_active=False)
        self.assertEqual(overlay._sentry_btn.text(), "S")

        # 2. Monitor running normal (green dot)
        overlay.update_sentry_indicator(mon_active=True, foc_active=False, waiting_for_answer=False)
        self.assertIn("MON", overlay._sentry_btn.text())
        self.assertIn("#00ff88", overlay._sentry_btn.styleSheet())

        # 3. Monitor waiting for answer (yellow dot)
        overlay.update_sentry_indicator(mon_active=True, foc_active=False, waiting_for_answer=True)
        self.assertIn("MON", overlay._sentry_btn.text())
        self.assertIn("#ffcc00", overlay._sentry_btn.styleSheet())

        # 4. Focus active (cyan FOC countdown)
        overlay.update_sentry_indicator(
            mon_active=False,
            foc_active=True,
            foc_remaining_s=1471, # 24:31
            drifting=False,
        )
        self.assertEqual(overlay._sentry_btn.text(), "FOC 24:31")
        self.assertIn(C.CYAN, overlay._sentry_btn.styleSheet())

        # 5. Focus drifting (red drift pulse)
        overlay.update_sentry_indicator(
            mon_active=False,
            foc_active=True,
            foc_remaining_s=1471,
            drifting=True,
        )
        self.assertEqual(overlay._sentry_btn.text(), "FOC 24:31")
        self.assertIn(C.RED, overlay._sentry_btn.styleSheet())

        overlay.shutdown()


if __name__ == "__main__":
    unittest.main()
