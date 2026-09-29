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

    def __init__(self, video_widget: QVideoWidget, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._volume: float = BACKEND_DEFAULT_VOLUME
        self._muted: bool = True
        self._ready_fired: bool = False

        self._audio = QAudioOutput(self)
        self._audio.setVolume(0.0)          # always start muted
        self._audio.setMuted(True)

        self._player = QMediaPlayer(self)
        self._player.setAudioOutput(self._audio)
        self._player.setVideoOutput(video_widget)

        self._player.playbackStateChanged.connect(self._on_playback_state)
        self._player.errorOccurred.connect(self._on_player_error)
        self._player.bufferProgressChanged.connect(self._on_buffer_progress)

    # ------------------------------------------------------------------
    # BackendBase interface
    # ------------------------------------------------------------------

    def load(self, ref: PlayableRef) -> None:
        self._ready_fired = False
        self._muted = True
        self._audio.setVolume(0.0)
        self._audio.setMuted(True)

        if ref.kind == "local_file":
            url = QUrl.fromLocalFile(ref.uri)
        else:
            url = QUrl(ref.uri)

        self._player.setSource(url)
        self._player.play()     # must call play() to trigger buffering

    def play(self) -> None:
        self._player.play()

    def pause(self) -> None:
        self._player.pause()

    def stop(self) -> None:
        self._player.stop()
        self._player.setSource(QUrl())  # release decoder / file handles

    def set_muted(self, muted: bool) -> None:
        self._muted = muted
        self._audio.setMuted(muted)
        if not muted:
            self._audio.setVolume(self._volume)

    def set_volume(self, volume: float) -> None:
        self._volume = max(0.0, min(1.0, volume))
        if not self._muted:
            self._audio.setVolume(self._volume)

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

    def _on_player_error(
        self,
        error: QMediaPlayer.Error,
        error_string: str,
    ) -> None:
        if error != QMediaPlayer.Error.NoError:
            log.warning("[LocalUrlBackend] error %s: %s", error, error_string)
            self.on_error.emit(error_string[:80])

    def _on_buffer_progress(self, progress: float) -> None:
        # Optional: could expose progress to loading chrome in future
        pass
