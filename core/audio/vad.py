"""core/audio/vad.py — Voice Activity Detection (VAD) module.

Guarantees & Invariants:
- 16 kHz mono audio processing in 512-sample (32 ms) windows.
- Dual-mode detector: uses Silero VAD ONNX model with seamless acoustic energy fallback.
- Detects speech onset, active speech probability, and trailing silence duration.
- Fail-open: never raises exceptions or blocks the real-time audio pipeline.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from typing import Optional, Union

import numpy as np

# ── VAD Constants ────────────────────────────────────────────────────────────
VAD_SAMPLE_RATE: int = 16000             # Native 16 kHz sample rate
VAD_WINDOW_SAMPLES: int = 512            # 32 ms window size (native for Silero VAD)
VAD_THRESHOLD: float = 0.50              # Default activation confidence threshold
VAD_SILENCE_TIMEOUT_MS: int = 600        # Silence duration to consider speech ended
ENERGY_FLOOR_RMS: float = 0.015          # Acoustic RMS energy floor for fallback

_LOGGER = logging.getLogger("core.audio.vad")


class VoiceActivityDetector:
    """Thread-safe Voice Activity Detector with neural Silero VAD and energy fallback."""

    def __init__(
        self,
        sample_rate: int = VAD_SAMPLE_RATE,
        threshold: float = VAD_THRESHOLD,
        silence_timeout_ms: int = VAD_SILENCE_TIMEOUT_MS,
    ) -> None:
        self.sample_rate = sample_rate
        self.threshold = threshold
        self.silence_timeout_s = silence_timeout_ms / 1000.0

        self._model = None
        self._model_failed = False
        self._lock = threading.Lock()

        self._in_speech = False
        self._last_speech_time = 0.0
        self._speech_start_time = 0.0

    def _ensure_model(self) -> None:
        if self._model is not None or self._model_failed:
            return
        with self._lock:
            if self._model is not None or self._model_failed:
                return
            try:
                import torch
                # Silero VAD loads via torch or silero_vad package
                try:
                    import silero_vad
                    self._model = silero_vad.load_silero_vad(onnx=True)
                    _LOGGER.info("VoiceActivityDetector loaded Silero VAD (ONNX)")
                except Exception:
                    # Alternative torch hub loader
                    model, _ = torch.hub.load(
                        repo_or_dir="snakers4/silero-vad",
                        model="silero_vad",
                        onnx=True,
                        trust_repo=True,
                    )
                    self._model = model
                    _LOGGER.info("VoiceActivityDetector loaded Silero VAD from torch.hub")
            except Exception as exc:
                _LOGGER.info("Silero VAD unavailable (%s) — using acoustic energy VAD", exc)
                self._model_failed = True

    def reset(self) -> None:
        """Reset internal speech tracking and model states."""
        with self._lock:
            self._in_speech = False
            self._last_speech_time = 0.0
            self._speech_start_time = 0.0
            if self._model is not None and hasattr(self._model, "reset_states"):
                try:
                    self._model.reset_states()
                except Exception:
                    pass

    def speech_probability(self, pcm_chunk: Union[bytes, np.ndarray]) -> float:
        """Compute the probability of speech (0.0 to 1.0) in the audio chunk."""
        if isinstance(pcm_chunk, bytes):
            pcm_arr = np.frombuffer(pcm_chunk, dtype=np.int16)
        else:
            pcm_arr = pcm_chunk

        if len(pcm_arr) == 0:
            return 0.0

        # Float32 normalized to [-1.0, 1.0]
        float_data = pcm_arr.astype(np.float32) / 32768.0

        self._ensure_model()

        if self._model is not None:
            try:
                import torch
                tensor = torch.from_numpy(float_data)
                if len(tensor.shape) == 1:
                    tensor = tensor.unsqueeze(0)
                with torch.no_grad():
                    prob = float(self._model(tensor, self.sample_rate).item())
                    return max(0.0, min(1.0, prob))
            except Exception:
                pass

        # Energy fallback
        rms = float(np.sqrt(np.mean(float_data * float_data)))
        if rms < ENERGY_FLOOR_RMS:
            return 0.0
        # Map [ENERGY_FLOOR_RMS, 0.25] to [0.0, 1.0]
        score = (rms - ENERGY_FLOOR_RMS) / (0.25 - ENERGY_FLOOR_RMS)
        return max(0.0, min(1.0, score))

    def process_chunk(self, pcm_chunk: Union[bytes, np.ndarray]) -> dict:
        """Process an audio chunk and update speech state.

        Returns dict with:
            - is_speech: bool
            - probability: float
            - speech_started: bool
            - speech_ended: bool
        """
        prob = self.speech_probability(pcm_chunk)
        now = time.monotonic()
        is_speech = prob >= self.threshold

        speech_started = False
        speech_ended = False

        with self._lock:
            if is_speech:
                if not self._in_speech:
                    self._in_speech = True
                    self._speech_start_time = now
                    speech_started = True
                self._last_speech_time = now
            else:
                if self._in_speech:
                    if (now - self._last_speech_time) >= self.silence_timeout_s:
                        self._in_speech = False
                        speech_ended = True

        return {
            "is_speech": is_speech,
            "probability": prob,
            "speech_started": speech_started,
            "speech_ended": speech_ended,
            "in_speech": self._in_speech,
        }
