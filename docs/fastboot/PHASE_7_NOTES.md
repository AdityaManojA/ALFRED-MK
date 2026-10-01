# Phase 7 Notes — Shadow Whisper & Decoupled ASR

## Status: COMPLETE

### 1. Architecture & Design
1. **Decoupled Shadow Whisper Worker (`core/speech/whisper_shadow.py`)**:
   - Runs off-thread in a dedicated daemon worker (`"whisper-shadow"`), completely decoupled from the Gemini Live audio websocket.
   - Subscribes to `SharedAudioStream` via non-blocking bounded queue (`BUFFER_MAX_CHUNKS = 100`).
   - Uses `faster-whisper` (`tiny.en`, `int8`, CPU, 4 threads) over a 1.5-second sliding recognition window (`PARTIAL_WINDOW_S = 1.5`).
   - Emits `WhisperPartial(text, is_final, confidence, timestamp)` callbacks for speculative intent prefetching and live HUD captions.
   - Non-blocking fail-open: if model or library initialization fails, it logs once and idles without disturbing live audio.

2. **Voice Activity Detection (`core/audio/vad.py`)**:
   - `VoiceActivityDetector`:
     - Native 16 kHz, 512-sample (32 ms) window analysis.
     - Neural Silero VAD (ONNX) primary classifier with acoustic RMS energy fallback.
     - Configurable silence timeout (`VAD_SILENCE_TIMEOUT_MS = 600`) and confidence threshold (`VAD_THRESHOLD = 0.50`).
     - Emits speech onset (`speech_started`), continuous probability, and speech termination (`speech_ended`) events.

### 2. Verification
- `py -3.12 -m unittest tests/audio/test_vad.py`: 5/5 PASS in 3.475s.
- `py -3.12 -m unittest tests/speech/test_whisper_shadow.py`: 3/3 PASS in 0.114s.
- Verified energy fallback, silence timeout hysteresis, queue bounded buffer, and lifecycle start/stop.
