"""
tests/hud_video/test_controls.py — Unit tests for Visual HUD controls strip, timeline, and buttons.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QKeyEvent, QMouseEvent
from PyQt6.QtWidgets import QApplication

_app = QApplication.instance()
if _app is None:
    _app = QApplication(["test", "-platform", "offscreen"])

from core.hud_video.controller import HudVideoController
from core.hud_video.controls import HudVideoControlsStrip, VideoTimeline, CyberTransportButton
from core.hud_video.resolve import PlayableRef
from core.hud_video.transport import VideoStatus, VideoState, SKIP_S


class FakeBackend:
    def __init__(self):
        self.playing = False
        self.paused = False
        self.seek_history: list[float] = []

    def play(self):
        self.playing = True
        self.paused = False

    def pause(self):
        self.playing = False
        self.paused = True

    def seek(self, pos: float):
        self.seek_history.append(pos)


class TestControlsUI(unittest.TestCase):

    def setUp(self):
        self.backend = FakeBackend()
        self.controller = HudVideoController()
        self.controller.wire(
            on_show_surface=lambda: None,
            on_hide_surface=lambda: None,
            on_backend_play=lambda ref, muted: self.backend.play(),
            on_backend_pause=self.backend.pause,
            on_backend_resume=self.backend.play,
            on_backend_stop=lambda: None,
            on_backend_set_muted=lambda m: None,
            on_backend_set_volume=lambda v: None,
            on_backend_seek=self.backend.seek,
        )

        self.strip = HudVideoControlsStrip(self.controller)
        self.strip.resize(400, 36)
        self.strip.show()

        self.ref = PlayableRef(
            kind="direct_url",
            uri="https://stream.cdn/video.mp4",
            title="Trailer",
        )
        self.controller.play(self.ref)
        self.controller.on_backend_duration(100.0)
        self.controller.on_backend_ready()

    def test_play_pause_toggle_button(self):
        """Button toggles play/pause."""
        self.assertEqual(self.controller.state().status, VideoStatus.PLAYING)
        self.assertEqual(self.strip._play_btn._mode, "pause")

        # Click button to pause
        self.strip._play_btn.click()
        self.assertEqual(self.controller.state().status, VideoStatus.PAUSED)
        self.assertEqual(self.strip._play_btn._mode, "play")

        # Click again to resume
        self.strip._play_btn.click()
        self.assertEqual(self.controller.state().status, VideoStatus.PLAYING)
        self.assertEqual(self.strip._play_btn._mode, "pause")

    def test_replay_button_highlight_on_ended(self):
        """Replay button is always visible and highlights on ENDED."""
        self.assertTrue(self.strip._replay_btn.isVisible())
        self.assertFalse(self.strip._replay_btn._highlighted)

        # Trigger ended
        self.controller.on_backend_ended()
        self.assertEqual(self.controller.state().status, VideoStatus.ENDED)
        self.assertTrue(self.strip._replay_btn._highlighted)

        # Click replay restarts from start
        self.strip._replay_btn.click()
        self.assertEqual(self.controller.state().status, VideoStatus.PLAYING)
        self.assertEqual(self.controller.state().position_s, 0.0)
        self.assertFalse(self.strip._replay_btn._highlighted)

    def test_timeline_scrub_commits_on_release_only(self):
        """Timeline drag scrubs with live time label and commits on release only."""
        timeline = self.strip._timeline
        timeline.resize(200, 16)

        # 1. Mouse press (at halfway x=100)
        press_ev = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(100.0, 8.0),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        timeline.mousePressEvent(press_ev)
        self.assertTrue(timeline._scrubbing)
        # Seeking has NOT committed to player yet
        self.assertEqual(len(self.backend.seek_history), 0)

        # 2. Mouse move (drag to x=150)
        move_ev = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(150.0, 8.0),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        timeline.mouseMoveEvent(move_ev)
        self.assertTrue(timeline._scrubbing)
        # Still not committed during move
        self.assertEqual(len(self.backend.seek_history), 0)

        # 3. Mouse release: commits seek
        release_ev = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            QPointF(150.0, 8.0),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        timeline.mouseReleaseEvent(release_ev)
        self.assertFalse(timeline._scrubbing)
        # Now committed!
        self.assertEqual(len(self.backend.seek_history), 1)
        self.assertGreater(self.backend.seek_history[0], 60.0)

    def test_live_stream_disables_bar_and_shows_live(self):
        """Live or unknown duration shows LIVE and disables bar."""
        self.controller.on_backend_duration(0.0)
        self.controller.on_backend_ready()

        self.assertIn("LIVE", self.strip._time_lbl.text())
        self.assertTrue(self.strip._timeline._is_live)

    def test_keyboard_shortcuts(self):
        """Space toggles, Left/Right skip 10s, Home goes to start."""
        timeline = self.strip._timeline

        # Space key toggles play -> pause
        space_ev = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Space,
            Qt.KeyboardModifier.NoModifier,
        )
        timeline.keyPressEvent(space_ev)
        self.assertEqual(self.controller.state().status, VideoStatus.PAUSED)

        # Right key skips +10s
        right_ev = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Right,
            Qt.KeyboardModifier.NoModifier,
        )
        timeline.keyPressEvent(right_ev)
        self.assertIn(10.0, self.backend.seek_history)

        # Home key seeks to 0.0
        home_ev = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Home,
            Qt.KeyboardModifier.NoModifier,
        )
        timeline.keyPressEvent(home_ev)
        self.assertIn(0.0, self.backend.seek_history)


if __name__ == "__main__":
    unittest.main()
