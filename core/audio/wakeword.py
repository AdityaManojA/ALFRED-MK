"""
core/audio/wakeword.py — Wake-word gate adapter and latency-instrumented detector.

Prompt Requirements:
- Entry/exit timestamps at key points:
  1. Audio buffer filled → wake word detector called
  2. Wake word match → listening mode starts
- Model lazy-loaded once at boot, not repeatedly on demand.
- Named constants at top of file: WAKEWORD_MODEL_PATH, AUDIO_BUFFER_SIZE, WAKEWORD_TIMEOUT_S.
"""

from __future__ import annotations

import logging
from pathlib import Path

from core.wake_word import (
    WakeWordDetector,
    WAKEWORD_MODEL_PATH,
    AUDIO_BUFFER_SIZE,
    WAKEWORD_TIMEOUT_S,
    DEFAULT_THRESHOLD,
    SAMPLE_RATE,
    WAKE_PHRASE,
    WAKE_MODEL,
    WAKE_MODEL_PATH,
    get_shared_model,
    get_detector,
    is_ready,
    is_installed,
    install_and_download,
)

logger = logging.getLogger("core.audio.wakeword")

__all__ = [
    "WakeWordDetector",
    "WAKEWORD_MODEL_PATH",
    "AUDIO_BUFFER_SIZE",
    "WAKEWORD_TIMEOUT_S",
    "DEFAULT_THRESHOLD",
    "SAMPLE_RATE",
    "WAKE_PHRASE",
    "WAKE_MODEL",
    "WAKE_MODEL_PATH",
    "get_shared_model",
    "is_ready",
    "is_installed",
    "install_and_download",
]
