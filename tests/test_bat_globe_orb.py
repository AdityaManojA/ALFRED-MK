"""Unit tests for the minimal interactive BatGlobeOrb floating widget."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import QApplication, QMainWindow

import ui
from ui import BatGlobeOrb, HudCanvas, MainWindow


class TestBatGlobeOrb(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_patch = patch.object(ui, "CONFIG_DIR", Path(self.temp_dir.name))
        self.config_patch.start()
        self.main = QMainWindow()
        self.main._face_path = "face.png"
        self.main.on_interrupt = MagicMock()
        self.main.on_wake_manual = MagicMock()
        self.orb = BatGlobeOrb(self.main, "Alfred")

    def tearDown(self) -> None:
        self.orb.close()
        self.main.close()
        self.config_patch.stop()
        self.temp_dir.cleanup()

    def test_orb_window_properties(self):
        self.assertTrue(self.orb.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))
        self.assertEqual(self.orb.width(), 240)
        self.assertEqual(self.orb.height(), 240)
        self.assertTrue(bool(self.orb.windowFlags() & Qt.WindowType.FramelessWindowHint))
        self.assertTrue(bool(self.orb.windowFlags() & Qt.WindowType.WindowStaysOnTopHint))

    def test_canvas_is_orb_mode(self):
        self.assertTrue(getattr(self.orb.canvas, "is_orb_mode", False))

    def test_state_sync_to_orb_canvas(self):
        self.orb.canvas.state = "LISTENING"
        self.assertEqual(self.orb.canvas.state, "LISTENING")
        self.orb.canvas.state = "SPEAKING"
        self.orb.canvas.speaking = True
        self.assertEqual(self.orb.canvas.state, "SPEAKING")
        self.assertTrue(self.orb.canvas.speaking)

    def test_orb_click_interrupts_when_speaking(self):
        self.orb.canvas.speaking = True
        self.orb._on_orb_clicked()
        self.main.on_interrupt.assert_called_once()
        self.main.on_wake_manual.assert_not_called()

    def test_orb_click_wakes_when_idle(self):
        self.orb.canvas.speaking = False
        self.orb._on_orb_clicked()
        self.main.on_wake_manual.assert_called_once()
        self.main.on_interrupt.assert_not_called()

    def test_restore_full_hud(self):
        self.orb.show()
        self.orb.restore_full_hud()
        self.assertTrue(self.orb.isHidden())


if __name__ == "__main__":
    unittest.main()
