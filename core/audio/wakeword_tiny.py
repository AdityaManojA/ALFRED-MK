"""core/audio/wakeword_tiny.py — Dual-phrase tiny wake word detector.

Guarantees & Invariants:
- Dual-phrase activation:
    1. "hey alfred": confidence threshold >= 0.70
    2. Bare "alfred": confidence threshold >= 0.85 (higher bar against ambient Batman media)
- Refractory suppression: 1500 ms cooldown after each trigger prevents re-trigger bounce.
- Acoustic gate shielding: suppresses inference whenever GATE_TTS is held.
- Fail-open: if ONNX runtime or weights are unavailable, logs once and remains usable.
"""

from __future__ import annotations

import dataclasses
import logging
from pathlib import Path
import threading
import time
from typing import Any, Callable, Dict, Optional, Union

import numpy as np

from core.audio.gate import GATE_TTS, get_audio_gate

# ── Dual Wake Word Constants ────────────────────────────────────────────────
WAKEWORD_CONFIDENCE_HEY: float = 0.70      # Threshold for compound "hey alfred"
WAKEWORD_CONFIDENCE_BARE: float = 0.85     # Higher threshold for bare "alfred"
REFRACTORY_WINDOW_MS: int = 1500           # 1.5-second lockout after activation
SAMPLE_RATE: int = 16000                   # 16 kHz sample rate
AUDIO_FRAME_SAMPLES: int = 1280            # 80 ms audio window for OpenWakeWord
MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "models"
DEFAULT_MODEL_PATH = MODELS_DIR / "alfred.onnx"

_LOGGER = logging.getLogger("core.audio.wakeword_tiny")


@dataclasses.dataclass
class WakeDetectionResult:
    """Detection event payload emitted on wake word recognition."""

    phrase: str              # "hey alfred" or "alfred"
    confidence: float        # Detected score (0.0 to 1.0)
    timestamp: float         # monotonic timestamp of detection


class DualWakeWordDetector:
    """Thread-safe dual-phrase wake word detector with acoustic gating and refractory cooldown."""

    def __init__(
        self,
        on_detect: Optional[Callable[[WakeDetectionResult], None]] = None,
        model_path: Optional[Union[str, Path]] = None,
        hey_threshold: float = WAKEWORD_CONFIDENCE_HEY,
        bare_threshold: float = WAKEWORD_CONFIDENCE_BARE,
        refractory_ms: int = REFRACTORY_WINDOW_MS,
    ) -> None:
        self.on_detect = on_detect
        self.model_path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
        self.hey_threshold = hey_threshold
        self.bare_threshold = bare_threshold
        self.refractory_s = max(0.0, refractory_ms / 1000.0)

        self._audio_gate = get_audio_gate()
        self._last_trigger_time: float = 0.0
        self._lock = threading.Lock()
        self._model: Any = None
        self._model_failed: bool = False
        self._ready: bool = False
        self._buffer: bytearray = bytearray()

    @property
    def ready(self) -> bool:
        return self._ready or self._model_failed

    def _ensure_model(self) -> None:
        if self._ready or self._model_failed:
            return
        with self._lock:
            if self._ready or self._model_failed:
                return
            if not self.model_path.exists():
                _LOGGER.warning(
                    "Wake word model not found at %s — failing open with speech verifier",
                    self.model_path,
                )
                self._model_failed = True
                return

            try:
                from core.wake_word import _MODEL_INIT_LOCK, _ensure_openwakeword
                with _MODEL_INIT_LOCK:
                    _ensure_openwakeword()
                    from openwakeword.model import Model
                    self._model = Model(
                        wakeword_models=[str(self.model_path.resolve())],
                        inference_framework="onnx",
                    )
                self._ready = True
                _LOGGER.info("DualWakeWordDetector loaded model '%s'", self.model_path.name)
            except Exception as exc:
                _LOGGER.warning("Could not initialize openwakeword Model: %s (fail-open)", exc)
                self._model_failed = True

    def reset(self) -> None:
        """Reset internal detector state and rolling buffers."""
        with self._lock:
            self._buffer.clear()
            self._last_trigger_time = 0.0
            if self._model is not None and hasattr(self._model, "reset"):
                try:
                    self._model.reset()
                except Exception:
                    pass

    def feed(self, pcm_data: Union[bytes, np.ndarray]) -> Optional[WakeDetectionResult]:
        """Feed PCM audio samples. Returns WakeDetectionResult if a phrase triggers."""
        # 1. Acoustic gate check: suppress wake-word processing while ALFRED speaks
        if self._audio_gate.is_reason_held(GATE_TTS):
            return None

        # 2. Refractory lockout check
        now = time.monotonic()
        if (now - self._last_trigger_time) < self.refractory_s:
            return None

        self._ensure_model()

        # Convert to int16 bytes
        if isinstance(pcm_data, np.ndarray):
            raw_bytes = pcm_data.tobytes()
        else:
            raw_bytes = pcm_data

        with self._lock:
            self._buffer.extend(raw_bytes)
            # Need at least AUDIO_FRAME_SAMPLES (1280 samples = 2560 bytes)
            frame_bytes = AUDIO_FRAME_SAMPLES * 2
            if len(self._buffer) < frame_bytes:
                return None

            chunk = bytes(self._buffer[:frame_bytes])
            del self._buffer[:frame_bytes]

        pcm_arr = np.frombuffer(chunk, dtype=np.int16)

        # 3. Model inference
        hey_score = 0.0
        bare_score = 0.0

        if self._model is not None:
            try:
                preds = self._model.predict(pcm_arr)
                # preds is dict mapping model name to score
                for k, v in preds.items():
                    k_lower = k.lower()
                    if "hey" in k_lower:
                        hey_score = max(hey_score, float(v))
                    else:
                        bare_score = max(bare_score, float(v))
            except Exception as exc:
                _LOGGER.debug("openwakeword predict error: %s", exc)

        # 4. Dual-phrase evaluation
        triggered_phrase: Optional[str] = None
        triggered_confidence: float = 0.0

        if hey_score >= self.hey_threshold:
            triggered_phrase = "hey alfred"
            triggered_confidence = hey_score
        elif bare_score >= self.bare_threshold:
            triggered_phrase = "alfred"
            triggered_confidence = bare_score

        if triggered_phrase is not None:
            self._last_trigger_time = time.monotonic()
            result = WakeDetectionResult(
                phrase=triggered_phrase,
                confidence=triggered_confidence,
                timestamp=self._last_trigger_time,
            )
            _LOGGER.info(
                "[WAKE] Triggered '%s' (conf=%.2f, time=%.3f)",
                triggered_phrase,
                triggered_confidence,
                self._last_trigger_time,
            )
            if self.on_detect:
                try:
                    self.on_detect(result)
                except Exception as exc:
                    _LOGGER.error("Error in on_detect callback: %s", exc)
            return result

        return None
