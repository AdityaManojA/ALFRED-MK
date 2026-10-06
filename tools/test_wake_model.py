"""Live Microphone Test for ALFRED Wake-Word Model (Universal / General Usage).

Tests the trained acoustic model (models/alfred.onnx) directly on live microphone input.
No speaker classification or biometric gating — open to all voices!
"""

import sys
import time
import numpy as np
import sounddevice as sd
from pathlib import Path

# Fix Windows console UTF-8 encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

MODEL_PATH = REPO_ROOT / "models" / "alfred.onnx"
SAMPLE_RATE = 16000
STEP_SIZE = 1280  # 80ms at 16kHz
THRESHOLD = 0.038  # Standard ALFRED wake threshold


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Live Microphone Test for ALFRED Wake-Word Model (Universal / General Usage)")
    parser.add_argument("--model", type=str, default="", help="Path to specific ONNX model, or leave empty for full ensemble")
    args = parser.parse_args()

    from core.wake_word import get_wake_model_paths, _is_alfred_wake_phrase, _get_whisper_verifier

    if args.model:
        chosen = Path(args.model)
        if not chosen.exists():
            print(f"❌ Error: Model not found at {chosen}")
            sys.exit(1)
        model_paths = [str(chosen)]
    else:
        model_paths = get_wake_model_paths()

    print("=" * 60)
    print("🎙️ ALFRED Unified Wake-Word Live Microphone Test")
    print("   Open to all voices — no speaker restrictions")
    print("=" * 60)
    print(f"• Models:    {', '.join(Path(p).name for p in model_paths)}")
    print(f"• Threshold: {THRESHOLD:.3f}")
    print("\n🎧 Initializing OpenWakeWord acoustic engine...")

    from openwakeword.model import Model

    model = Model(wakeword_models=model_paths, inference_framework="onnx")
    whisper_model = _get_whisper_verifier()

    print("✅ Ready! Listening live... Speak 'Hey Alfred' or 'Alfred'.")
    print("Press Ctrl+C to exit.\n")

    buffer = bytearray()
    last_ui = 0.0
    in_burst = False
    burst_frames = []
    silence_count = 0
    noise_floor = 110.0

    def audio_callback(indata, frames, _time_info, _status):
        nonlocal buffer
        buffer.extend(indata)

    with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=STEP_SIZE, dtype="int16", channels=1, callback=audio_callback):
        try:
            while True:
                if len(buffer) >= STEP_SIZE * 2:
                    chunk = bytes(buffer[:STEP_SIZE * 2])
                    del buffer[:STEP_SIZE * 2]
                    arr = np.frombuffer(chunk, dtype=np.int16)

                    # 1. Acoustic Model Inference
                    preds = model.predict(arr)
                    matches = {str(k): float(v) for k, v in preds.items() if "alfred" in str(k).lower()}
                    top_name = max(matches, key=matches.get) if matches else (list(preds.keys())[0] if preds else "alfred")
                    score = matches[top_name] if matches else (max(float(v) for v in preds.values()) if preds else 0.0)
                    rms = float(np.sqrt(np.mean(arr.astype(np.float32) ** 2)))

                    # Fast Acoustic Trigger
                    if score >= THRESHOLD:
                        print(f"\n🎯 [WAKE DETECTED] Acoustic Trigger via [{top_name}]! Score={score:.3f} (Threshold={THRESHOLD:.3f})\n")
                        time.sleep(1.2)
                        in_burst = False
                        burst_frames.clear()
                        silence_count = 0
                        continue

                    # 2. Conversational Speech Burst Verifier (Whisper fallback)
                    is_speech = rms >= max(160.0, noise_floor * 1.4)
                    if is_speech:
                        if not in_burst:
                            in_burst = True
                            burst_frames.clear()
                            silence_count = 0
                        burst_frames.append(arr)
                        silence_count = 0
                        if len(burst_frames) > 40:
                            in_burst = False
                            burst_frames.clear()
                    else:
                        if in_burst:
                            silence_count += 1
                            burst_frames.append(arr)
                            if silence_count >= 3:  # ~240ms pause
                                dur_s = len(burst_frames) * 0.08
                                if 0.35 <= dur_s <= 3.0 and whisper_model is not None:
                                    concat_audio = np.concatenate(burst_frames).astype(np.float32) / 32768.0
                                    try:
                                        segments, _ = whisper_model.transcribe(
                                            concat_audio, language="en", beam_size=1, temperature=0.0,
                                            initial_prompt="Alfred", vad_filter=True
                                        )
                                        text = " ".join(s.text for s in segments).strip()
                                        if _is_alfred_wake_phrase(text):
                                            print(f"\n🎯 [WAKE DETECTED] Speech Verifier Match! Spoke: '{text}'\n")
                                            time.sleep(1.2)
                                    except Exception:
                                        pass
                                in_burst = False
                                burst_frames.clear()
                                silence_count = 0
                        else:
                            noise_floor = 0.98 * noise_floor + 0.02 * min(rms, 250.0)

                    # Live VU Meter (continuous terminal update)
                    now = time.monotonic()
                    if (now - last_ui) >= 0.08:
                        bar_len = min(20, int(rms / 50))
                        bar = "█" * bar_len
                        status_hint = " ⚠️ (Zero signal: Check macOS Privacy > Microphone)" if rms == 0 else ""
                        print(f"\r  🎙️ Mic [{bar:<20}] RMS={rms:4.0f} | Wake Score={score:.3f}{status_hint}  ", end="", flush=True)
                        last_ui = now

                time.sleep(0.01)
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
