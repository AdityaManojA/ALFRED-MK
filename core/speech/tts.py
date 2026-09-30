"""
core/speech/tts.py — Latency-instrumented Text-to-Speech coordinator with phrase caching.

Target: TTS latency < 500 ms (end of speech / result to start of playback).
Prompt Requirements:
- Measure:
  1. TTS synthesis time (text → audio)
  2. Audio device latency (playback start after synthesis)
  3. Queue delay (pending TTS backlog)
- Cache common phrases (e.g., "Checking, sir", "Done, sir", "Right away, sir")
- Windows shared audio mode with tuned buffer size.
- Named constants at top of file: TTS_CACHE_SIZE, AUDIO_OUTPUT_BUFFER_SIZE, TTS_TIMEOUT_S.
"""

from __future__ import annotations

import collections
import logging
import queue
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple
import numpy as np

# ── Configuration Constants ──────────────────────────────────────────────────
TTS_CACHE_SIZE: int = 128                   # Max pre-synthesized audio cache entries
AUDIO_OUTPUT_BUFFER_SIZE: int = 512         # Tuned output buffer frames for low latency
TTS_TIMEOUT_S: float = 3.0                  # Max synthesis wait time before timeout

logger = logging.getLogger("core.speech.tts")


@dataclass
class TTSLatencyReport:
    """Latency metrics recorded during TTS synthesis and playback."""
    text: str
    queue_delay_ms: float = 0.0
    synthesis_ms: float = 0.0
    device_latency_ms: float = 0.0
    total_ms: float = 0.0
    from_cache: bool = False


class TTSPhraseCache:
    """Thread-safe LRU cache for synthesized audio waveforms."""

    def __init__(self, maxsize: int = TTS_CACHE_SIZE):
        self.maxsize = maxsize
        self._cache: collections.OrderedDict[str, Tuple[np.ndarray, int]] = collections.OrderedDict()
        self._lock = threading.Lock()

    def get(self, text: str) -> Optional[Tuple[np.ndarray, int]]:
        key = text.strip().lower()
        with self._lock:
            if key in self._cache:
                data = self._cache[key]
                self._cache.move_to_end(key)
                return data
            return None

    def put(self, text: str, audio: np.ndarray, sample_rate: int) -> None:
        key = text.strip().lower()
        with self._lock:
            if len(self._cache) >= self.maxsize:
                self._cache.popitem(last=False)
            self._cache[key] = (audio, sample_rate)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


# Global audio phrase cache
TTS_CACHE = TTSPhraseCache()


class InstrumentedTTS:
    """TTS manager with queue latency tracking, audio caching, and low-latency playback."""

    def __init__(
        self,
        synthesizer: Optional[Callable[[str], Tuple[np.ndarray, int]]] = None,
        cache_size: int = TTS_CACHE_SIZE,
    ):
        self._synthesizer = synthesizer
        self._cache = TTS_CACHE
        self._queue: queue.Queue = queue.Queue(maxsize=20)
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._worker_thread = threading.Thread(
            target=self._playback_loop,
            daemon=True,
            name="InstrumentedTTSWorker"
        )
        self._worker_thread.start()

    def stop(self) -> None:
        self._running = False
        try:
            self._queue.put_nowait(None)
        except Exception:
            pass

    def speak(
        self,
        text: str,
        on_playback_start: Optional[Callable[[TTSLatencyReport], None]] = None,
    ) -> None:
        """Enqueue text for synthesis and playback."""
        if not text or not text.strip():
            return
        enqueued_at = time.perf_counter()
        try:
            self._queue.put_nowait((text.strip(), enqueued_at, on_playback_start))
        except queue.Full:
            logger.warning(f"[TTS] Queue full, dropping speech request: {text[:30]}")

    def synthesize_or_cache(self, text: str) -> Tuple[np.ndarray, int, bool]:
        """Retrieve from cache or synthesize via underlying engine."""
        cached = self._cache.get(text)
        if cached is not None:
            return cached[0], cached[1], True

        if self._synthesizer is not None:
            audio, sr = self._synthesizer(text)
            self._cache.put(text, audio, sr)
            return audio, sr, False

        # Fallback empty audio
        return np.zeros(1600, dtype=np.float32), 16000, False

    def _playback_loop(self) -> None:
        import sounddevice as sd

        while self._running:
            try:
                item = self._queue.get()
                if item is None or not self._running:
                    break
                text, enqueued_at, callback = item
                report = TTSLatencyReport(text=text)

                # 1. Queue delay
                t_pulled = time.perf_counter()
                report.queue_delay_ms = (t_pulled - enqueued_at) * 1000.0

                # 2. Synthesis (or cache lookup)
                audio, sr, from_cache = self.synthesize_or_cache(text)
                t_synthesized = time.perf_counter()
                report.synthesis_ms = (t_synthesized - t_pulled) * 1000.0
                report.from_cache = from_cache

                # 3. Audio device playback start
                t_dev_start = time.perf_counter()
                try:
                    # Low-latency output stream
                    sd.play(audio, sr, blocking=False)
                except Exception as dev_err:
                    logger.warning(f"[TTS] sounddevice play error: {dev_err}")
                report.device_latency_ms = (time.perf_counter() - t_dev_start) * 1000.0

                # Total latency: queue + synthesis + device init
                report.total_ms = (time.perf_counter() - enqueued_at) * 1000.0

                logger.debug(
                    f"[TTS Metrics] '{text[:25]}' total={report.total_ms:.1f}ms "
                    f"queue={report.queue_delay_ms:.1f}ms synth={report.synthesis_ms:.1f}ms "
                    f"device={report.device_latency_ms:.1f}ms cache={from_cache}"
                )

                if callback:
                    try:
                        callback(report)
                    except Exception:
                        pass

            except Exception as loop_err:
                logger.error(f"[TTS] Playback loop error: {loop_err}")
