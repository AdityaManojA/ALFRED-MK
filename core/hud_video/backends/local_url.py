"""
core/hud_video/backends/local_url.py — QMediaPlayer backend.

Handles:
  - local_file kind: file:// URI
  - direct_url kind: http(s):// direct media stream

Must be created on the Qt thread (QObject hierarchy).
Emits Qt signals consumed by HudVideoController.
"""

from __future__ import annotations

import logging
from typing import Callable

from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget

from core.hud_video.backends import BackendBase
from core.hud_video.resolve import PlayableRef

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

BACKEND_DEFAULT_VOLUME: float = 0.75    # volume when unmuted (0.0–1.0)
PLAYER_STOP_WAIT_MS: int = 300          # max ms to wait for demuxer/player to stop


class LocalUrlBackend(QObject, BackendBase):
    """Qt Multimedia backend for local files and direct HTTP media URLs.

    Signals
    -------
    on_ready()   — first frame decoded / media buffered
    on_error(str) — short error description
    on_ended()   — natural end of stream
    """

    on_ready = pyqtSignal()
    on_error = pyqtSignal(str)
    on_ended = pyqtSignal()
    on_position_changed = pyqtSignal(float)
    on_duration_changed = pyqtSignal(float)
    on_seekable_changed = pyqtSignal(bool)

    def __init__(self, video_widget: QVideoWidget, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._volume: float = BACKEND_DEFAULT_VOLUME
        self._muted: bool = False
        self._ready_fired: bool = False
        self._has_dual_stream: bool = False

        self._audio = QAudioOutput(self)
        self._audio.setVolume(self._volume)
        self._audio.setMuted(self._muted)

        self._player = QMediaPlayer(self)
        self._player.setAudioOutput(self._audio)
        self._player.setVideoOutput(video_widget)

        self._audio_player = QMediaPlayer(self)
        self._audio_player.errorOccurred.connect(self._on_audio_player_error)

        self._player.playbackStateChanged.connect(self._on_playback_state)
        self._player.mediaStatusChanged.connect(self._on_media_status)
        self._player.errorOccurred.connect(self._on_player_error)
        self._player.bufferProgressChanged.connect(self._on_buffer_progress)
        self._player.positionChanged.connect(self._on_position_changed_slot)
        self._player.durationChanged.connect(self._on_duration_changed_slot)
        self._player.seekableChanged.connect(self._on_seekable_changed_slot)

    # ------------------------------------------------------------------
    # BackendBase interface
    # ------------------------------------------------------------------

    def _wait_stopped(self, max_ms: int = PLAYER_STOP_WAIT_MS) -> None:
        """Wait for player to enter StoppedState before switching sources."""
        if self._player.playbackState() == QMediaPlayer.PlaybackState.StoppedState and (
            not self._has_dual_stream or self._audio_player.playbackState() == QMediaPlayer.PlaybackState.StoppedState
        ):
            return
        self._player.stop()
        if self._has_dual_stream:
            self._audio_player.stop()
        from PyQt6.QtCore import QCoreApplication, QElapsedTimer
        timer = QElapsedTimer()
        timer.start()
        while self._player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            if timer.elapsed() >= max_ms:
                break
            QCoreApplication.processEvents()

    def load(self, ref: PlayableRef) -> None:
        from core.hud_video.controller import assert_gui_thread
        assert_gui_thread()

        # Stop, wait for demuxer shutdown, and clear any existing stream first
        self.stop()

        self._ready_fired = False
        self._has_dual_stream = bool(ref.audio_uri)

        if ref.kind == "local_file":
            video_url = QUrl.fromLocalFile(ref.uri)
        else:
            video_url = QUrl(ref.uri)

        if ref.audio_uri:
            # Separate video and audio streams
            self._player.setAudioOutput(None)
            self._audio_player.setAudioOutput(self._audio)
            self._audio_player.setSource(QUrl(ref.audio_uri))
        else:
            # Single stream containing both video & audio
            self._audio_player.setSource(QUrl())
            self._player.setAudioOutput(self._audio)

        self._audio.setVolume(self._volume if not self._muted else 0.0)
        self._audio.setMuted(self._muted)

        self._player.setSource(video_url)
        self._player.play()     # must call play() to trigger buffering
        if self._has_dual_stream:
            self._audio_player.play()

    def play(self) -> None:
        from core.hud_video.controller import assert_gui_thread
        assert_gui_thread()
        self._player.play()
        if self._has_dual_stream:
            self._audio_player.play()

    def pause(self) -> None:
        from core.hud_video.controller import assert_gui_thread
        assert_gui_thread()
        self._player.pause()
        if self._has_dual_stream:
            self._audio_player.pause()

    def stop(self) -> None:
        from core.hud_video.controller import assert_gui_thread
        assert_gui_thread()
        self._ready_fired = False
        self._wait_stopped(PLAYER_STOP_WAIT_MS)
        self._player.setSource(QUrl())  # release decoder / file handles
        self._audio_player.setSource(QUrl())
        self._has_dual_stream = False

    def set_muted(self, muted: bool) -> None:
        from core.hud_video.controller import assert_gui_thread
        assert_gui_thread()
        self._muted = muted
        self._audio.setMuted(muted)
        if not muted:
            self._audio.setVolume(self._volume)

    def set_volume(self, volume: float) -> None:
        from core.hud_video.controller import assert_gui_thread
        assert_gui_thread()
        self._volume = max(0.0, min(1.0, volume))
        if not self._muted:
            self._audio.setVolume(self._volume)

    def seek(self, position_s: float) -> None:
        from core.hud_video.controller import assert_gui_thread
        assert_gui_thread()
        ms = int(max(0.0, position_s) * 1000)
        self._player.setPosition(ms)
        if self._has_dual_stream:
            self._audio_player.setPosition(ms)

    # ------------------------------------------------------------------
    # Private Qt slot handlers
    # ------------------------------------------------------------------

    def _on_playback_state(self, state: QMediaPlayer.PlaybackState) -> None:
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        stopped = state == QMediaPlayer.PlaybackState.StoppedState

        # Fire on_ready once when we first enter Playing state
        if playing and not self._ready_fired:
            self._ready_fired = True
            self.on_ready.emit()

        if stopped and self._ready_fired:
            self.on_ended.emit()

    def _on_media_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia and self._ready_fired:
            self.on_ended.emit()

    def _on_player_error(
        self,
        error: QMediaPlayer.Error,
        error_string: str,
    ) -> None:
        if error != QMediaPlayer.Error.NoError:
            log.warning("[LocalUrlBackend] error %s: %s", error, error_string)
            self.on_error.emit(error_string[:80])

    def _on_audio_player_error(
        self,
        error: QMediaPlayer.Error,
        error_string: str,
    ) -> None:
        if error != QMediaPlayer.Error.NoError:
            log.warning("[LocalUrlBackend] audio player error %s: %s", error, error_string)

    def _on_buffer_progress(self, progress: float) -> None:
        # Optional: could expose progress to loading chrome in future
        pass

    def _on_position_changed_slot(self, position_ms: int) -> None:
        if self._has_dual_stream:
            # Keep audio synchronized with video if drift exceeds 400ms
            audio_pos_ms = self._audio_player.position()
            if abs(position_ms - audio_pos_ms) > 400:
                self._audio_player.setPosition(position_ms)
        self.on_position_changed.emit(max(0.0, position_ms / 1000.0))

    def _on_duration_changed_slot(self, duration_ms: int) -> None:
        self.on_duration_changed.emit(max(0.0, duration_ms / 1000.0))

    def _on_seekable_changed_slot(self, seekable: bool) -> None:
        self.on_seekable_changed.emit(seekable)
