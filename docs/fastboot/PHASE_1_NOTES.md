# Phase 1 Notes — Stop the Bleeding

## Status: COMPLETE

### 1. Root Cause Identification & Solved Items
1. **Windows Proactor Transport Exception Noise (WinError 10054)**:
   - Python's `asyncio.ProactorEventLoop` logs unhandled tracebacks to `sys.stderr` when an active IOCP pipe receives a remote TCP reset (`WINSOCK_CONNRESET = 10054`), even when the application cleanly catches socket errors during reconnection.
   - **Solution**: Implemented `core/net/loop_guard.py` with `install_transport_guard(loop)`. It wraps the exception handler to swallow known Windows socket teardown noise and monkeypatches `_ProactorBasePipeTransport._call_connection_lost` so that genuine reconnect sequences complete without console noise.

2. **Signed URL Leak & Console Flooding**:
   - `core/logger.py` was enhanced with `redact_signed_urls()` using regex pattern matching AWS S3, Google Cloud Storage, Cloudflare R2, Azure Blob, and signed CDN parameters, redacting signatures while preserving scheme and hostname.
   - Added `_is_ffmpeg_banner()` log filter and extended `QT_LOGGING_RULES` in `main.py` (`qt.multimedia=false;qt.multimedia.*=false;qt.multimedia.ffmpeg=false;qt.multimedia.ffmpeg.*=false;qt.tls.*=false;qt.multimedia.audio=false`) to eliminate FFmpeg AV1 hardware acceleration probing messages.

3. **Acoustic Self-Triggering & Additive Audio Gate**:
   - Discovered that `go_to_sleep` in `main.py` returned `"Going to sleep now, sir. Say 'Alfred' when you need me."` which Gemini TTS spoke directly into the room, causing the wake-word detector to self-trigger immediately.
   - Scrubbed prompt return in `main.py` to `"Going to sleep now, sir. Call me when you need me."`.
   - Created `core/audio/gate.py` containing `AudioGate`, an additive multi-reason acoustic shield:
     - `GATE_TTS`: Held during ALFRED speech playback.
     - `GATE_MEDIA`: Held during Visual HUD video playback and Tron score / Spotify music.
     - `GATE_AUTOMATION`: Held during automated OS keystrokes.
     - `GATE_RESOLVING`: Held during yt-dlp media resolution.
     - 250 ms release delay tail (`GATE_RELEASE_DELAY_MS`) to allow room reverberation and soundcard DAC buffers to dissipate.
   - In `main.py`:
     - Asleep wake detector explicitly checks `self._audio_gate.is_reason_held(GATE_TTS)`: wake detector is suppressed during TTS speech to prevent feedback, but stays receptive during media playback so the user can say "hey alfred, pause".
     - Awake mic streaming is gated on `self._audio_gate.is_open()`.
   - In `core/hud_video/controller.py`: wired `_set_state` to hold/release `GATE_MEDIA` and `GATE_RESOLVING`.
   - In `ui.py`: wired `TronScoreBackgroundPlayer.playback_state_changed` to hold/release `GATE_MEDIA`.

4. **Latency Constants Unified**:
   - Aligned `RECONNECT_BASE_S = 0.5` and `RECONNECT_MAX_S = 5.0` across `main.py`, `dashboard/server.py`, and `tests/test_uplink_latency.py`.

### 2. Verification
- `py -3.12 -m unittest discover -s tests/hud_video`: 102/102 PASS.
- `py -3.12 -m unittest tests/test_audio_gate.py`: 7/7 PASS.
- `py -3.12 -m unittest tests/test_uplink_latency.py tests/test_voice_sleep.py tests/test_wake_word.py`: 13/13 PASS.
