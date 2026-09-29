# ALFRED-MK-V — Jarvis Voice Option: Phase 0 Reconnaissance Notes

**Date:** 2026-09-29  
**Branch / Workspace:** ALFRED-MK-V  
**Knowledge Graph Nodes Referenced:**  
- `core_tts_edgettsengine` (`core/tts.py`)
- `core_tts_kokorottsengine` (`core/tts.py`)
- `core_tts_elevenlabsttsengine` (`core/tts.py`)
- `core_tts_ttsplayer` (`core/tts.py`)
- `core_tts_create_tts_player` (`core/tts.py`)
- `core_local_ttt_localttsmanager` (`core/local_ttt.py`)
- `core_local_ttt_localttsmanager_speak_loop` (`core/local_ttt.py`)
- `core_local_pipeline_localpipelinecoordinator` (`core/local_pipeline.py`)
- `ui_customizeoverlay` (`ui.py`)
- `ui_mainwindow` (`ui.py`, `main.py`)
- `memory_config_manager` (`memory/config_manager.py`)

---

## 1. Current Spoken Line Flow & Entry Points

- **Primary Abstraction:** Spoken text flows through `TTSPlayer.speak(text, on_start, on_done)` located in `core/tts.py`. `TTSPlayer` wraps an underlying engine (`EdgeTTSEngine`, `KokoroTTSEngine`, or `ElevenLabsTTSEngine`) and delegates synchronously to `self._engine.speak(text)`.
- **Queued Pipeline:** In local audio pipeline mode, `LocalTTSManager` (`core/local_ttt.py`) encapsulates `TTSPlayer`. It exposes `speak_text(text)` and `speak_sentence(sentence)` which append text chunks into a `queue.Queue` (`self.text_queue`). A dedicated background worker thread (`self.speak_thread` running `_speak_loop`) pops items from `self.text_queue` and invokes `self.tts_player.speak(text)`.
- **Callers:**
  - `LocalPipelineCoordinator._handle_tts_flow()` (`core/local_pipeline.py`)
  - Sentry mode callouts (`speak_fn` dispatch)
  - `main.py` tactical announcements and feedback
- **Caching:** Currently, **zero** audio-file caching exists in the codebase. Every utterance is synthesized and streamed on demand.

## 2. TTS Abstraction & Engine Interface Status

- Currently, engines are purely **duck-typed**:
  - `EdgeTTSEngine.speak(text: str) -> None`
  - `KokoroTTSEngine.speak(text: str) -> None`
  - `ElevenLabsTTSEngine.speak(text: str) -> None`
- There is no formal `TTSEngine` abstract base class or unified return type (such as `(pcm, sample_rate)`).
- **Invasiveness Assessment:** Very low. Because all engines are constructed via `create_tts_player(config)` in `core/tts.py`, we can introduce `core/tts/engine_base.py` (`TTSEngine` ABC) and wrap existing engines inside `core/tts/engine_default.py` without modifying any downstream call sites.

## 3. Voice Settings, Schema & UI Persistence

- **Storage File:** `config/api_keys.json` (persisted and reloaded via `memory/config_manager.py`).
- **Existing Schema:**
  - `"tts_engine"`: `"edgetts"`, `"kokoro"`, `"elevenlabs"`
  - `"tts_voice"`: string identifier (e.g. `"en-US-GuyNeural"`, `"af_heart"`)
  - `"tts_speed"`: float
- **Persistence Pattern:** `_patch_config(patch: dict)` protected by `_CONFIG_LOCK`. Configuration changes are thread-safe and atomic.
- **UI Location:** `CustomizeOverlay` in `ui.py` (lines ~5556–5576). It presents radio/dropdown choices and speed sliders.
- **Runtime Application:** `MainWindow._apply_name_update` invokes `config_manager.save_voice(...)` and triggers the live pipeline's voice reload callback.

## 4. Audio Output Path & Sample Rate Expectations

- **Playback Library:** `sounddevice` (`sd.play()`, `sd.wait()`).
- **Formats Handled Today:**
  - Float32 mono/stereo NumPy arrays (via `_play_np(samples, sample_rate)` in `core/tts.py`, used by Kokoro at 24 kHz).
  - MP3/WAV/OGG bytes (via `_play_audio_bytes(audio_bytes)` decoded by `miniaudio` into float32, used by EdgeTTS and ElevenLabs).
- **48 kHz Float PCM Support:** `sounddevice.play()` on Windows (DirectSound/MME/WASAPI), Linux (PulseAudio/ALSA), and macOS (CoreAudio) natively accepts 48 kHz float32 PCM without requiring explicit software resampling. If a backend device requires a different rate, sounddevice or OS audio engines handle rate adaptation transparently.

## 5. Hardware / Environment Detection

- **CUDA / GPU:** Existing code in `core/tts.py` (lines 245–261) detects CUDA via `torch.cuda.is_available()`.
- **VRAM Detection:** Can be queried via `torch.cuda.get_device_properties(0).total_memory / (1024**3)` in gigabytes.
- **Python Version:** VoxCPM2 requires Python `>= 3.10` and `< 3.13`. Runtime detection via `sys.version_info` will gate this.
- **Capability States:**
  - `OK`
  - `MISSING_DEPS` (missing `voxcpm`, `torch`, `soundfile`, or `huggingface_hub`)
  - `NO_CUDA` / `CPU_ONLY` (distinct state; CPU execution permitted only if explicitly enabled)
  - `LOW_VRAM` (< 8 GB VRAM)
  - `PYTHON_VERSION` (unsupported Python runtime)
  - `NOT_DOWNLOADED` (weights or reference audio absent)

## 6. Pipeline Threading Model

- Spoken audio synthesis is executed off the main Qt UI thread:
  - `LocalTTSManager` consumes requests on `self.speak_thread`.
  - Kokoro internally spawns an asynchronous `_synth()` thread feeding an `audio_q` while the caller thread feeds `sd.play()`.
- **Jarvis Synthesis Worker:** `EngineJarvis` will employ a dedicated worker thread with an internal task queue. Model warm-up, synthesis, sentence chunking, and playback dispatch run entirely off the GUI event loop. No Qt timers or UI-thread blocking operations will be introduced.

## 7. Cache Keying & Fallback Rules

- An utterance cache will be introduced for fixed canned lines (e.g. system acknowledgments, confirmations).
- **Cache Key Schema:** `(engine_name: str, normalized_text: str)`.
  - Jarvis utterances are cached under `("jarvis", text)`.
  - Default utterances are cached under `("default", text)`.
  - If Jarvis fails and falls back to the default engine, the synthesized utterance is tagged and cached under `("default", text)`. Jarvis and default engine entries will never collide or poison each other.
- **Sentry v2 Privacy Guarantee:** Any utterance containing drift-callout dynamic labels (such as `{label}` or Sentry target identifiers) will **NEVER** be cached.

---

## Proposed Architecture for `core/tts/`

We will modularize `core/tts.py` into a clean package structure under `core/tts/`:

```
core/tts/
├── __init__.py           # Backwards-compatible exports (TTSPlayer, create_tts_player, etc.)
├── engine_base.py        # TTSEngine ABC, Capability enum, AudioChunk data structure
├── engine_default.py     # Default engines: EdgeTTS, Kokoro, ElevenLabs wrapped behind TTSEngine
├── capability.py         # Hardware, CUDA, VRAM, Python version, and dependency inspector
├── jarvis_assets.py      # HuggingFace snapshot downloader & integrity verifier
└── engine_jarvis.py      # VoxCPM2 LoRA synthesis engine, sentence chunker, queue, fallback logic
```

`core/tts/__init__.py` will re-export all legacy symbols so that existing imports throughout `core/` and `main.py` remain 100% unbroken.
