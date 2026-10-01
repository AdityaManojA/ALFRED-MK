"""core/speech/whisper_shadow.py — Decoupled off-thread shadow Whisper ASR worker.

Guarantees & Invariants:
- Decoupled observer: listens to SharedAudioStream on a background worker thread.
- Transcribes speech speculatively using local faster-whisper ("tiny.en", int8, CPU).
- Emits WhisperPartial tokens for live HUD captions and intent prefetching.
- Zero audio interference: NEVER alters, gates, or delays the live Gemini stream.
- Fail-open: if model or library fails to initialize, logs once and silently idles.
"""

from __future__ import annotations

import dataclasses
import logging
import queue
import threading
import time
from typing import Callable, Optional, Union

import numpy as np

# ── Shadow Whisper Constants ────────────────────────────────────────────────
WHISPER_MODEL_NAME: str = "tiny.en"       # Fast lightweight English model
WHISPER_COMPUTE_TYPE: str = "int8"        # Low memory int8 CPU quantization
WHISPER_DEVICE: str = "cpu"               # CPU inference
WHISPER_THREADS: int = 4                  # Worker thread affinity
PARTIAL_WINDOW_S: float = 1.5             # 1.5-second sliding recognition window
SAMPLE_RATE: int = 16000                  # Native 16 kHz sample rate
BUFFER_MAX_CHUNKS: int = 100              # Maximum queued chunks before dropping

_LOGGER = logging.getLogger("core.speech.whisper_shadow")


@dataclasses.dataclass
class WhisperPartial:
    """A speculative or finalized partial transcript emitted by Shadow Whisper."""

    text: str
    is_final: bool
    confidence: float
    timestamp: float


class ShadowWhisperWorker:
    """Off-thread speculative ASR observer processing background audio frames."""

    def __init__(
        self,
        model_name: str = WHISPER_MODEL_NAME,
        on_partial: Optional[Callable[[WhisperPartial], None]] = None,
        window_s: float = PARTIAL_WINDOW_S,
    ) -> None:
        self.model_name = model_name
        self.on_partial = on_partial
        self.window_s = window_s

        self._queue: queue.Queue[bytes] = queue.Queue(maxsize=BUFFER_MAX_CHUNKS)
        self._running = False
        self._thread: Optional[threading.Thread] = None

        self._model = None
        self._model_failed = False
        self._lock = threading.Lock()

        self._window_samples = int(SAMPLE_RATE * window_s)
        self._audio_buffer = bytearray()
        self._sub_token: Optional[int] = None

    def _ensure_model(self) -> bool:
        if self._model is not None:
            return True
        if self._model_failed:
            return False

        with self._lock:
            if self._model is not None:
                return True
            if self._model_failed:
                return False

            try:
                from faster_whisper import WhisperModel
                self._model = WhisperModel(
                    self.model_name,
                    device=WHISPER_DEVICE,
                    compute_type=WHISPER_COMPUTE_TYPE,
                    cpu_threads=WHISPER_THREADS,
                )
                _LOGGER.info(
                    "ShadowWhisperWorker initialized model '%s' (compute=%s)",
                    self.model_name,
                    WHISPER_COMPUTE_TYPE,
                )
                return True
            except Exception as exc:
                _LOGGER.warning("Could not initialize faster-whisper: %s (fail-open)", exc)
                self._model_failed = True
                return False

    def feed_chunk(self, data: Union[bytes, np.ndarray]) -> None:
        """Feed an audio chunk into the internal processing queue."""
        if not self._running:
            return
        raw_bytes = data.tobytes() if isinstance(data, np.ndarray) else data
        try:
            self._queue.put_nowait(raw_bytes)
        except queue.Full:
            # Drop frame rather than blocking caller
            pass

    def start(self) -> None:
        """Start the shadow worker thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(
                target=self._worker_loop,
                name="whisper-shadow",
                daemon=True,
            )
            self._thread.start()
            _LOGGER.info("ShadowWhisperWorker thread started")

    def stop(self) -> None:
        """Stop the shadow worker thread."""
        with self._lock:
            if not self._running:
                return
            self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
            self._thread = None
        _LOGGER.info("ShadowWhisperWorker stopped")

    def _worker_loop(self) -> None:
        target_bytes = self._window_samples * 2

        while self._running:
            try:
                chunk = self._queue.get(timeout=0.1)
                self._audio_buffer.extend(chunk)
            except queue.Empty:
                continue

            if len(self._audio_buffer) < target_bytes:
                continue

            # Take current window
            window_bytes = bytes(self._audio_buffer[:target_bytes])
            del self._audio_buffer[:target_bytes // 2]  # 50% overlap

            if not self._ensure_model():
                # Fail-open: drain buffer and continue
                continue

            # Convert to float32
            pcm_arr = np.frombuffer(window_bytes, dtype=np.int16)
            float_arr = pcm_arr.astype(np.float32) / 32768.0

            # Quick energy filter: avoid running inference on total silence
            rms = float(np.sqrt(np.mean(float_arr * float_arr)))
            if rms < 0.015:
                continue

            try:
                segments, info = self._model.transcribe(
                    float_arr,
                    beam_size=1,
                    language="en",
                    vad_filter=False,
                )
                text_parts = [s.text.strip() for s in segments if s.text.strip()]
                if text_parts:
                    full_text = " ".join(text_parts)
                    partial = WhisperPartial(
                        text=full_text,
                        is_final=False,
                        confidence=0.85,
                        timestamp=time.monotonic(),
                    )
                    _LOGGER.debug("[SHADOW] Speculated text: '%s'", full_text)
                    if self.on_partial:
                        try:
                            self.on_partial(partial)
                        except Exception as exc:
                            _LOGGER.error("Error in on_partial callback: %s", exc)
            except Exception as exc:
                _LOGGER.debug("Transcription step error: %s", exc)
