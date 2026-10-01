# Phase 9 Notes — Regression Sweep & Test Hardening

## Status: COMPLETE

### 1. Regression Audit & Verification
A full regression sweep was executed across all major test suites, confirming zero regressions, clean thread safety, bounded buffers, and robust error boundaries:

| Test Suite / Subsystem | Tests Executed | Result | Time |
| :--- | :--- | :--- | :--- |
| `tests/hud_video` | 102 tests | **PASS** | 0.768s |
| `tests/sentry` | 29 tests | **PASS** | 4.702s |
| `tests/audio` | 10 tests | **PASS** | 6.728s |
| `tests/boot` | 12 tests | **PASS** | 4.154s |
| `tests/intents` | 4 tests | **PASS** | 0.379s |
| `tests/speech` | 3 tests | **PASS** | 0.115s |
| `tests/media` | 3 tests | **PASS** | 0.136s |
| `tests/test_voice_sleep.py`, `tests/test_wake_word.py`, `test_audio_gate.py`, etc. | 33 tests | **PASS** | 3.252s |
| `tests/test_hud_frame_latency.py`, `test_hud_reactivity.py`, `test_hybrid_wake.py` | 21 tests | **PASS** | 14.331s |
| `tests/test_intent_router.py`, `tests/test_system_monitor.py` | 12 tests | **PASS** | 1.812s |

### 2. Thread Safety & Architectural Invariants Verified
1. **Thread-Boundary Integrity**:
   - `assert_gui_thread()` respected across all UI methods and Qt slots.
   - Background audio and pipeline workers communicate exclusively via signals (`pyqtSignal`) or thread-safe non-blocking queues (`queue.Queue`, `asyncio.Queue`).
   - Zero cross-thread GUI warnings or violations encountered during tests.

2. **Acoustic Self-Trigger Feedback Shielding**:
   - `go_to_sleep` sleep directive response verified scrubbed (`"Going to sleep now, sir. Call me when you need me."`).
   - `AudioGate` holds `GATE_TTS` during speech output, actively suppressing wake-word model feeding during ALFRED's vocalizations.
   - Refractory lockout window (`1500 ms`) confirmed locking out duplicate activations.

3. **Leak & Memory Hardening**:
   - Bounded ring buffers in `push_visemes` (clamped to 500 frames) and `SharedAudioStream` pre-roll (clamped to 62 chunks = 2.0s).
   - In-memory `SpeculativePrefetcher` LRU cache bounded to 64 records with 10.0s TTL eviction.
