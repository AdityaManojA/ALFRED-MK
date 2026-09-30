"""Reusable, in-memory continuous screen monitoring.

The controller owns only the polling lifecycle. Screen interpretation is supplied
through an analyzer callback so callers can use local heuristics, OCR, or a vision
model without coupling those choices to capture scheduling.
"""
from __future__ import annotations

import hashlib
import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from io import BytesIO
from typing import Callable, Mapping

from PIL import Image

from actions.screen_processor import capture_screen


_LOGGER = logging.getLogger(__name__)
_COMPLETION_WORDS = re.compile(
    r"\b(done|complete|completed|finished|success|succeeded|failed|failure|error)\b",
    re.IGNORECASE,
)
_FINGERPRINT_SIZE = 16
_VISUAL_CHANGE_THRESHOLD = 0.08


@dataclass(frozen=True, slots=True)
class ScreenObservation:
    """One captured frame and its metadata, retained only until the next frame."""

    image_bytes: bytes
    mime_type: str
    window_context: str
    captured_at: datetime
    visual_fingerprint: tuple[int, ...] | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Result returned by a screen analyzer."""

    meaningful_change: bool = False
    completed: bool = False
    summary: str = ""
    event_key: str | None = None


@dataclass(frozen=True, slots=True)
class ScreenMonitorEvent:
    """Event delivered to meaningful-state and completion callbacks."""

    goal: str
    observation: ScreenObservation
    analysis: AnalysisResult


@dataclass(frozen=True, slots=True)
class ScreenMonitorStatus:
    """Thread-safe snapshot of controller state."""

    active: bool
    goal: str | None
    interval_seconds: float
    latest_observation: ScreenObservation | None
    consecutive_failures: int
    capture_count: int
    completed: bool
    stopped_reason: str | None
    last_error: str | None


CaptureCallback = Callable[[], object]
AnalysisCallback = Callable[
    [ScreenObservation, ScreenObservation | None, str],
    AnalysisResult | Mapping[str, object] | None,
]
EventCallback = Callable[[ScreenMonitorEvent], None]
StoppedCallback = Callable[[ScreenMonitorStatus], None]


def _visual_fingerprint(
    image_bytes: bytes,
    size: int = _FINGERPRINT_SIZE,
) -> tuple[int, ...]:
    """Return a tiny grayscale frame representation without writing image data."""
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            reduced = image.convert("L").resize(
                (size, size),
                Image.Resampling.BILINEAR,
            )
            return tuple(reduced.tobytes())
    except (OSError, ValueError):
        # Synthetic capture callbacks may supply non-image bytes. Exact changes
        # remain detectable without turning analyzer setup into capture failure.
        return tuple(hashlib.blake2s(image_bytes, digest_size=16).digest())


def _visual_difference(
    current: tuple[int, ...],
    previous: tuple[int, ...],
) -> float:
    """Return normalized mean absolute difference in the range 0.0 to 1.0."""
    if len(current) != len(previous) or not current:
        return 1.0
    return sum(abs(a - b) for a, b in zip(current, previous)) / (
        len(current) * 255.0
    )


def _fingerprint_key(fingerprint: tuple[int, ...]) -> str:
    return hashlib.blake2s(bytes(fingerprint), digest_size=8).hexdigest()


def _default_analyzer(
    observation: ScreenObservation,
    previous: ScreenObservation | None,
    goal: str,
    *,
    visual_change_threshold: float = _VISUAL_CHANGE_THRESHOLD,
) -> AnalysisResult:
    """Detect context, visual-frame, and explicit completion changes."""
    del goal
    completed = bool(_COMPLETION_WORDS.search(observation.window_context))
    context_changed = (
        previous is None
        or previous.window_context != observation.window_context
    )
    current_fingerprint = observation.visual_fingerprint or _visual_fingerprint(
        observation.image_bytes
    )
    previous_fingerprint = (
        previous.visual_fingerprint or _visual_fingerprint(previous.image_bytes)
        if previous is not None
        else None
    )
    visual_changed = (
        previous_fingerprint is not None
        and current_fingerprint != previous_fingerprint
        and _visual_difference(current_fingerprint, previous_fingerprint)
        >= visual_change_threshold
    )

    if completed:
        summary = "Possible completion signal detected in the active window."
        event_key = f"completion:{observation.window_context}"
    elif context_changed:
        summary = "Active window context changed."
        event_key = f"context:{observation.window_context}"
    elif visual_changed:
        summary = "Visual frame changed."
        event_key = f"visual:{_fingerprint_key(current_fingerprint)}"
    else:
        summary = ""
        event_key = None

    return AnalysisResult(
        meaningful_change=context_changed or visual_changed or completed,
        completed=completed,
        summary=summary,
        event_key=event_key,
    )


class ScreenMonitorController:
    """Poll screen capture in a daemon thread and retain only the latest frame."""

    def __init__(
        self,
        *,
        capture: CaptureCallback | None = None,
        analyze: AnalysisCallback | None = None,
        on_meaningful_state: EventCallback | None = None,
        on_completion: EventCallback | None = None,
        on_stopped: StoppedCallback | None = None,
        interval_seconds: float = 3.0,
        max_capture_failures: int = 3,
        visual_change_threshold: float = _VISUAL_CHANGE_THRESHOLD,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be greater than zero")
        if max_capture_failures <= 0:
            raise ValueError("max_capture_failures must be greater than zero")
        if not 0.0 <= visual_change_threshold <= 1.0:
            raise ValueError("visual_change_threshold must be between 0.0 and 1.0")

        self._capture = capture or capture_screen
        self._analyze = analyze or self._analyze_default
        self._on_meaningful_state = on_meaningful_state
        self._on_completion = on_completion
        self._on_stopped = on_stopped
        self._default_interval = float(interval_seconds)
        self._max_capture_failures = max_capture_failures
        self._visual_change_threshold = float(visual_change_threshold)

        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._active = False
        self._goal: str | None = None
        self._interval_seconds = self._default_interval
        self._latest_observation: ScreenObservation | None = None
        self._consecutive_failures = 0
        self._consecutive_degraded_frames = 0
        self._max_degraded_frames = 12
        self._capture_count = 0
        self._completed = False
        self._stopped_reason: str | None = None
        self._last_error: str | None = None
        self._emitted_meaningful_keys: set[str] = set()
        self._completion_emitted = False
        self._stopped_emitted = False

    def start(self, goal: str, interval_seconds: float | None = None) -> bool:
        """Start monitoring immediately; return false if a run is already active."""
        normalized_goal = goal.strip()
        if not normalized_goal:
            raise ValueError("goal must not be empty")
        interval = (
            self._default_interval
            if interval_seconds is None
            else float(interval_seconds)
        )
        if interval <= 0:
            raise ValueError("interval_seconds must be greater than zero")

        with self._lock:
            if self._active or (self._thread is not None and self._thread.is_alive()):
                return False

            self._stop_event.clear()
            self._active = True
            self._goal = normalized_goal
            self._interval_seconds = interval
            self._latest_observation = None
            self._consecutive_failures = 0
            self._consecutive_degraded_frames = 0
            self._capture_count = 0
            self._completed = False
            self._stopped_reason = None
            self._last_error = None
            self._emitted_meaningful_keys.clear()
            self._completion_emitted = False
            self._stopped_emitted = False
            self._thread = threading.Thread(
                target=self._run,
                name="ScreenMonitor",
                daemon=True,
            )
            thread = self._thread

        thread.start()
        return True

    def stop(self, *, wait: bool = True, timeout: float | None = None) -> bool:
        """Request a clean stop; optionally wait for the polling thread to exit."""
        with self._lock:
            was_active = self._active
            if was_active:
                self._active = False
                self._stopped_reason = "stopped"
            self._stop_event.set()
            thread = self._thread

        if was_active:
            self._emit_stopped()
        if (
            wait
            and thread is not None
            and thread is not threading.current_thread()
            and thread.is_alive()
        ):
            thread.join(timeout)
        return was_active

    def status(self) -> ScreenMonitorStatus:
        """Return an immutable snapshot without copying or persisting image bytes."""
        with self._lock:
            return self._status_unlocked()

    def _run(self) -> None:
        try:
            while not self._stop_event.is_set():
                sleep_s = self._interval_seconds
                try:
                    observation = self._capture_observation()
                except Exception as exc:
                    if self._record_capture_failure(exc):
                        return
                    backoff = min(self._interval_seconds * (1.5 ** min(self._consecutive_failures, 5)), 30.0)
                    if self._stop_event.wait(backoff):
                        return
                    continue

                # Detect degraded GDI / BitBlt fallback frames (e.g. 1x1 black frame or Unknown context)
                is_degraded = (
                    len(observation.image_bytes) < 700
                    and "Unknown" in observation.window_context
                )

                if is_degraded:
                    self._consecutive_degraded_frames += 1
                    sleep_s = min(self._interval_seconds * (1.5 ** min(self._consecutive_degraded_frames, 6)), 30.0)
                    if self._consecutive_degraded_frames >= self._max_degraded_frames:
                        _LOGGER.warning(
                            "Screen monitor entered degraded GDI fallback mode (%d consecutive attempts). Display may be locked or asleep.",
                            self._consecutive_degraded_frames,
                        )
                        if self._record_capture_failure(RuntimeError("GDI screen capture failed: screen unavailable or locked")):
                            return
                else:
                    self._consecutive_degraded_frames = 0
                    sleep_s = self._interval_seconds

                with self._lock:
                    previous = self._latest_observation
                    self._latest_observation = observation
                    self._consecutive_failures = 0
                    self._last_error = None
                    self._capture_count += 1
                    goal = self._goal or ""

                try:
                    result = self._coerce_analysis(self._analyze(observation, previous, goal))
                except Exception:
                    _LOGGER.exception("Screen monitor analysis failed")
                else:
                    if self._emit_analysis(result, observation, goal):
                        return

                if self._stop_event.wait(sleep_s):
                    return
        finally:
            with self._lock:
                self._active = False
                if self._thread is threading.current_thread():
                    self._thread = None

    def _capture_observation(self) -> ScreenObservation:
        captured = self._capture()
        if isinstance(captured, ScreenObservation):
            if captured.visual_fingerprint is not None:
                return captured
            return ScreenObservation(
                image_bytes=captured.image_bytes,
                mime_type=captured.mime_type,
                window_context=captured.window_context,
                captured_at=captured.captured_at,
                visual_fingerprint=_visual_fingerprint(captured.image_bytes),
            )

        try:
            image_bytes, mime_type, window_context = captured  # type: ignore[misc]
        except (TypeError, ValueError) as exc:
            raise TypeError(
                "capture callback must return ScreenObservation or "
                "(image_bytes, mime_type, window_context)"
            ) from exc
        if not isinstance(image_bytes, bytes):
            raise TypeError("capture callback image_bytes must be bytes")
        return ScreenObservation(
            image_bytes=image_bytes,
            mime_type=str(mime_type),
            window_context=str(window_context),
            captured_at=datetime.now(timezone.utc),
            visual_fingerprint=_visual_fingerprint(image_bytes),
        )

    def _analyze_default(
        self,
        observation: ScreenObservation,
        previous: ScreenObservation | None,
        goal: str,
    ) -> AnalysisResult:
        return _default_analyzer(
            observation,
            previous,
            goal,
            visual_change_threshold=self._visual_change_threshold,
        )

    def _record_capture_failure(self, exc: Exception) -> bool:
        with self._lock:
            self._consecutive_failures += 1
            self._last_error = f"{type(exc).__name__}: {exc}"
            terminal = self._consecutive_failures >= self._max_capture_failures
            if terminal:
                self._active = False
                self._stopped_reason = "capture_failures"
                self._stop_event.set()
                failures = self._consecutive_failures
            else:
                failures = self._consecutive_failures

        if terminal:
            _LOGGER.error(
                "Screen monitoring stopped after %d consecutive capture failures: %s",
                failures,
                exc,
            )
            self._emit_stopped()
        else:
            _LOGGER.warning(
                "Screen capture failed (%d/%d): %s",
                failures,
                self._max_capture_failures,
                exc,
            )
        return terminal

    @staticmethod
    def _coerce_analysis(
        result: AnalysisResult | Mapping[str, object] | None,
    ) -> AnalysisResult:
        if result is None:
            return AnalysisResult()
        if isinstance(result, AnalysisResult):
            return result
        if isinstance(result, Mapping):
            return AnalysisResult(
                meaningful_change=bool(result.get("meaningful_change", False)),
                completed=bool(result.get("completed", False)),
                summary=str(result.get("summary", "")),
                event_key=(
                    str(result["event_key"])
                    if result.get("event_key") is not None
                    else None
                ),
            )
        raise TypeError("analysis callback must return AnalysisResult, a mapping, or None")

    def _emit_analysis(
        self,
        result: AnalysisResult,
        observation: ScreenObservation,
        goal: str,
    ) -> bool:
        event = ScreenMonitorEvent(goal=goal, observation=observation, analysis=result)

        if result.completed:
            with self._lock:
                should_emit = not self._completion_emitted
                self._completion_emitted = True
                self._completed = True
                self._active = False
                self._stopped_reason = "completed"
                self._stop_event.set()
            if should_emit:
                self._invoke_callback(self._on_completion, event, "completion")
            self._emit_stopped()
            return True

        if result.meaningful_change:
            event_key = result.event_key or result.summary or observation.window_context
            with self._lock:
                should_emit = event_key not in self._emitted_meaningful_keys
                if should_emit:
                    self._emitted_meaningful_keys.add(event_key)
            if should_emit:
                self._invoke_callback(self._on_meaningful_state, event, "meaningful-state")
        return False

    def _status_unlocked(self) -> ScreenMonitorStatus:
        return ScreenMonitorStatus(
            active=self._active,
            goal=self._goal,
            interval_seconds=self._interval_seconds,
            latest_observation=self._latest_observation,
            consecutive_failures=self._consecutive_failures,
            capture_count=self._capture_count,
            completed=self._completed,
            stopped_reason=self._stopped_reason,
            last_error=self._last_error,
        )

    def _emit_stopped(self) -> None:
        with self._lock:
            if self._stopped_emitted or self._stopped_reason is None:
                return
            self._stopped_emitted = True
            callback = self._on_stopped
            status = self._status_unlocked()
        if callback is None:
            return
        try:
            callback(status)
        except Exception:
            _LOGGER.exception("Screen monitor stopped callback failed")

    @staticmethod
    def _invoke_callback(
        callback: EventCallback | None,
        event: ScreenMonitorEvent,
        callback_name: str,
    ) -> None:
        if callback is None:
            return
        try:
            callback(event)
        except Exception:
            _LOGGER.exception("Screen monitor %s callback failed", callback_name)


__all__ = [
    "AnalysisResult",
    "ScreenMonitorController",
    "ScreenMonitorEvent",
    "ScreenMonitorStatus",
    "ScreenObservation",
]
