"""
tests/hud_video/test_playback_hygiene.py — Tests for terminal tool output, privacy logging, and source switching.
"""

from __future__ import annotations

import logging
import unittest
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QApplication

from actions.hud_video import (
    SAME_TARGET_TTL_S,
    _single_flight,
    hud_video,
)
from core.hud_video.backends.local_url import LocalUrlBackend
from core.hud_video.resolve import PlayableRef

# Ensure single QApplication exists for Qt tests
_app = QApplication.instance() or QApplication([])


class TestPlaybackHygieneAndPrivacy(unittest.TestCase):

    def setUp(self):
        _single_flight.reset()

    def test_tool_output_is_terminal_and_no_resolving_string(self):
        """Verify tool outputs for initial play, in-flight duplicate, and different target are terminal."""
        mock_ctrl = MagicMock()

        with patch("actions.hud_video._get_controller", return_value=mock_ctrl), \
             patch("actions.hud_video._resolve_and_play") as mock_worker:
            # 1. First invocation
            out1 = hud_video({"action": "play", "target": "dune trailer", "locus_confirmed": True})
            self.assertIn("Playing dune trailer on the Visual HUD.", out1)
            self.assertNotIn("Resolving", out1)

            # 2. Duplicate invocation while first is in flight
            out2 = hud_video({"action": "play", "target": "dune trailer", "locus_confirmed": True})
            self.assertEqual(out2, "Visual HUD is already preparing dune trailer.")
            self.assertNotIn("Resolving", out2)

            # 3. Different target invocation replaces in-flight
            out3 = hud_video({"action": "play", "target": "blade runner 2049", "locus_confirmed": True})
            self.assertIn("Playing blade runner 2049 on the Visual HUD.", out3)
            self.assertNotIn("Resolving", out3)

    def test_privacy_googlevideo_query_token_not_logged(self):
        """Verify stream resolution logs host only and strips sensitive signed tokens."""
        from core.hud_video.backends import youtube

        fake_signed_stream_url = (
            "https://rr1---sn-4g5ednss.googlevideo.com/videoplayback?"
            "expire=1710000000&ei=SECRET_EI_TOKEN&ip=127.0.0.1&id=o-SECRET_TOKEN"
            "&itag=248&aitags=133%2C134&source=youtube&requiressl=yes&signature=SECRET_SIG"
        )

        with patch.object(youtube, "_ytdlp_available", return_value=True), \
             patch("subprocess.run") as mock_subproc:
            mock_subproc.return_value = MagicMock(
                returncode=0,
                stdout=f"{fake_signed_stream_url}\n",
                stderr="",
            )

            with self.assertLogs("core.hud_video.backends.youtube", level="INFO") as captured:
                stream_url, audio_url = youtube.extract_stream_url("https://www.youtube.com/watch?v=mock123")

                self.assertEqual(stream_url, fake_signed_stream_url)
                self.assertIsNone(audio_url)

                log_output = "\n".join(captured.output)
                # Host must be logged
                self.assertIn("rr1---sn-4g5ednss.googlevideo.com", log_output)
                # Query parameters and sensitive tokens must NEVER appear in logs
                self.assertNotIn("SECRET_EI_TOKEN", log_output)
                self.assertNotIn("SECRET_TOKEN", log_output)
                self.assertNotIn("SECRET_SIG", log_output)
                self.assertNotIn("videoplayback?", log_output)

    def test_switching_sources_twice_runs_cleanly(self):
        """Verify sequential source loading stops previous stream with _wait_stopped without errors."""
        from PyQt6.QtMultimediaWidgets import QVideoWidget
        widget = QVideoWidget()
        backend = LocalUrlBackend(widget)

        ref1 = PlayableRef(
            kind="direct_url",
            uri="http://127.0.0.1:8000/sample1.mp4",
            title="Sample 1",
        )
        ref2 = PlayableRef(
            kind="direct_url",
            uri="http://127.0.0.1:8000/sample2.mp4",
            title="Sample 2",
        )
        ref3 = PlayableRef(
            kind="direct_url",
            uri="http://127.0.0.1:8000/sample3.mp4",
            title="Sample 3",
        )

        # Load first source
        backend.load(ref1)
        QCoreApplication.processEvents()

        # Switch to second source
        backend.load(ref2)
        QCoreApplication.processEvents()

        # Switch to third source
        backend.load(ref3)
        QCoreApplication.processEvents()

        # Stop cleanly
        backend.stop()
        QCoreApplication.processEvents()


if __name__ == "__main__":
    unittest.main()
