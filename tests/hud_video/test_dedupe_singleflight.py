"""
tests/hud_video/test_dedupe_singleflight.py — Unit tests for single-flight deduplication and debounce.
"""

from __future__ import annotations

import time
import unittest
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication

# Ensure QApplication instance exists
_APP = QApplication.instance() or QApplication([])

from actions.hud_video import (
    _single_flight,
    hud_video,
    RESOLVE_DEBOUNCE_MS,
    SAME_TARGET_TTL_S,
)
from core.hud_video.controller import HudVideoController
from core.hud_video.resolve import PlayableRef
from core.registry import register


class TestDedupeSingleFlight(unittest.TestCase):

    def setUp(self):
        _single_flight.reset()
        self.ctrl = HudVideoController()
        register("hud_video_controller", self.ctrl)

    def tearDown(self):
        _single_flight.reset()

    def test_20_duplicate_plays_starts_one_resolve(self):
        """Firing the same play 20 times in 100ms triggers exactly 1 resolve and returns terminal outputs."""
        mock_speak = MagicMock()
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

        with patch("actions.hud_video.threading.Thread") as mock_thread:
            fake_t = MagicMock()
            mock_thread.return_value = fake_t

            results = []
            for _ in range(20):
                res = hud_video(
                    {"action": "play", "target": "the new Dune trailer in the app"},
                    speak=mock_speak,
                )
                results.append(res)

            # Exactly 1 thread was started
            self.assertEqual(mock_thread.call_count, 1)

            # First result indicates playing; subsequent 19 indicate already preparing
            self.assertIn("Playing new Dune trailer", results[0])
            for r in results[1:]:
                self.assertIn("already preparing", r)

            # Assert all 20 returns are terminal and none contain "Resolving:"
            for r in results:
                self.assertNotIn("Resolving:", r)

            # Assert no early speech was triggered
            mock_speak.assert_not_called()

    def test_different_target_cancels_previous_resolve(self):
        """A new different target cancels the in-flight generation token."""
        with patch("actions.hud_video.threading.Thread") as mock_thread:
            fake_t = MagicMock()
            mock_thread.return_value = fake_t

            res1 = hud_video({"action": "play", "target": "Dune trailer in the app"})
            token1 = _single_flight._active_token

            res2 = hud_video({"action": "play", "target": "Interstellar trailer on screen"})
            token2 = _single_flight._active_token

            self.assertNotEqual(token1, token2)
            self.assertFalse(_single_flight.is_current_token(token1))
            self.assertTrue(_single_flight.is_current_token(token2))
            self.assertEqual(mock_thread.call_count, 2)


if __name__ == "__main__":
    unittest.main()
