"""Private, application-owned arbitration of ALFRED audio sources."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
import threading
import time

from PyQt6.QtCore import QObject, pyqtSignal


STATE_SIGNAL_INTERVAL_S = 1.0
SUPPRESS_SWEEP_S = 3.0
EXTERNAL_OVERRIDE_WINDOW_S = 20.0
RESUME_EXTERNAL_ON_STOP = True
SPEAK_ON_SUPPRESS = True


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

    def __init__(self, parent: QObject | None = None, suppressor=None) -> None:
        super().__init__(parent)
        self._lock = threading.RLock()
        self._claims: set[AudioSource] = set()
        self._state = MediaState()
        self._last_emit_s = 0.0
        self._pending_timer: threading.Timer | None = None
        self._suppressor = suppressor
        self._suppressed_handles: set[object] = set()
        self._override_times: dict[object, list[float]] = {}
        self._overridden_handles: set[object] = set()
        self._watchdog_stop = threading.Event()
        self._watchdog_thread: threading.Thread | None = None
        self._notice_callback = None
        self._suppression_announced = False
        self._override_announced = False

    @property
    def state(self) -> MediaState:
        with self._lock:
            return self._state

    def claim(self, source: AudioSource) -> MediaState:
        with self._lock:
            if source in self._claims:
                return self._state
            self._claims.add(source)
            if source is AudioSource.APP_PLAYER:
                self._start_suppression_locked()
            self._rebuild_state_locked()
            return self._state

    def release(self, source: AudioSource) -> MediaState:
        with self._lock:
            if source not in self._claims:
                return self._state
            self._claims.remove(source)
            if source is AudioSource.APP_PLAYER:
                self._stop_suppression_locked()
            self._rebuild_state_locked()
            return self._state

    def _rebuild_state_locked(self) -> None:
        next_state = MediaState(
            app_playing=AudioSource.APP_PLAYER in self._claims,
            external_suppressed=self._state.external_suppressed,
            suppressed_count=self._state.suppressed_count,
            overridden=self._state.overridden,
            tts_ducking=(
                AudioSource.APP_PLAYER in self._claims and AudioSource.TTS in self._claims
            ),
        )
        if next_state == self._state:
            return
        self._state = next_state
        self._schedule_state_signal_locked()

    def set_notice_callback(self, callback) -> None:
        self._notice_callback = callback

    def _get_suppressor_locked(self):
        if self._suppressor is None:
            from .suppress import get_suppressor
            self._suppressor = get_suppressor()
        return self._suppressor

    def _start_suppression_locked(self) -> None:
        self._watchdog_stop.clear()
        if self._watchdog_thread is None or not self._watchdog_thread.is_alive():
            self._watchdog_thread = threading.Thread(
                target=self._watchdog_loop, name="media-suppress-watchdog", daemon=True
            )
            self._watchdog_thread.start()

    def _stop_suppression_locked(self) -> None:
        self._watchdog_stop.set()
        if RESUME_EXTERNAL_ON_STOP:
            suppressor = self._get_suppressor_locked()
            for handle in tuple(self._suppressed_handles):
                suppressor.resume(handle)
        self._suppressed_handles.clear()
        self._override_times.clear()
        self._overridden_handles.clear()
        self._suppression_announced = False
        self._override_announced = False
        self._state = MediaState(
            app_playing=False,
            tts_ducking=False,
        )
        self._schedule_state_signal_locked()
        self._rebuild_state_locked()

    def _watchdog_loop(self) -> None:
        while True:
            with self._lock:
                if AudioSource.APP_PLAYER not in self._claims:
                    return
                self._sweep_locked()
            if self._watchdog_stop.wait(SUPPRESS_SWEEP_S):
                return

    def _sweep_locked(self) -> None:
        suppressor = self._get_suppressor_locked()
        now = time.monotonic()
        suppressed_now = 0
        for handle in suppressor.enumerate_players():
            if handle in self._overridden_handles:
                continue
            if handle in self._suppressed_handles and suppressor.is_playing(handle):
                times = [stamp for stamp in self._override_times.get(handle, [])
                         if now - stamp <= EXTERNAL_OVERRIDE_WINDOW_S]
                times.append(now)
                self._override_times[handle] = times
                if len(times) >= 2:
                    self._overridden_handles.add(handle)
                    continue
            if suppressor.pause(handle):
                self._suppressed_handles.add(handle)
                suppressed_now += 1
        next_state = MediaState(
            app_playing=AudioSource.APP_PLAYER in self._claims,
            external_suppressed=bool(self._suppressed_handles),
            suppressed_count=len(self._suppressed_handles),
            overridden=bool(self._overridden_handles),
            tts_ducking=(AudioSource.APP_PLAYER in self._claims and AudioSource.TTS in self._claims),
        )
        if next_state != self._state:
            self._state = next_state
            self._schedule_state_signal_locked()
        if suppressed_now and not self._suppression_announced:
            self._suppression_announced = True
            self._notice("I'll take it from here, sir.")
        if self._overridden_handles and not self._override_announced:
            self._override_announced = True
            self._notice("As you wish, sir — I'll share the stage.")

    def _notice(self, text: str) -> None:
        callback = self._notice_callback
        if callback and SPEAK_ON_SUPPRESS:
            callback(text)

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
