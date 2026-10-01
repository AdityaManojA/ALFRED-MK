"""
tests/test_idle_sleep_optimizations.py — Unit tests for idle/sleep CPU and memory optimizations.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication

_APP = QApplication.instance() or QApplication([])

from ui import HudCanvas, SlotHostWidget


class TestIdleSleepOptimizations(unittest.TestCase):

    def test_openmp_environment_defaults(self):
        """Verify OpenMP passive waiting and zero blocktime are configured."""
        self.assertEqual(os.environ.get("KMP_BLOCKTIME"), "0")
        self.assertEqual(os.environ.get("OMP_WAIT_POLICY"), "PASSIVE")
        self.assertIn(os.environ.get("OMP_NUM_THREADS"), ("1", "2"))

    def test_hud_canvas_sleep_throttle(self):
        """Verify that when state is SLEEPING, HudCanvas throttles repaints to ~4 FPS (every 15 ticks)."""
        canvas = HudCanvas(face_path="", assistant_name="Test")
        try:
            canvas.state = "SLEEPING"
            canvas.speaking = False
            canvas._amp_disp = 0.0

            # Mock on_screen to True
            with patch.object(canvas, "_on_screen", return_value=True), \
                 patch.object(canvas, "update") as mock_update:

                # Advance 60 ticks (1 second at 60 Hz)
                for _ in range(60):
                    canvas._step()

                # In SLEEPING state, repaints should happen at ~4 FPS (about 4 times in 60 ticks, not 20)
                self.assertLessEqual(mock_update.call_count, 6)
                self.assertGreaterEqual(mock_update.call_count, 3)
        finally:
            canvas._tmr.stop()

    def test_hud_canvas_off_screen_skips_processing(self):
        """Verify that when canvas window is minimized, _step does not update."""
        canvas = HudCanvas(face_path="", assistant_name="Test")
        try:
            canvas.state = "LISTENING"
            with patch.object(canvas, "_is_minimized", return_value=True), \
                 patch.object(canvas, "update") as mock_update:
                for _ in range(60):
                    canvas._step()
                mock_update.assert_not_called()
        finally:
            canvas._tmr.stop()

    def test_slot_host_widget_sleep_throttle(self):
        """Verify SlotHostWidget throttles tick rate when window state is SLEEPING."""
        slot = SlotHostWidget(slot_index=0, height=120)
        try:
            mock_win = MagicMock()
            mock_win.isMinimized.return_value = False
            mock_win.isHidden.return_value = False
            mock_win.hud.state = "SLEEPING"

            with patch.object(slot, "isVisible", return_value=True), \
                 patch.object(slot, "window", return_value=mock_win), \
                 patch.object(slot, "update") as mock_update:

                for _ in range(12):
                    slot._step()

                # In sleep mode, updates should be throttled to every 6th tick (~2 updates for 12 ticks)
                self.assertLessEqual(mock_update.call_count, 3)
        finally:
            slot._tmr.stop()


    def test_trim_process_memory_success(self):
        """Verify trim_process_memory runs cleanly without raising errors."""
        from core.memory_trimmer import trim_process_memory
        result = trim_process_memory()
        self.assertIsInstance(result, bool)


if __name__ == "__main__":
    unittest.main()

