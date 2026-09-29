"""Private, application-owned arbitration of ALFRED audio sources."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
import threading
import time

from PyQt6.QtCore import QObject, pyqtSignal


STATE_SIGNAL_INTERVAL_S = 1.0


class AudioSource(Enum):
    APP_PLAYER = auto()
    TTS = auto()
    ALERT = auto()


@dataclass(frozen=True)
class MediaState:
    """The complete client-visible media state; deliberately identity-free."""

    app_playing: bool = False
    external_suppressed: bool = False
    suppressed_count: int = 0
    overridden: bool = False
    tts_ducking: bool = False


class MediaArbiter(QObject):
    """Coordinate local audio ownership without exposing external identities."""

    state_changed = pyqtSignal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._lock = threading.RLock()
        self._claims: set[AudioSource] = set()
        self._state = MediaState()
        self._last_emit_s = 0.0
        self._pending_timer: threading.Timer | None = None

    @property
    def state(self) -> MediaState:
        with self._lock:
            return self._state

    def claim(self, source: AudioSource) -> MediaState:
        with self._lock:
            if source in self._claims:
                return self._state
            self._claims.add(source)
            self._rebuild_state_locked()
            return self._state

    def release(self, source: AudioSource) -> MediaState:
        with self._lock:
            if source not in self._claims:
                return self._state
            self._claims.remove(source)
            self._rebuild_state_locked()
            return self._state

    def _rebuild_state_locked(self) -> None:
        next_state = MediaState(
            app_playing=AudioSource.APP_PLAYER in self._claims,
            tts_ducking=(
                AudioSource.APP_PLAYER in self._claims and AudioSource.TTS in self._claims
            ),
        )
        if next_state == self._state:
            return
        self._state = next_state
        self._schedule_state_signal_locked()

    def _schedule_state_signal_locked(self) -> None:
        now = time.monotonic()
        remaining_s = STATE_SIGNAL_INTERVAL_S - (now - self._last_emit_s)
        if remaining_s <= 0 and self._pending_timer is None:
            self._emit_state()
            return
        if self._pending_timer is None:
            self._pending_timer = threading.Timer(max(0.0, remaining_s), self._emit_state)
            self._pending_timer.daemon = True
            self._pending_timer.start()

    def _emit_state(self) -> None:
        with self._lock:
            self._pending_timer = None
            self._last_emit_s = time.monotonic()
            state = self._state
        self.state_changed.emit(state)


_arbiter_lock = threading.Lock()
_arbiter: MediaArbiter | None = None


def get_media_arbiter() -> MediaArbiter:
    """Return the sole arbiter owned by the running application."""
    global _arbiter
    with _arbiter_lock:
        if _arbiter is None:
            _arbiter = MediaArbiter()
        return _arbiter
