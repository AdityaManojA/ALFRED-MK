"""
ALFRED Text-to-Speech package.
Provides pluggable TTSEngine interface with default (EdgeTTS/Kokoro/ElevenLabs)
and Jarvis (VoxCPM2 LoRA) backends.
"""
from __future__ import annotations

from core.tts.engine_base import Capability, TTSEngine
from core.tts.engine_default import (
    EdgeTTSEngine,
    KokoroTTSEngine,
    ElevenLabsTTSEngine,
    TTSPlayer,
    EngineDefault,
    create_tts_player,
    _to_numpy,
    _compress_silence,
    _play_np,
    _play_audio_bytes,
)

from core.tts.capability import check_jarvis_capability, check_alfred_capability
from core.tts.jarvis_assets import are_assets_downloaded

__all__ = [
    "Capability",
    "TTSEngine",
    "EdgeTTSEngine",
    "KokoroTTSEngine",
    "ElevenLabsTTSEngine",
    "TTSPlayer",
    "EngineDefault",
    "create_tts_player",
    "get_engine",
    "check_jarvis_capability",
    "check_alfred_capability",
    "are_assets_downloaded",
    "_to_numpy",
    "_compress_silence",
    "_play_np",
    "_play_audio_bytes",
]


def get_engine(name: str = "default", config: dict | None = None) -> TTSEngine:
    """Factory to retrieve a configured TTSEngine instance."""
    clean_name = (name or "default").strip().lower()
    if clean_name in ("jarvis", "alfred"):
        try:
            from core.tts.engine_jarvis import EngineJarvis
            return EngineJarvis(config=config)
        except Exception as e:
            print(f"[TTS] Failed to instantiate Alfred/Jarvis engine: {e} — falling back to default.")
            return EngineDefault(config=config)
    return EngineDefault(config=config)
