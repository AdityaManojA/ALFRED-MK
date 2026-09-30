"""
tests/test_hud_frame_latency.py — Unit tests for HUD frame budget and paint timing constants.
"""

from __future__ import annotations

import unittest
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import QApplication

_APP = QApplication.instance() or QApplication([])

from ui import (
    FRAME_TIME_BUDGET_MS,
    PAINT_WARN_THRESHOLD_MS,
    HudCanvas,
)


class TestHudFrameLatency(unittest.TestCase):

    def test_constants_defined(self):
        self.assertEqual(FRAME_TIME_BUDGET_MS, 16.7)
        self.assertEqual(PAINT_WARN_THRESHOLD_MS, 20.0)

    def test_hud_canvas_step_timer_interval(self):
        canvas = HudCanvas(face_path="", assistant_name="Test")
        self.assertEqual(canvas._tmr.interval(), int(FRAME_TIME_BUDGET_MS))
        canvas._tmr.stop()

    def test_hud_paint_event_alloc_cache(self):
        canvas = HudCanvas(face_path="", assistant_name="Test")
        canvas.resize(400, 400)
        img = QImage(400, 400, QImage.Format.Format_ARGB32_Premultiplied)
        p = QPainter(img)
        try:
            # Trigger paintEvent logic
            canvas.paintEvent(None)
        finally:
            p.end()
            canvas._tmr.stop()

        # Check blend cache initialized
        self.assertIsInstance(canvas._blend_cache, dict)


if __name__ == "__main__":
    unittest.main()
