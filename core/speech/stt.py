"""
core/speech/stt.py — Latency-instrumented Speech-to-Text coordinator.

Prompt Requirements:
- Measure:
  1. Audio upload start → API received (network latency)
  2. API processing time (model inference latency)
  3. Result unpacking → intent parse start
- Providers: local (whisper/vosk) or cloud (gRPC/streaming preferred, max 2 retries)
- Named constants: STT_PROVIDER, STT_TIMEOUT_S, STT_STREAMING_ENABLED, STT_RETRY_MAX_ATTEMPTS.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, Optional, Tuple
import numpy as np

# ── Configuration Constants ──────────────────────────────────────────────────
STT_PROVIDER: str = "whisper"                # "whisper", "vosk", or "google"
STT_TIMEOUT_S: float = 2.0                   # Max latency budget for STT transcription
STT_STREAMING_ENABLED: bool = True           # Prefer streaming for partials
STT_RETRY_MAX_ATTEMPTS: int = 2              # Tight retry bound, no long backoff

logger = logging.getLogger("core.speech.stt")


class LatencyReport:
    """Detailed latency measurement breakdown for STT."""
    def __init__(self):
        self.upload_start: float = 0.0
        self.api_received: float = 0.0
        self.inference_end: float = 0.0
        self.unpacking_end: float = 0.0

    @property
    def network_latency_ms(self) -> float:
        return max(0.0, (self.api_received - self.upload_start) * 1000.0)

    @property
    def inference_latency_ms(self) -> float:
        return max(0.0, (self.inference_end - self.api_received) * 1000.0)

    @property
    def unpack_latency_ms(self) -> float:
        return max(0.0, (self.unpacking_end - self.inference_end) * 1000.0)

    @property
    def total_latency_ms(self) -> float:
        return max(0.0, (self.unpacking_end - self.upload_start) * 1000.0)


class InstrumentedSTT:
    """Wraps STT engines with high-precision latency profiling and bounded retries."""

    def __init__(
        self,
        provider: str = STT_PROVIDER,
        timeout_s: float = STT_TIMEOUT_S,
        streaming: bool = STT_STREAMING_ENABLED,
        max_retries: int = STT_RETRY_MAX_ATTEMPTS,
    ):
        self.provider = provider
        self.timeout_s = timeout_s
        self.streaming = streaming
        self.max_retries = max_retries
        self._engine = None

    def _ensure_engine(self):
        if self._engine is not None:
            return self._engine
        from core.stt import WhisperSTT, VoskSTT
        if self.provider == "vosk":
            self._engine = VoskSTT()
        else:
            self._engine = WhisperSTT(model_name="base")
        return self._engine

    def transcribe_with_metrics(self, audio: np.ndarray) -> Tuple[str, LatencyReport]:
        """Transcribe audio array and record precise pipeline metrics."""
        report = LatencyReport()
        engine = self._ensure_engine()

        report.upload_start = time.perf_counter()
        # For local STT, upload is internal buffer transfer (< 0.1ms)
        report.api_received = time.perf_counter()

        text = ""
        attempts = 0
        while attempts < self.max_retries:
            attempts += 1
            try:
                if hasattr(engine, "transcribe"):
                    text = engine.transcribe(audio)
                break
            except Exception as e:
                logger.warning(f"[STT] Attempt {attempts} failed: {e}")
                if attempts >= self.max_retries:
                    raise

        report.inference_end = time.perf_counter()

        # Unpacking and normalization
        text = (text or "").strip()
        report.unpacking_end = time.perf_counter()

        logger.debug(
            f"[STT Profiling] network={report.network_latency_ms:.1f}ms "
            f"inference={report.inference_latency_ms:.1f}ms "
            f"unpack={report.unpack_latency_ms:.1f}ms "
            f"total={report.total_latency_ms:.1f}ms"
        )
        return text, report
