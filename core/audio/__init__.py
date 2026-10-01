"""core/audio/__init__.py — Audio subsystem package.

Exports AudioGate, SharedAudioStream, DualWakeWordDetector, and VoiceActivityDetector.
"""

from __future__ import annotations

from core.audio.gate import (
    AudioGate,
    GATE_AUTOMATION,
    GATE_MEDIA,
    GATE_RELEASE_DELAY_MS,
    GATE_RESOLVING,
    GATE_TTS,
    get_audio_gate,
)
from core.audio.stream import (
    CHUNK_SAMPLES,
    MAX_SUBSCRIBERS,
    PREROLL_S,
    SAMPLE_RATE,
    STREAM_LATENCY,
    SharedAudioStream,
    get_shared_audio_stream,
)
from core.audio.vad import (
    VAD_SAMPLE_RATE,
    VAD_SILENCE_TIMEOUT_MS,
    VAD_THRESHOLD,
    VAD_WINDOW_SAMPLES,
    VoiceActivityDetector,
)
from core.audio.wakeword_tiny import (
    DualWakeWordDetector,
    WakeDetectionResult,
    WAKEWORD_CONFIDENCE_BARE,
    WAKEWORD_CONFIDENCE_HEY,
)

__all__ = [
    "AudioGate",
    "get_audio_gate",
    "GATE_TTS",
    "GATE_MEDIA",
    "GATE_AUTOMATION",
    "GATE_RESOLVING",
    "GATE_RELEASE_DELAY_MS",
    "SharedAudioStream",
    "get_shared_audio_stream",
    "DualWakeWordDetector",
    "WakeDetectionResult",
    "WAKEWORD_CONFIDENCE_HEY",
    "WAKEWORD_CONFIDENCE_BARE",
    "VoiceActivityDetector",
    "VAD_SAMPLE_RATE",
    "VAD_WINDOW_SAMPLES",
    "VAD_THRESHOLD",
    "VAD_SILENCE_TIMEOUT_MS",
    "SAMPLE_RATE",
    "CHUNK_SAMPLES",
    "PREROLL_S",
    "MAX_SUBSCRIBERS",
    "STREAM_LATENCY",
]
