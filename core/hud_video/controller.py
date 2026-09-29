"""
core/hud_video/controller.py — HUD Video session state machine.

HudVideoController owns: state, current PlayableRef, and UI-side signals.
It is a QObject (so it can own a QTimer) and should be created on the Qt thread.

State machine:
    IDLE -> RESOLVING -> LOADING -> PLAYING -> PAUSED -> IDLE
    Any live state -> ERROR -> IDLE
    Any live state -> IDLE (via stop())
"""

from __future__ import annotations

import logging
from enum import Enum, auto
from typing import Callable

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from .resolve import PlayableRef

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named constants — all tunables in one place
# ---------------------------------------------------------------------------

VIDEO_IDLE_UNLOAD_S: int = 300      # seconds background before auto-stop
VIDEO_ERROR_DISPLAY_S: float = 3.5  # seconds ERROR state shows before -> IDLE
VIDEO_DEFAULT_VOLUME: float = 0.75  # applied when user unmutes (0.0–1.0)
VIDEO_VOLUME_STEP: float = 0.10     # louder/quieter step

VIDEO_ACK_LINES: tuple[str, ...] = (
    "Coming up, sir.",
    "On screen shortly, sir.",
    "Pulling that in now, sir.",
)

VIDEO_RESOLVE_TIMEOUT_S: int = 30   # max RESOLVING duration


class VideoState(Enum):
    IDLE = auto()
    RESOLVING = auto()
    LOADING = auto()
    PLAYING = auto()
    PAUSED = auto()
    ERROR = auto()


class HudVideoController(QObject):
    """Singleton-like session controller for HUD video.

    Owns the state machine. The HudVideoSurface holds a reference to this
    controller and subscribes to its signals. The action handler calls the
    public API methods, which are all thread-safe (they post to the Qt thread).

    Signals
    -------
    state_changed(VideoState)
    status_text_changed(str)      — short human-readable status line
    ready(PlayableRef)            — backend loaded, playback about to start
    failed(str)                   — short error code / user-visible message
    """

    state_changed = pyqtSignal(object)          # VideoState
    status_text_changed = pyqtSignal(str)
    ready = pyqtSignal(object)                  # PlayableRef
    failed = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state: VideoState = VideoState.IDLE
        self._ref: PlayableRef | None = None
        self._muted: bool = True
        self._volume: float = VIDEO_DEFAULT_VOLUME
        self._on_show_surface: Callable[[], None] | None = None
        self._on_hide_surface: Callable[[], None] | None = None
        self._on_backend_play: Callable[[PlayableRef, bool], None] | None = None
        self._on_backend_pause: Callable[[], None] | None = None
        self._on_backend_resume: Callable[[], None] | None = None
        self._on_backend_stop: Callable[[], None] | None = None
        self._on_backend_set_muted: Callable[[bool], None] | None = None
        self._on_backend_set_volume: Callable[[float], None] | None = None

        # Auto-unload timer: fires VIDEO_IDLE_UNLOAD_S after leaving foreground
        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self._on_idle_timeout)

        # Error-clear timer: flash ERROR for a short time then go IDLE
        self._error_timer = QTimer(self)
        self._error_timer.setSingleShot(True)
        self._error_timer.timeout.connect(self._clear_error)

        # Resolve timeout guard
        self._resolve_timer = QTimer(self)
        self._resolve_timer.setSingleShot(True)
        self._resolve_timer.timeout.connect(self._on_resolve_timeout)

    # ------------------------------------------------------------------
    # Wire-up (called once at construction by MainWindow / surface owner)
    # ------------------------------------------------------------------

    def wire(
        self,
        on_show_surface: Callable[[], None],
        on_hide_surface: Callable[[], None],
        on_backend_play: Callable[[PlayableRef, bool], None],
        on_backend_pause: Callable[[], None],
        on_backend_resume: Callable[[], None],
        on_backend_stop: Callable[[], None],
        on_backend_set_muted: Callable[[bool], None],
        on_backend_set_volume: Callable[[float], None],
    ) -> None:
        """Inject surface + backend callbacks.  Called once from MainWindow."""
        self._on_show_surface = on_show_surface
        self._on_hide_surface = on_hide_surface
        self._on_backend_play = on_backend_play
        self._on_backend_pause = on_backend_pause
        self._on_backend_resume = on_backend_resume
        self._on_backend_stop = on_backend_stop
        self._on_backend_set_muted = on_backend_set_muted
        self._on_backend_set_volume = on_backend_set_volume

    # ------------------------------------------------------------------
    # Public API — all safe to call from any thread via QMetaObject or
    # Qt signal/slot queued connection; Qt will marshal to the Qt thread.
    # ------------------------------------------------------------------

    @property
    def state(self) -> VideoState:
        return self._state

    @property
    def is_active(self) -> bool:
        """True when video surface should be visible (not IDLE or ERROR->gone)."""
        return self._state in (
            VideoState.RESOLVING,
            VideoState.LOADING,
            VideoState.PLAYING,
            VideoState.PAUSED,
            VideoState.ERROR,
        )

    def begin_resolve(self, status: str = "Resolving…") -> None:
        """Transition to RESOLVING; show surface with loading chrome."""
        self._stop_all_timers()
        self._ref = None
        self._set_state(VideoState.RESOLVING)
        self._set_status(status)
        if self._on_show_surface:
            self._on_show_surface()
        self._resolve_timer.start(VIDEO_RESOLVE_TIMEOUT_S * 1000)

    def on_resolved(self, ref: PlayableRef) -> None:
        """Called when resolve() has a PlayableRef. Transition to LOADING."""
        self._resolve_timer.stop()
        if self._state != VideoState.RESOLVING:
            return
        self._ref = ref
        self._set_state(VideoState.LOADING)
        self._set_status(f"Loading: {ref.title}")
        if self._on_backend_play:
            self._on_backend_play(ref, self._muted)

    def on_backend_ready(self) -> None:
        """Called by backend when the first frame is ready to show."""
        if self._state != VideoState.LOADING:
            return
        self._set_state(VideoState.PLAYING)
        self._set_status("")
        if self._ref:
            self.ready.emit(self._ref)

    def play(self, ref: PlayableRef, *, muted: bool = True) -> None:
        """Shortcut: resolved ref already available — skip RESOLVING."""
        # Stop any in-progress playback first
        if self.is_active:
            self._do_stop_backend()
        self._muted = muted
        self._stop_all_timers()
        self._ref = ref
        self._set_state(VideoState.LOADING)
        self._set_status(f"Loading: {ref.title}")
        if self._on_show_surface:
            self._on_show_surface()
        if self._on_backend_play:
            self._on_backend_play(ref, muted)

    def pause(self) -> None:
        if self._state == VideoState.PLAYING:
            self._set_state(VideoState.PAUSED)
            self._set_status("Paused")
            if self._on_backend_pause:
                self._on_backend_pause()
            # Start idle unload countdown
            self._idle_timer.start(VIDEO_IDLE_UNLOAD_S * 1000)

    def resume(self) -> None:
        if self._state == VideoState.PAUSED:
            self._idle_timer.stop()
            self._set_state(VideoState.PLAYING)
            self._set_status("")
            if self._on_backend_resume:
                self._on_backend_resume()

    def stop(self) -> None:
        """Stop playback and return to avatar (IDLE)."""
        self._stop_all_timers()
        self._do_stop_backend()
        self._ref = None
        self._set_state(VideoState.IDLE)
        self._set_status("")
        if self._on_hide_surface:
            self._on_hide_surface()

    def signal_error(self, message: str) -> None:
        """Transition to ERROR state; auto-clear after ERROR_DISPLAY_S."""
        log.warning("[HudVideo] error: %s", message)
        self._stop_all_timers()
        self._do_stop_backend()
        self._set_state(VideoState.ERROR)
        self._set_status(f"Error: {message}")
        self.failed.emit(message)
        self._error_timer.start(int(VIDEO_ERROR_DISPLAY_S * 1000))

    def set_muted(self, muted: bool) -> None:
        self._muted = muted
        if self._on_backend_set_muted:
            self._on_backend_set_muted(muted)
        # Duck background music only when unmuted
        # (parent MainWindow handles duck via state_changed signal)

    def toggle_mute(self) -> None:
        self.set_muted(not self._muted)

    def set_volume(self, volume: float) -> None:
        """Set absolute volume 0.0–1.0. Effective only when unmuted."""
        self._volume = max(0.0, min(1.0, volume))
        if not self._muted and self._on_backend_set_volume:
            self._on_backend_set_volume(self._volume)

    def step_volume(self, delta: float) -> None:
        """Louder/quieter by VIDEO_VOLUME_STEP."""
        self.set_volume(self._volume + delta)

    def on_minimise(self) -> None:
        """Called by MainWindow.changeEvent when app is minimised."""
        if self._state == VideoState.PLAYING:
            self.pause()

    def on_restore(self) -> None:
        """Called by MainWindow.changeEvent when app is restored."""
        if self._state == VideoState.PAUSED:
            self.resume()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _set_state(self, state: VideoState) -> None:
        self._state = state
        self.state_changed.emit(state)

    def _set_status(self, text: str) -> None:
        self.status_text_changed.emit(text)

    def _do_stop_backend(self) -> None:
        if self._on_backend_stop:
            try:
                self._on_backend_stop()
            except Exception as exc:
                log.debug("[HudVideo] backend stop error: %s", exc)

    def _stop_all_timers(self) -> None:
        self._idle_timer.stop()
        self._error_timer.stop()
        self._resolve_timer.stop()

    def _on_idle_timeout(self) -> None:
        """Background idle too long — stop and unload."""
        if self._state == VideoState.PAUSED:
            self.stop()

    def _clear_error(self) -> None:
        """After error flash, return to IDLE and hide surface."""
        self._ref = None
        self._set_state(VideoState.IDLE)
        self._set_status("")
        if self._on_hide_surface:
            self._on_hide_surface()

    def _on_resolve_timeout(self) -> None:
        if self._state == VideoState.RESOLVING:
            self.signal_error("resolve_timeout")
