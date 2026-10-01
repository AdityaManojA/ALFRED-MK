# Phase 5 Notes — Tiny Wake Word: "hey alfred" OR "alfred"

## Status: COMPLETE

### 1. Architecture & Design
1. **Dual-Phrase Activation Strategy (`core/audio/wakeword_tiny.py`)**:
   - Single-word wake words in Batman-themed environments are heavily prone to false-positive activations from media dialogue, movies, or the assistant speaking its own name.
   - Dual-phrase detector introduces asymmetric confidence barriers:
     - `"hey alfred"`: Compound phonetic structure carries low accidental collision probability → Threshold `WAKEWORD_CONFIDENCE_HEY = 0.70`.
     - Bare `"alfred"`: High ambient exposure risk → Strict elevated threshold `WAKEWORD_CONFIDENCE_BARE = 0.85`.

2. **Acoustic Gating & Refractory Suppression**:
   - **`GATE_TTS` Lockout**: Before performing inference on incoming audio frames, `DualWakeWordDetector.feed()` queries `get_audio_gate().is_reason_held(GATE_TTS)`. If ALFRED is speaking, inference is immediately bypassed, preventing acoustic self-trigger loops.
   - **Refractory Cooldown**: A 1500 ms refractory window (`REFRACTORY_WINDOW_MS = 1500`) locks out duplicate detections on prolonged utterances.

3. **Fail-Open Guarantees**:
   - If ONNX Runtime or the model weights are unavailable or fail to initialize, `DualWakeWordDetector` logs a warning once and falls open (allowing fallback verifiers or manual triggers without crashing the main application).

4. **Model Verification & CLI Tooling (`tools/train_wakeword.py`)**:
   - Added `tools/train_wakeword.py` with `--verify` and `--download` options.
   - Verified local `models/alfred.onnx` integrity (SHA256 verified, ONNX Runtime session initialized successfully).

### 2. Verification
- `py -3.12 tools/train_wakeword.py --verify`: SUCCESS (SHA256: 6b6723..., ONNX Runtime inputs & outputs validated).
- `py -3.12 -m unittest tests/audio/test_wakeword_tiny.py`: 5/5 PASS in 3.935s.
- Verified dual thresholds, refractory lockout timing, buffer frame accumulation, and GATE_TTS acoustic suppression.
