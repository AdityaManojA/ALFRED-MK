# ALFRED-MK-V: Cross-Platform Parity (macOS + Linux)
## Phase 4 Implementation Notes: TTS & STT Parity

**Corpus & Graph References:**
- `core/tts/engine_default.py` (`KokoroTTSEngine`, `EdgeTTSEngine`, `ElevenLabsTTSEngine`, `EngineDefault`)
- `core/local_stt.py` (`LocalSTTManager`)
- `core/platform/base.py` / `core/platform/mac.py` / `core/platform/linux.py`

---

## 1. Speech-to-Text (STT)

- **Engine:** `sounddevice` handles cross-platform audio input buffering.
- **PortAudio Wheels:** PyPI pre-builds binaries for macOS (x86_64 + arm64) and Linux (x86_64).
- **Vosk / Whisper:** Batch and streaming inference execute purely in Python/C++ binaries without Win32 hooks.

---

## 2. Text-to-Speech (TTS)

- **EdgeTTS & ElevenLabs:** Operate over standard HTTPS connections.
- **Kokoro Neural TTS:** Runs offline via ONNX/PyTorch on all platforms.
- **Native OS Fallbacks (via `core/platform/`):**
  - **macOS:** `say -v Daniel -r 175 "<text>"`
  - **Linux:** `espeak-ng "<text>"` or `piper`
  - **Windows:** SAPI speech synthesizer

---

## 3. Audio Ducking Parity

- Dynamic volume reduction during ALFRED vocal synthesis is applied symmetrically:
  - **Windows:** WASAPI endpoint ducking via `pycaw`.
  - **macOS:** AppleScript volume adjustments.
  - **Linux:** PulseAudio / PipeWire `pactl set-sink-volume` controls.
