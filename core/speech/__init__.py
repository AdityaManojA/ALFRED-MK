"""core/speech/__init__.py — Speech subsystem package.

Exports ShadowWhisperWorker, WhisperPartial, and speech constants.
"""

from __future__ import annotations

from core.speech.whisper_shadow import (
    PARTIAL_WINDOW_S,
    SAMPLE_RATE,
    WHISPER_COMPUTE_TYPE,
    WHISPER_DEVICE,
    WHISPER_MODEL_NAME,
    WHISPER_THREADS,
    ShadowWhisperWorker,
    WhisperPartial,
)

__all__ = [
    "ShadowWhisperWorker",
    "WhisperPartial",
    "WHISPER_MODEL_NAME",
    "WHISPER_COMPUTE_TYPE",
    "WHISPER_DEVICE",
    "WHISPER_THREADS",
    "PARTIAL_WINDOW_S",
    "SAMPLE_RATE",
]
