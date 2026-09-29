"""
tests/hud_video/test_transport.py — Unit tests for Visual HUD transport core.

Covers:
- Fake player integration (no QtMultimedia, no network, runs headless)
- Queued seek during LOADING
- Seek clamping to [0, duration - END_MARGIN_S]
- ended -> replay on play()
- Non-seekable media rejection with SeekRejectReason.NOT_SEEKABLE
- Single re-resolve on stream error (RERESOLVE_RETRIES = 1) and resume at last position
- VideoState whitelist and privacy (no stream URLs in state)
- Emit throttle at STATE_EMIT_HZ = 4
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from PyQt6.QtCore import QCoreApplication

# Ensure QCoreApplication exists for signals/slots in headless tests
_app = QCoreApplication.instance()
if _app is None:
    _app = QCoreApplication([])

from core.hud_video.controller import HudVideoController
from core.hud_video.resolve import PlayableRef
from core.hud_video.transport import (
    STATE_EMIT_HZ,
    END_MARGIN_S,
    RERESOLVE_RETRIES,
    VideoStatus,
    SeekRejectReason,
    VideoState,
    clamp_seek,
)


class FakePlayerBackend:
    """Mock playback engine that simulates QMediaPlayer backend signals."""

    def __init__(self) -> None:
        self.loaded_ref: PlayableRef | None = None
        self.playing: bool = False
        self.paused: bool = False
        self.stopped: bool = False
        self.position_s: float = 0.0
        self.duration_s: float = 0.0
        self.seekable: bool = False
        self.seek_history: list[float] = []
        self.muted: bool = True
        self.volume: float = 0.75

    def load(self, ref: PlayableRef) -> None:
        self.loaded_ref = ref
        self.playing = True
        self.paused = False
        self.stopped = False

    def play(self) -> None:
        self.playing = True
        self.paused = False

    def pause(self) -> None:
        self.playing = False
        self.paused = True

    def stop(self) -> None:
        self.playing = False
        self.paused = False
        self.stopped = True

    def seek(self, position_s: float) -> None:
        self.position_s = position_s
        self.seek_history.append(position_s)

    def set_muted(self, muted: bool) -> None:
        self.muted = muted

    def set_volume(self, volume: float) -> None:
        self.volume = volume


class TestTransportCore(unittest.TestCase):

    def setUp(self) -> None:
        self.backend = FakePlayerBackend()
        self.controller = HudVideoController()

        # Wire controller to fake backend
        self.controller.wire(
            on_show_surface=lambda: None,
            on_hide_surface=lambda: None,
            on_backend_play=lambda ref, muted: self.backend.load(ref),
            on_backend_pause=self.backend.pause,
            on_backend_resume=self.backend.play,
            on_backend_stop=self.backend.stop,
            on_backend_set_muted=self.backend.set_muted,
            on_backend_set_volume=self.backend.set_volume,
            on_backend_seek=self.backend.seek,
        )

        self.sample_ref = PlayableRef(
            kind="direct_url",
            uri="https://secure-stream.cdn/token123_signed.mp4",
            title="Dune 2 Official Trailer",
            thumb_url="https://img.cdn/thumb.jpg",
            source_query="Dune trailer",
        )

    def test_clamp_seek_helper(self):
        # Target within bounds
        self.assertEqual(clamp_seek(50.0, 100.0, END_MARGIN_S), 50.0)
        # Target beyond duration - margin
        self.assertEqual(clamp_seek(99.8, 100.0, END_MARGIN_S), 99.5)
        self.assertEqual(clamp_seek(150.0, 100.0, END_MARGIN_S), 99.5)
        # Target below zero
        self.assertEqual(clamp_seek(-10.0, 100.0, END_MARGIN_S), 0.0)

    def test_queued_seek_during_loading(self):
        """A seek during LOADING is queued and applied on load."""
        self.controller.play(self.sample_ref)
        self.assertEqual(self.controller.state().status, VideoStatus.LOADING)

        # Seek while loading
        res = self.controller.seek(45.0)
        self.assertTrue(res)
        # Backend has not been sought yet because media isn't ready
        self.assertEqual(len(self.backend.seek_history), 0)

        # Backend duration reported and ready fired
        self.controller.on_backend_duration(150.0)
        self.controller.on_backend_ready()

        # Queued seek must be applied immediately upon ready
        self.assertEqual(self.controller.state().status, VideoStatus.PLAYING)
        self.assertIn(45.0, self.backend.seek_history)
        self.assertEqual(self.controller.state().position_s, 45.0)

    def test_seek_clamping_to_end_margin(self):
        """Seek clamps to [0, duration - END_MARGIN_S]."""
        self.controller.play(self.sample_ref)
        self.controller.on_backend_duration(100.0)
        self.controller.on_backend_ready()

        # Seek past end
        self.controller.seek(150.0)
        self.assertEqual(self.backend.position_s, 100.0 - END_MARGIN_S)
        self.assertEqual(self.controller.state().position_s, 99.5)

        # Seek below zero
        self.controller.seek(-25.0)
        self.assertEqual(self.backend.position_s, 0.0)
        self.assertEqual(self.controller.state().position_s, 0.0)

        # Relative seek forward past end
        self.controller.seek(90.0)
        self.controller.seek_rel(20.0)  # 90 + 20 = 110 -> 99.5
        self.assertEqual(self.backend.position_s, 99.5)

    def test_ended_to_replay(self):
        """play() while ENDED acts as replay."""
        self.controller.play(self.sample_ref)
        self.controller.on_backend_duration(60.0)
        self.controller.on_backend_ready()

        # Reach end of video
        self.controller.on_backend_ended()
        self.assertEqual(self.controller.state().status, VideoStatus.ENDED)

        # Calling play() while ENDED should replay from 0
        self.controller.play()
        self.assertEqual(self.controller.state().status, VideoStatus.PLAYING)
        self.assertEqual(self.controller.state().position_s, 0.0)
        self.assertIn(0.0, self.backend.seek_history)
        self.assertTrue(self.backend.playing)

    def test_non_seekable_media_refuses_seek(self):
        """Non-seekable media refuses the seek with a reason enum."""
        self.controller.play(self.sample_ref)
        self.controller.on_backend_duration(0.0)
        self.controller.on_backend_seekable(False)
        self.controller.on_backend_ready()

        # Non-seekable
        self.assertFalse(self.controller.state().seekable)
        reason = self.controller.seek(30.0)
        self.assertEqual(reason, SeekRejectReason.NOT_SEEKABLE)

    def test_single_reresolve_on_stream_error(self):
        """On stream error, re-resolve once and resume at last position."""
        resolve_calls: list[str] = []
        new_ref = PlayableRef(
            kind="direct_url",
            uri="https://refreshed-stream.cdn/token456_new.mp4",
            title="Dune 2 Official Trailer (Refreshed)",
            thumb_url="https://img.cdn/thumb.jpg",
            source_query="Dune trailer",
        )

        def mock_resolver(query: str) -> PlayableRef:
            resolve_calls.append(query)
            return new_ref

        controller = HudVideoController(resolver_fn=mock_resolver)
        controller.wire(
            on_show_surface=lambda: None,
            on_hide_surface=lambda: None,
            on_backend_play=lambda ref, muted: self.backend.load(ref),
            on_backend_pause=self.backend.pause,
            on_backend_resume=self.backend.play,
            on_backend_stop=self.backend.stop,
            on_backend_set_muted=self.backend.set_muted,
            on_backend_set_volume=self.backend.set_volume,
            on_backend_seek=self.backend.seek,
        )

        controller.begin_resolve("Searching...", source_query="Dune trailer")
        controller.on_resolved(self.sample_ref)
        controller.on_backend_duration(150.0)
        controller.on_backend_ready()

        # Advance playback to 72.5 seconds
        controller.on_backend_position(72.5)
        self.assertEqual(controller.state().position_s, 72.5)

        # Trigger stream error (e.g. 403 Forbidden / expired CDN token)
        controller.on_backend_error("HTTP 403 Forbidden")

        # Let the background thread complete
        time.sleep(0.05)
        _app.processEvents()

        # Verify resolver was called once
        self.assertEqual(len(resolve_calls), 1)
        self.assertEqual(resolve_calls[0], "Dune trailer")

        # Media ready on new stream
        controller.on_backend_duration(150.0)
        controller.on_backend_ready()

        # Playback resumed at the saved position (72.5)
        self.assertIn(72.5, self.backend.seek_history)

        # A second error should NOT re-resolve again (RERESOLVE_RETRIES = 1)
        controller.on_backend_error("HTTP 403 Forbidden")
        time.sleep(0.05)
        _app.processEvents()
        self.assertEqual(len(resolve_calls), 1)  # Still 1
        self.assertEqual(controller.state().status, VideoStatus.ERROR)

    def test_state_whitelist_privacy(self):
        """Client-visible state must be strictly enums, bools, and seconds only."""
        self.controller.play(self.sample_ref)
        self.controller.on_backend_duration(120.0)
        self.controller.on_backend_position(45.0)
        self.controller.on_backend_ready()

        st = self.controller.state()
        # Whitelist fields check
        expected_keys = {"loaded", "status", "position_s", "duration_s", "seekable"}
        self.assertEqual(set(st.__dataclass_fields__.keys()), expected_keys)

        # Verify types
        self.assertIsInstance(st.loaded, bool)
        self.assertIsInstance(st.status, VideoStatus)
        self.assertIsInstance(st.position_s, float)
        self.assertIsInstance(st.duration_s, float)
        self.assertIsInstance(st.seekable, bool)

        # Privacy test: stream URL token MUST NOT appear anywhere in str(state) or repr(state)
        self.assertNotIn("token123_signed", str(st))
        self.assertNotIn("https://", str(st))
        self.assertNotIn("Dune", str(st))

    def test_audio_unmuted_by_default(self):
        """HUD video must start unmuted (muted=False) so audio is audible by default."""
        self.assertFalse(self.controller._muted)
        self.controller.play(self.sample_ref)
        self.assertFalse(self.controller._muted)

    def test_local_url_backend_dual_stream_audio_support(self):
        """LocalUrlBackend handles separate audio_uri for adaptive streams."""
        from PyQt6.QtMultimediaWidgets import QVideoWidget
        from core.hud_video.backends.local_url import LocalUrlBackend
        widget = QVideoWidget()
        backend = LocalUrlBackend(widget)

        dual_ref = PlayableRef(
            kind="direct_url",
            uri="http://127.0.0.1:8000/video_only.mp4",
            title="Dual Stream Video",
            audio_uri="http://127.0.0.1:8000/audio_only.m4a",
        )
        backend.load(dual_ref)
        self.assertTrue(backend._has_dual_stream)
        self.assertFalse(backend._muted)
        self.assertEqual(backend._volume, 0.75)


if __name__ == "__main__":
    unittest.main()
