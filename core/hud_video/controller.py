"""
core/hud_video/controller.py — HUD Video session state machine and transport controller.

Enforces:
- Named constants at top of file
- Strict VideoState whitelist: loaded, status, position_s, duration_s, seekable
- Privacy: stream URLs are signed, never log them or put them in state
- Seek clamping to [0, duration - END_MARGIN_S]
- Seek queued during LOADING
- play() while ENDED acts as replay()
- Non-seekable media returns SeekRejectReason.NOT_SEEKABLE
- Single re-resolve on stream error (RERESOLVE_RETRIES = 1)
- Timestamp-throttled state emission at STATE_EMIT_HZ = 4 while PLAYING
- Off-thread voice call marshalling to Qt thread via signals
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Any

from PyQt6.QtCore import QObject, QTimer, QThread, pyqtSignal

from core.hud_video.resolve import PlayableRef
from core.hud_video.transport import (
    STATE_EMIT_HZ,
    END_MARGIN_S,
    RERESOLVE_RETRIES,
    SKIP_S,
    PAUSE_ON_MINIMISE,
    VideoStatus,
    SeekRejectReason,
    VideoState,
    clamp_seek,
    format_timestamp,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------
VIDEO_IDLE_UNLOAD_S: int = 120       # Seconds after pause before auto-unloading to IDLE
VIDEO_ERROR_DISPLAY_S: float = 3.5   # Seconds ERROR state shows before auto-clearing to IDLE
VIDEO_DEFAULT_VOLUME: float = 0.75   # Applied when user unmutes (0.0–1.0)
VIDEO_VOLUME_STEP: float = 0.10      # Louder/quieter step
VIDEO_RESOLVE_TIMEOUT_S: int = 30    # Max RESOLVING duration in seconds
DUCK_VOLUME_PCT: float = 30.0        # Volume percentage during TTS/mic speech ducking

# Re-export for convenience / backwards compatibility
VideoState = VideoState
VideoStatus = VideoStatus
SeekRejectReason = SeekRejectReason

from core.gui_thread import assert_gui_thread


class HudVideoController(QObject):
    """Session controller and transport manager for the Visual HUD.

    Signals
    -------
    video_state_changed(VideoState) — Whitelisted state snapshot, throttled to STATE_EMIT_HZ
    state_changed(object)           — Emits VideoState (retains backward compatibility)
    status_text_changed(str)        — Short status line for UI display
    ready(PlayableRef)              — Backend loaded, first frame ready
    failed(str)                     — Short error message / reason code
    toast_requested(str)            — Request in-HUD toast display
    """

    video_state_changed = pyqtSignal(object)    # VideoState
    state_changed = pyqtSignal(object)          # VideoState
    status_text_changed = pyqtSignal(str)
    ready = pyqtSignal(object)                  # PlayableRef
    failed = pyqtSignal(str)
    toast_requested = pyqtSignal(str)

    # Internal signals for marshalling cross-thread calls to Qt thread (QueuedConnection)
    _sig_begin_resolve = pyqtSignal(str, str)
    _sig_source_ready = pyqtSignal(object, float)
    _sig_signal_error = pyqtSignal(str)
    _sig_play = pyqtSignal(object, bool)
    _sig_pause = pyqtSignal()
    _sig_toggle = pyqtSignal()
    _sig_replay = pyqtSignal()
    _sig_seek = pyqtSignal(float)
    _sig_seek_rel = pyqtSignal(float)
    _sig_stop = pyqtSignal()
    _sig_set_muted = pyqtSignal(bool)
    _sig_set_volume = pyqtSignal(float)

    def __init__(
        self,
        parent: QObject | None = None,
        resolver_fn: Callable[[str], PlayableRef] | None = None,
    ) -> None:
        super().__init__(parent)
        self._resolver_fn = resolver_fn

        # Playback tracking
        self._status: VideoStatus = VideoStatus.IDLE
        self._loaded: bool = False
        self._position_s: float = 0.0
        self._duration_s: float = 0.0
        self._seekable: bool = False
        self._queued_seek: float | None = None
        self._reresolve_count: int = 0
        self._source_query: str = ""
        self._last_emit_time: float = 0.0

        self._ref: PlayableRef | None = None
        self._muted: bool = False
        self._volume: float = VIDEO_DEFAULT_VOLUME

        # Injected backend & surface callbacks
        self._on_show_surface: Callable[[], None] | None = None
        self._on_hide_surface: Callable[[], None] | None = None
        self._on_backend_play: Callable[[PlayableRef, bool], None] | None = None
        self._on_backend_pause: Callable[[], None] | None = None
        self._on_backend_resume: Callable[[], None] | None = None
        self._on_backend_stop: Callable[[], None] | None = None
        self._on_backend_seek: Callable[[float], None] | None = None
        self._on_backend_set_muted: Callable[[bool], None] | None = None
        self._on_backend_set_volume: Callable[[float], None] | None = None

        # Timers
        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self._on_idle_timeout)

        self._error_timer = QTimer(self)
        self._error_timer.setSingleShot(True)
        self._error_timer.timeout.connect(self._clear_error)

        self._resolve_timer = QTimer(self)
        self._resolve_timer.setSingleShot(True)
        self._resolve_timer.timeout.connect(self._on_resolve_timeout)

        # Connect internal marshalling signals
        self._sig_begin_resolve.connect(self._do_begin_resolve)
        self._sig_source_ready.connect(self._do_source_ready)
        self._sig_signal_error.connect(self._do_signal_error)
        self._sig_play.connect(self._do_play)
        self._sig_pause.connect(self._do_pause)
        self._sig_toggle.connect(self._do_toggle)
        self._sig_replay.connect(self._do_replay)
        self._sig_seek.connect(self._do_seek)
        self._sig_seek_rel.connect(self._do_seek_rel)
        self._sig_stop.connect(self._do_stop)
        self._sig_set_muted.connect(self._do_set_muted)
        self._sig_set_volume.connect(self._do_set_volume)

    # ------------------------------------------------------------------
    # Wire-up
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
        on_backend_seek: Callable[[float], None] | None = None,
    ) -> None:
        """Inject surface + backend callbacks. Called once from MainWindow."""
        self._on_show_surface = on_show_surface
        self._on_hide_surface = on_hide_surface
        self._on_backend_play = on_backend_play
        self._on_backend_pause = on_backend_pause
        self._on_backend_resume = on_backend_resume
        self._on_backend_stop = on_backend_stop
        self._on_backend_set_muted = on_backend_set_muted
        self._on_backend_set_volume = on_backend_set_volume
        self._on_backend_seek = on_backend_seek

    # ------------------------------------------------------------------
    # Public Controller API (thread-safe, callable from voice threads)
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        """True when the Visual HUD surface should be visible."""
        return self._status in (
            VideoStatus.RESOLVING,
            VideoStatus.LOADING,
            VideoStatus.PLAYING,
            VideoStatus.PAUSED,
            VideoStatus.ENDED,
        )

    def state(self) -> VideoState:
        """Return the current whitelisted VideoState snapshot."""
        return VideoState(
            loaded=self._loaded,
            status=self._status,
            position_s=self._position_s,
            duration_s=self._duration_s,
            seekable=self._seekable,
        )

    def play(self, ref: PlayableRef | None = None, *, muted: bool = False) -> None:
        """Start or resume playback.

        If ref is given: loads and begins playback of new media.
        If ref is None:
          - If ENDED: acts as replay().
          - If PAUSED: resumes playback.
          - If PLAYING: no-op.
        """
        if self._is_off_thread():
            self._sig_play.emit(ref, muted)
            return
        self._do_play(ref, muted)

    def pause(self) -> None:
        """Pause playback."""
        if self._is_off_thread():
            self._sig_pause.emit()
            return
        self._do_pause()

    def toggle(self) -> None:
        """Toggle between play and pause."""
        if self._is_off_thread():
            self._sig_toggle.emit()
            return
        self._do_toggle()

    def replay(self) -> None:
        """Restart current video from 0.0 seconds."""
        if self._is_off_thread():
            self._sig_replay.emit()
            return
        self._do_replay()

    def seek(self, abs_s: float) -> bool | SeekRejectReason:
        """Seek to absolute seconds.

        Clamps to [0, duration - END_MARGIN_S].
        Queues seek if currently LOADING or RESOLVING.
        Refuses if media is non-seekable.
        """
        if not self._loaded and self._status == VideoStatus.IDLE:
            return SeekRejectReason.NOT_LOADED

        if self._status in (VideoStatus.LOADING, VideoStatus.RESOLVING):
            self._queued_seek = abs_s
            return True

        if not self._seekable:
            return SeekRejectReason.NOT_SEEKABLE

        if self._is_off_thread():
            self._sig_seek.emit(abs_s)
            return True

        return self._do_seek(abs_s)

    def seek_rel(self, delta_s: float) -> bool | SeekRejectReason:
        """Seek relative to current position by delta seconds."""
        if self._is_off_thread():
            self._sig_seek_rel.emit(delta_s)
            return True
        return self._do_seek_rel(delta_s)

    def stop(self) -> None:
        """Stop playback and return to avatar (IDLE)."""
        if self._is_off_thread():
            self._sig_stop.emit()
            return
        self._do_stop()

    def set_muted(self, muted: bool) -> None:
        if self._is_off_thread():
            self._sig_set_muted.emit(muted)
            return
        self._do_set_muted(muted)

    def _do_set_muted(self, muted: bool) -> None:
        assert_gui_thread()
        self._muted = muted
        if self._on_backend_set_muted:
            self._on_backend_set_muted(muted)

    def toggle_mute(self) -> None:
        self.set_muted(not self._muted)

    def set_volume(self, volume: float) -> None:
        if self._is_off_thread():
            self._sig_set_volume.emit(volume)
            return
        self._do_set_volume(volume)

    def _do_set_volume(self, volume: float) -> None:
        assert_gui_thread()
        self._volume = max(0.0, min(1.0, volume))
        if not self._muted and self._on_backend_set_volume:
            self._on_backend_set_volume(self._volume)

    def step_volume(self, delta: float) -> None:
        self.set_volume(self._volume + delta)

    def duck(self) -> None:
        """Duck video volume to DUCK_VOLUME_PCT while Alfred speaks or mic is open."""
        if not getattr(self, "_is_ducked", False) and not self._muted:
            self._pre_duck_volume = self._volume
            ducked_vol = (DUCK_VOLUME_PCT / 100.0) * self._volume
            if self._on_backend_set_volume:
                self._on_backend_set_volume(ducked_vol)
            self._is_ducked = True

    def unduck(self) -> None:
        """Restore video volume after speech/mic activity completes."""
        if getattr(self, "_is_ducked", False):
            if not self._muted and self._on_backend_set_volume:
                self._on_backend_set_volume(getattr(self, "_pre_duck_volume", self._volume))
            self._is_ducked = False

    def show_toast(self, message: str) -> None:
        """Request in-HUD toast acknowledgement."""
        self.toast_requested.emit(message)

    def on_minimise(self) -> None:
        """Called when main window is minimised."""
        if PAUSE_ON_MINIMISE:
            if self._status == VideoStatus.PLAYING:
                self._was_playing_before_minimise = True
                self.pause()
            else:
                self._was_playing_before_minimise = False

    def on_restore(self) -> None:
        """Called when main window is restored."""
        if PAUSE_ON_MINIMISE:
            if getattr(self, "_was_playing_before_minimise", False) and self._status == VideoStatus.PAUSED:
                self.resume()
            self._was_playing_before_minimise = False

    def resume(self) -> None:
        """Alias for resuming paused video."""
        self.play()

    # ------------------------------------------------------------------
    # Backend Signal Handlers (invoked by player backend)
    # ------------------------------------------------------------------

    def on_backend_position(self, position_s: float) -> None:
        """Handle position update from player backend."""
        self._position_s = max(0.0, position_s)
        now = time.monotonic()
        # Throttle position updates while PLAYING
        if self._status == VideoStatus.PLAYING:
            if now - self._last_emit_time >= (1.0 / STATE_EMIT_HZ):
                self._emit_state(now)

    def on_backend_duration(self, duration_s: float) -> None:
        """Handle duration update from player backend."""
        self._duration_s = max(0.0, duration_s)
        if self._duration_s > 0.0:
            self._seekable = True
        self._emit_state()

    def on_backend_seekable(self, seekable: bool) -> None:
        """Handle seekability status update."""
        self._seekable = seekable
        self._emit_state()

    def on_backend_ready(self) -> None:
        """Called by backend when the first frame is ready to show."""
        self._loaded = True
        self._set_status("")
        self._set_state(VideoStatus.PLAYING)

        # Apply queued seek if requested while loading
        if self._queued_seek is not None:
            target = self._queued_seek
            self._queued_seek = None
            self._do_seek(target)

        if self._ref:
            self.ready.emit(self._ref)

    def on_backend_ended(self) -> None:
        """Called when natural end of media is reached."""
        self._position_s = self._duration_s
        self._set_state(VideoStatus.ENDED)
        self._set_status("Ended")

    def on_backend_error(self, message: str) -> None:
        """Called when backend encounters a playback error."""
        log.warning("[HudVideo] backend error: %s", message)

        # Single re-resolve on stream expiry if retries remain
        if self._reresolve_count < RERESOLVE_RETRIES and (self._source_query or self._ref):
            self._reresolve_count += 1
            resume_pos = self._position_s
            self._queued_seek = resume_pos
            log.info("[HudVideo] re-resolving stream (attempt %d/%d) at pos=%.1fs",
                     self._reresolve_count, RERESOLVE_RETRIES, resume_pos)
            self._begin_re_resolve()
            return

        self.signal_error(message)

    def begin_resolve(self, status: str = "Resolving…", source_query: str = "") -> None:
        """Transition to RESOLVING; show surface with loading chrome."""
        if self._is_off_thread():
            self._sig_begin_resolve.emit(status, source_query)
            return
        self._do_begin_resolve(status, source_query)

    def _do_begin_resolve(self, status: str, source_query: str) -> None:
        assert_gui_thread()
        self._stop_all_timers()
        self._ref = None
        self._loaded = False
        self._position_s = 0.0
        self._duration_s = 0.0
        self._seekable = False
        self._queued_seek = None
        self._reresolve_count = 0
        self._source_query = source_query

        self._set_state(VideoStatus.RESOLVING)
        self._set_status(status)
        if self._on_show_surface:
            self._on_show_surface()
        self._resolve_timer.start(VIDEO_RESOLVE_TIMEOUT_S * 1000)

    def on_resolved(self, ref: PlayableRef, start_s: float = 0.0) -> None:
        """Called when resolve() yields a PlayableRef."""
        if self._is_off_thread():
            self._sig_source_ready.emit(ref, start_s)
            return
        self._do_source_ready(ref, start_s)

    def _do_source_ready(self, ref: PlayableRef, start_s: float = 0.0) -> None:
        assert_gui_thread()
        self._resolve_timer.stop()
        if self._status != VideoStatus.RESOLVING:
            return
        if start_s > 0:
            self._queued_seek = start_s
        self._ref = ref
        self._set_state(VideoStatus.LOADING)
        self._set_status(f"Loading: {ref.title}")
        if self._on_backend_play:
            self._on_backend_play(ref, self._muted)

    def signal_error(self, message: str) -> None:
        """Transition to ERROR state; auto-clear after VIDEO_ERROR_DISPLAY_S."""
        if self._is_off_thread():
            self._sig_signal_error.emit(message)
            return
        self._do_signal_error(message)

    def _do_signal_error(self, message: str) -> None:
        assert_gui_thread()
        log.warning("[HudVideo] error: %s", message)
        self._stop_all_timers()
        self._do_stop_backend()
        self._loaded = False
        self._set_state(VideoStatus.ERROR)
        self._set_status(f"Error: {message}")
        self.failed.emit(message)
        self._error_timer.start(int(VIDEO_ERROR_DISPLAY_S * 1000))

    # ------------------------------------------------------------------
    # Internal Implementations (executed on Qt thread)
    # ------------------------------------------------------------------

    def _is_off_thread(self) -> bool:
        """Check if caller is running on a non-Qt thread."""
        try:
            return QThread.currentThread() != self.thread()
        except Exception:
            return False

    def _do_play(self, ref: PlayableRef | None, muted: bool) -> None:
        assert_gui_thread()
        if ref is not None:
            # New media reference: stop existing and load
            if self.is_active:
                self._do_stop_backend()
            self._muted = muted
            self._stop_all_timers()
            self._ref = ref
            self._loaded = False
            self._position_s = 0.0
            self._duration_s = 0.0
            self._seekable = False
            if not getattr(self, "_is_reresolving", False):
                self._reresolve_count = 0
            self._is_reresolving = False
            self._set_state(VideoStatus.LOADING)
            self._set_status(f"Loading: {ref.title}")
            if self._on_show_surface:
                self._on_show_surface()
            if self._on_backend_play:
                self._on_backend_play(ref, muted)
            return

        # ref is None: resume, replay, or no-op
        if self._status == VideoStatus.ENDED:
            self._do_replay()
        elif self._status == VideoStatus.PAUSED:
            self._idle_timer.stop()
            self._set_state(VideoStatus.PLAYING)
            self._set_status("")
            if self._on_backend_resume:
                self._on_backend_resume()

    def _do_pause(self) -> None:
        assert_gui_thread()
        if self._status == VideoStatus.PLAYING:
            self._set_state(VideoStatus.PAUSED)
            self._set_status("Paused")
            if self._on_backend_pause:
                self._on_backend_pause()
            self._idle_timer.start(VIDEO_IDLE_UNLOAD_S * 1000)

    def _do_toggle(self) -> None:
        assert_gui_thread()
        if self._status == VideoStatus.PLAYING:
            self._do_pause()
        elif self._status in (VideoStatus.PAUSED, VideoStatus.ENDED):
            self._do_play(None, self._muted)

    def _do_replay(self) -> None:
        assert_gui_thread()
        self._idle_timer.stop()
        self._position_s = 0.0
        if self._on_backend_seek:
            self._on_backend_seek(0.0)
        self._set_state(VideoStatus.PLAYING)
        self._set_status("")
        if self._on_backend_resume:
            self._on_backend_resume()
        elif self._ref and self._on_backend_play:
            self._on_backend_play(self._ref, self._muted)

    def _do_seek(self, abs_s: float) -> bool:
        assert_gui_thread()
        clamped = clamp_seek(abs_s, self._duration_s, END_MARGIN_S)
        self._position_s = clamped
        if self._on_backend_seek:
            self._on_backend_seek(clamped)
        self._emit_state()
        return True

    def _do_seek_rel(self, delta_s: float) -> bool:
        assert_gui_thread()
        target = self._position_s + delta_s
        return self._do_seek(target)

    def _do_stop(self) -> None:
        assert_gui_thread()
        self._stop_all_timers()
        self._do_stop_backend()
        self._ref = None
        self._loaded = False
        self._position_s = 0.0
        self._duration_s = 0.0
        self._seekable = False
        self._queued_seek = None
        self._set_state(VideoStatus.IDLE)
        self._set_status("")
        if self._on_hide_surface:
            self._on_hide_surface()

    def _begin_re_resolve(self) -> None:
        """Trigger re-resolve in a background thread."""
        query = self._source_query or (self._ref.title if self._ref else "")
        self._is_reresolving = True
        self._set_state(VideoStatus.LOADING)
        self._set_status("Re-connecting stream…")

        def _worker():
            try:
                resolver = self._resolver_fn
                if resolver is None:
                    from core.hud_video.resolve import resolve
                    resolver = resolve
                new_ref = resolver(query)
                # Post back on Qt thread
                self._sig_play.emit(new_ref, self._muted)
            except Exception as exc:
                log.warning("[HudVideo] re-resolve failed: %s", exc)
                self.signal_error("Stream expired and re-connect failed.")

        t = threading.Thread(target=_worker, daemon=True, name="hud-video-reresolve")
        t.start()

    def _set_state(self, status: VideoStatus) -> None:
        assert_gui_thread()
        self._status = status
        self._emit_state(time.monotonic())

    def _set_status(self, text: str) -> None:
        assert_gui_thread()
        self.status_text_changed.emit(text)

    def _emit_state(self, now: float | None = None) -> None:
        assert_gui_thread()
        self._last_emit_time = now if now is not None else time.monotonic()
        curr_state = self.state()
        self.video_state_changed.emit(curr_state)
        self.state_changed.emit(curr_state)

    def _do_stop_backend(self) -> None:
        assert_gui_thread()
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
        if self._status == VideoStatus.PAUSED:
            self.stop()

    def _clear_error(self) -> None:
        self._ref = None
        self._loaded = False
        self._set_state(VideoStatus.IDLE)
        self._set_status("")
        if self._on_hide_surface:
            self._on_hide_surface()

    def _on_resolve_timeout(self) -> None:
        if self._status == VideoStatus.RESOLVING:
            self.signal_error("resolve_timeout")
