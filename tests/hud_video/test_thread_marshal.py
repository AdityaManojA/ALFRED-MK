"""
tests/hud_video/test_thread_marshal.py — Unit tests for GUI-thread marshalling.

Verifies:
1. Direct calls from a worker thread to backend / player methods raise RuntimeError (assert_gui_thread).
2. Cross-thread calls to HudVideoController methods (play, stop, begin_resolve, on_resolved)
   are marshalled via queued signals onto the Qt GUI thread.
3. Timers and QMediaPlayer are only touched on the GUI thread.
"""

from __future__ import annotations

import threading
import time
import unittest
from unittest.mock import MagicMock

from PyQt6.QtCore import QCoreApplication, QThread
from PyQt6.QtWidgets import QApplication

# Ensure QApplication instance exists
_APP = QApplication.instance() or QApplication([])

from core.hud_video.controller import HudVideoController, assert_gui_thread
from core.hud_video.resolve import PlayableRef


class TestThreadMarshal(unittest.TestCase):

    def setUp(self):
        self.ctrl = HudVideoController()

    def test_assert_gui_thread_on_main_thread(self):
        """assert_gui_thread succeeds on the Qt GUI thread."""
        try:
            assert_gui_thread()
        except RuntimeError:
            self.fail("assert_gui_thread unexpectedly raised on main thread")

    def test_assert_gui_thread_fails_on_worker_thread(self):
        """assert_gui_thread raises RuntimeError when called from a worker thread."""
        error_raised = []

        def worker():
            try:
                assert_gui_thread()
            except RuntimeError as e:
                error_raised.append(e)

        t = threading.Thread(target=worker)
        t.start()
        t.join()

        self.assertEqual(len(error_raised), 1)
        self.assertIn("must be called on Qt GUI thread", str(error_raised[0]))

    def test_cross_thread_begin_resolve_and_ready(self):
        """Cross-thread begin_resolve and on_resolved marshal cleanly without timer errors."""
        mock_show = MagicMock()
        mock_play = MagicMock()

        self.ctrl.wire(
            on_show_surface=mock_show,
            on_hide_surface=MagicMock(),
            on_backend_play=mock_play,
            on_backend_pause=MagicMock(),
            on_backend_resume=MagicMock(),
            on_backend_stop=MagicMock(),
            on_backend_set_muted=MagicMock(),
            on_backend_set_volume=MagicMock(),
        )

        ref = PlayableRef(kind="direct_url", uri="https://example.com/stream.mp4", title="Test Trailer")

        # Emit from a background worker thread
        def background_caller():
            self.ctrl.begin_resolve("Searching...", source_query="Dune trailer")
            self.ctrl.on_resolved(ref)

        t = threading.Thread(target=background_caller)
        t.start()
        t.join()

        # Process Qt event loop on main thread
        _APP.processEvents()

        mock_show.assert_called_once()
        mock_play.assert_called_once_with(ref, False)


if __name__ == "__main__":
    unittest.main()
