"""Focused behavior checks for the minimized transcript overlay."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMainWindow

import ui
from ui import MinimizedHudOverlay


class _LogSource(QObject):
    emitted = pyqtSignal(str)


class TestMinimizedHudOverlay(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
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

    def test_only_assistant_lines_are_kept(self):
        for line in ("SYS: ready", "You: hello", "ERR: no", "Alfred: At your service"):
            self.source.emitted.emit(line)
        self.assertEqual(list(self.overlay._lines), ["Alfred: At your service"])

    def test_transcript_is_bounded_to_ten_replies(self):
        for index in range(12):
            self.source.emitted.emit(f"Alfred: reply {index}")
        self.assertEqual(len(self.overlay._lines), 10)
        self.assertEqual(self.overlay._lines[0], "Alfred: reply 2")
        self.assertIn("reply 11", self.overlay._transcript.toPlainText())

    def test_name_update_changes_filter_and_title(self):
        self.overlay.set_assistant_name("Pennyworth")
        self.source.emitted.emit("Pennyworth: Ready")
        self.assertEqual(list(self.overlay._lines), ["Pennyworth: Ready"])
        self.assertIn("PENNYWORTH", self.overlay._title.text())

    def test_close_hides_only_for_current_minimize_session(self):
        self.overlay.begin_minimize_session()
        self.overlay.close()
        self.assertFalse(self.overlay.isVisible())
        self.assertTrue(self.overlay._user_closed)

        self.overlay.begin_minimize_session()
        self.assertTrue(self.overlay.isVisible())
        self.assertFalse(self.overlay._user_closed)

    def test_position_is_persisted(self):
        self.overlay.move(31, 47)
        self.overlay.hide_overlay()
        saved = self.overlay._position_path.read_text(encoding="utf-8")
        self.assertIn('"x": 31', saved)
        self.assertIn('"y": 47', saved)

    def test_transcript_uses_readable_accessible_text(self):
        font = self.overlay._transcript.font()
        self.assertGreaterEqual(font.pointSize(), 10)
        self.assertGreaterEqual(font.weight(), font.Weight.Medium)
        self.assertEqual(self.overlay._transcript.accessibleName(), "Recent Alfred replies")


if __name__ == "__main__":
    unittest.main()
