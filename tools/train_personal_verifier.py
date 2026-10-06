"""tools/train_personal_verifier.py — [LEGACY / EXPERIMENTAL] openWakeWord Feature Classifier.

NOTE: This script is deprecated and isolated from production activation.
ALFRED now uses true neural speaker verification via:
  • Pretrained CAM++ ONNX speaker embeddings (models/speaker_verifier.onnx)
  • Per-user atomic profile storage (~/.alfred/voice_profiles/)
  • Official enrollment tool: python tools/enroll_voice.py --enroll <username>
  • In-app tactical HUD drawer: [VOICE BIOMETRICS] button

Why this legacy script was superseded:
  1. openWakeWord feature frames (1, 16, 96) encode acoustic/phonetic information,
     not robust speaker identity embeddings.
  2. Training against silence/synthetic noise without other-speaker wake utterances
     yields uncalibrated decision boundaries and high false-acceptance rates.
  3. models/alfred_verifier.pkl is NOT used by production wake detection.
"""

from __future__ import annotations

import argparse
import glob
import os
from pathlib import Path
import pickle
import sys
import time

for stream in (sys.stdout, sys.stderr):
    if stream and hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SAMPLES_DIR = ROOT / "data" / "wakeword_samples"
POS_DIR = SAMPLES_DIR / "positive"
NEG_DIR = SAMPLES_DIR / "negative"
MODELS_DIR = ROOT / "models"
MODEL_PATH = MODELS_DIR / "alfred.onnx"
VERIFIER_PATH = MODELS_DIR / "alfred_verifier.pkl"

SAMPLE_RATE = 16000
RECORD_SECONDS = 2.0


def record_clip(duration_s: float = RECORD_SECONDS) -> any:
    """Record mono 16 kHz int16 audio from default microphone."""
    import numpy as np
    import sounddevice as sd

    samples_n = int(duration_s * SAMPLE_RATE)
    recording = sd.rec(samples_n, samplerate=SAMPLE_RATE, channels=1, dtype="int16")
    sd.wait()
    return recording.flatten()


def record_interactive_positive(speaker_name: str, phrase: str, num_clips: int = 10) -> None:
    """Interactively guide user through recording positive wake-word utterances."""
    import scipy.io.wavfile as wavfile

    POS_DIR.mkdir(parents=True, exist_ok=True)
    speaker_clean = speaker_name.strip().lower().replace(" ", "_")
    phrase_clean = phrase.strip().lower().replace(" ", "_")

    print(f"\n🎙️ Recording {num_clips} samples for Speaker '{speaker_name}' saying '{phrase}'")
    print("----------------------------------------------------------------------")
    print("Instructions: When prompted, speak clearly into your microphone.")
    print("You can vary your tone slightly (normal, quiet, enthusiastic, far away).\n")

    for i in range(1, num_clips + 1):
        input(f"[{i}/{num_clips}] Press ENTER, then say '{phrase}' immediately...")
        print("  🔴 Recording (2.0s)... ", end="", flush=True)
        audio = record_clip(RECORD_SECONDS)
        print("Done!")

        filename = f"{speaker_clean}_{phrase_clean}_{int(time.time())}_{i:02d}.wav"
        filepath = POS_DIR / filename
        wavfile.write(str(filepath), SAMPLE_RATE, audio)
        print(f"  ✓ Saved to: {filepath.name}\n")

    print(f"🎉 Successfully recorded {num_clips} positive clips for {speaker_name}!")


def record_interactive_negative(num_clips: int = 10) -> None:
    """Record negative ambient sounds or random speech (not saying the wake word)."""
    import scipy.io.wavfile as wavfile

    NEG_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n🎙️ Recording {num_clips} NEGATIVE ambient/speech samples (2.0s each)")
    print("----------------------------------------------------------------------")
    print("Instructions: Speak random phrases ('Hello', 'Computer', 'Batman', 'Wayne'),")
    print("type on your keyboard, play music, or record room silence.\n")

    for i in range(1, num_clips + 1):
        input(f"[{i}/{num_clips}] Press ENTER to record background sound / chatter...")
        print("  🔴 Recording (2.0s)... ", end="", flush=True)
        audio = record_clip(RECORD_SECONDS)
        print("Done!")

        filename = f"neg_{int(time.time())}_{i:02d}.wav"
        filepath = NEG_DIR / filename
        wavfile.write(str(filepath), SAMPLE_RATE, audio)
        print(f"  ✓ Saved to: {filepath.name}\n")

    print(f"🎉 Successfully recorded {num_clips} negative clips!")


def extract_positive_features(wav_path: str, model: any, model_name: str) -> any:
    import numpy as np
    import scipy.io.wavfile as wavfile

    sr, dat = wavfile.read(wav_path)
    if dat.ndim > 1:
        dat = dat[:, 0]
    features_list = []
    step_size = 1280
    model.reset()

    for i in range(0, len(dat) - step_size, step_size):
        chunk = dat[i:i + step_size]
        rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
        model.predict(chunk)
        if rms >= 250.0:
            feat = model.preprocessor.get_features(model.model_inputs[model_name])
            if feat.shape == (1, 16, 96):
                features_list.append(feat)

    if not features_list:
        rms_scores = [(j, float(np.sqrt(np.mean(dat[j:j+step_size].astype(np.float32)**2))))
                      for j in range(0, len(dat) - step_size, step_size)]
        rms_scores.sort(key=lambda x: x[1], reverse=True)
        model.reset()
        for j, _ in rms_scores[:3]:
            for k in range(0, j + step_size, step_size):
                model.predict(dat[k:k+step_size])
            feat = model.preprocessor.get_features(model.model_inputs[model_name])
            if feat.shape == (1, 16, 96):
                features_list.append(feat)

    if not features_list:
        return np.empty((0, model.model_inputs[model_name], 96))
    return np.vstack(features_list)


def extract_negative_features(wav_path: str, model: any, model_name: str) -> any:
    import numpy as np
    import scipy.io.wavfile as wavfile

    sr, dat = wavfile.read(wav_path)
    if dat.ndim > 1:
        dat = dat[:, 0]
    features_list = []
    step_size = 1280
    model.reset()
    for i in range(0, len(dat) - step_size, step_size):
        chunk = dat[i:i + step_size]
        model.predict(chunk)
        feat = model.preprocessor.get_features(model.model_inputs[model_name])
        if feat.shape == (1, 16, 96):
            features_list.append(feat)
    if not features_list:
        return np.empty((0, model.model_inputs[model_name], 96))
    return np.vstack(features_list)


def train_verifier() -> bool:
    """Train voice-specific verifier on recorded positive and negative clips."""
    pos_files = sorted(glob.glob(str(POS_DIR / "*.wav")))
    neg_files = sorted(glob.glob(str(NEG_DIR / "*.wav")))

    if not pos_files:
        print(f"❌ Error: No positive WAV files found in {POS_DIR}")
        print("Record samples first using:")
        print("  py tools/train_personal_verifier.py --record-positive --speaker <your_name> --phrase \"Hey Alfred\"")
        print("  py tools/train_personal_verifier.py --record-positive --speaker <friend_name> --phrase \"Hey Alfred\"")
        return False

    speakers = set()
    for pf in pos_files:
        basename = Path(pf).stem
        parts = basename.split("_")
        if parts:
            speakers.add(parts[0].capitalize())

    if len(neg_files) < 5:
        print(f"⚠️ Notice: Found only {len(neg_files)} negative clips in {NEG_DIR}.")
        print("Generating synthetic noise clips for robust negative baseline...")
        NEG_DIR.mkdir(parents=True, exist_ok=True)
        import numpy as np
        import scipy.io.wavfile as wavfile
        for idx in range(15):
            noise = (np.random.randn(int(RECORD_SECONDS * SAMPLE_RATE)) * 250).astype(np.int16)
            wavfile.write(str(NEG_DIR / f"synthetic_noise_{idx:02d}.wav"), SAMPLE_RATE, noise)
        neg_files = sorted(glob.glob(str(NEG_DIR / "*.wav")))

    print("\n🚀 Training Multi-User Voice Verifier")
    print(f"  • Base model:        {MODEL_PATH.name}")
    print(f"  • Authorized voices: {', '.join(sorted(speakers)) if speakers else 'unknown'}")
    print(f"  • Positive clips:    {len(pos_files)}")
    print(f"  • Negative clips:    {len(neg_files)}")
    print(f"  • Output target:     {VERIFIER_PATH}")

    try:
        import numpy as np
        from core.wake_word import _ensure_openwakeword, _MODEL_INIT_LOCK
        import openwakeword.custom_verifier_model as cvm

        with _MODEL_INIT_LOCK:
            _ensure_openwakeword()
            from openwakeword.model import Model
            oww = Model(wakeword_models=[str(MODEL_PATH)], inference_framework="onnx")
            model_name = list(oww.models.keys())[0]

        print("\n⏳ Extracting acoustic embeddings from positive audio clips...")
        pos_feature_list = []
        for pf in pos_files:
            feats = extract_positive_features(pf, oww, model_name)
            if feats.shape[0] > 0:
                pos_feature_list.append(feats)

        if not pos_feature_list:
            print("❌ Error: Could not extract features from positive clips.")
            return False

        pos_features = np.vstack(pos_feature_list)
        print(f"  ✓ Extracted {pos_features.shape[0]} positive feature frames across all speakers.")

        print("⏳ Extracting acoustic embeddings from negative audio clips...")
        neg_feature_list = []
        for nf in neg_files:
            feats = extract_negative_features(nf, oww, model_name)
            if feats.shape[0] > 0:
                neg_feature_list.append(feats)

        # Add digital silence and ambient noise to negative dataset
        oww.reset()
        for _ in range(50):
            oww.predict(np.zeros(1280, dtype=np.int16))
            feat = oww.preprocessor.get_features(16)
            if feat.shape == (1, 16, 96):
                neg_feature_list.append(feat)

        neg_features = np.vstack(neg_feature_list)
        print(f"  ✓ Extracted {neg_features.shape[0]} negative feature frames.")

        print("\n⚙️ Training personal voice classifier head...")
        X = np.vstack((pos_features, neg_features))
        y = np.array([1] * pos_features.shape[0] + [0] * neg_features.shape[0])

        clf = cvm.train_verifier_model(X, y)

        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        with open(VERIFIER_PATH, "wb") as f:
            pickle.dump(clf, f)

        print("\n🎉 Multi-User Voice Verifier Successfully Trained and Saved!")
        print(f"  • Target: {VERIFIER_PATH}")
        print(f"  • Authorized speakers calibrated: {', '.join(sorted(speakers))}")
        print("  • ALFRED will now only respond to these voices and reject strangers.")
        return True
    except Exception as exc:
        print(f"\n❌ Training failed: {exc}")
        import traceback
        traceback.print_exc()
        return False


def test_live() -> None:
    """Live microphone test demonstrating hybrid wake-word verification:
    1. Wake Word Match (Acoustic model score or Whisper speech burst)
    2. Speaker Verification (Aditya/Friend vs Stranger/TV via alfred_verifier.pkl)
    """
    if not VERIFIER_PATH.exists():
        print(f"❌ Verifier model not found at {VERIFIER_PATH}.")
        print("Train one first with: py tools/train_personal_verifier.py --train")
        return

    import numpy as np
    import sounddevice as sd
    from core.wake_word import (
        _ensure_openwakeword,
        _MODEL_INIT_LOCK,
        _is_alfred_wake_phrase,
        _get_whisper_verifier,
        DEFAULT_THRESHOLD,
    )

    with _MODEL_INIT_LOCK:
        _ensure_openwakeword()
        from openwakeword.model import Model

        print(f"Loading base wake model: {MODEL_PATH}...")
        model = Model(wakeword_models=[str(MODEL_PATH)], inference_framework="onnx")

    print(f"Loading custom verifier: {VERIFIER_PATH}...")
    with open(VERIFIER_PATH, "rb") as f:
        verifier = pickle.load(f)

    # Prewarm Whisper in background
    whisper_model = _get_whisper_verifier()

    print("\n🎧 Listening live... Speak 'Hey Alfred' or 'Alfred' into your microphone.")
    print("Dual Gate Active: Requires Wake Phrase + Authorized Voice (Aditya/Friend).")
    print("Microphone VU meter active. Press Ctrl+C to stop.\n")

    step_size = 1280  # 80ms at 16kHz
    buffer = bytearray()
    last_ui_update = 0.0

    # Speech burst accumulator for Whisper verifier
    in_burst = False
    burst_frames = []
    silence_count = 0
    noise_floor = 110.0

    def callback(indata, frames, _time_info, _status):
        nonlocal buffer
        buffer.extend(indata)

    with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=step_size, dtype="int16", channels=1, callback=callback):
        try:
            while True:
                if len(buffer) >= step_size * 2:
                    chunk = bytes(buffer[:step_size * 2])
                    del buffer[:step_size * 2]
                    arr = np.frombuffer(chunk, dtype=np.int16)
                    preds = model.predict(arr)
                    score = max(float(v) for v in preds.values()) if preds else 0.0
                    rms = float(np.sqrt(np.mean(arr.astype(np.float32) ** 2)))

                    model_name = list(model.models.keys())[0]
                    features = model.preprocessor.get_features(model.model_inputs[model_name])
                    prob = float(verifier.predict_proba(features)[0][1])

                    # Gate 1A: Acoustic Wake Match (score >= DEFAULT_THRESHOLD)
                    if score >= DEFAULT_THRESHOLD:
                        speaker = "Aditya/Friend" if prob >= 0.50 else "Guest/Other Voice"
                        print(f"\n🎯 [WAKE DETECTED] Acoustic Match ({score:.3f}) | Speaker: {speaker} ({prob * 100:5.1f}%) -> AUTHORIZED\n")
                        time.sleep(1.0)
                        in_burst = False
                        burst_frames.clear()
                        silence_count = 0
                        continue

                    # Gate 1B: Speech Burst Whisper Verifier (captures real conversational phrasing)
                    is_speech = rms >= max(160.0, noise_floor * 1.4)
                    if is_speech:
                        if not in_burst:
                            in_burst = True
                            burst_frames.clear()
                            silence_count = 0
                        burst_frames.append(arr)
                        silence_count = 0
                        if len(burst_frames) > 40:  # > 3.2s
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
                                            concat_audio,
                                            language="en",
                                            beam_size=1,
                                            temperature=0.0,
                                            initial_prompt="Alfred",
                                            vad_filter=True,
                                        )
                                        text = " ".join(s.text for s in segments).strip()
                                        if _is_alfred_wake_phrase(text):
                                            speaker = "Aditya/Friend" if prob >= 0.50 else "Guest/Other Voice"
                                            print(f"\n🎯 [WAKE DETECTED] Spoke '{text}' | Speaker: {speaker} ({prob * 100:5.1f}%) -> AUTHORIZED\n")
                                            time.sleep(1.0)
                                    except Exception:
                                        pass
                                in_burst = False
                                burst_frames.clear()
                                silence_count = 0
                        else:
                            noise_floor = 0.98 * noise_floor + 0.02 * min(rms, 250.0)

                    # Live VU Meter update while listening
                    if rms >= 150:
                        now = time.monotonic()
                        if (now - last_ui_update) >= 0.10:
                            bar_len = min(20, int(rms / 100))
                            bar = "█" * bar_len
                            speaker = "Aditya/Friend" if prob >= 0.50 else "Guest/Other"
                            print(f"\r  🎙️ Mic [{bar:<20}] RMS={rms:4.0f} | Voice: {speaker} ({prob * 100:4.1f}%) | Wake={score:.3f}  ", end="", flush=True)
                            last_ui_update = now

                time.sleep(0.01)
        except KeyboardInterrupt:
            print("\nStopped.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-User Personal Wake-Word Verifier Trainer")
    parser.add_argument("--record-positive", action="store_true", help="Record positive wake-word utterances")
    parser.add_argument("--record-negative", action="store_true", help="Record negative chatter/ambient clips")
    parser.add_argument("--speaker", type=str, default="user", help="Name of speaker (e.g. aditya, john)")
    parser.add_argument("--phrase", type=str, default="Hey Alfred", help="Phrase to record ('Hey Alfred' or 'Alfred')")
    parser.add_argument("--clips", type=int, default=10, help="Number of clips to record")
    parser.add_argument("--train", action="store_true", help="Train verifier model from recorded clips")
    parser.add_argument("--test", action="store_true", help="Test microphone live against trained verifier")

    args = parser.parse_args()

    if args.record_positive:
        record_interactive_positive(speaker_name=args.speaker, phrase=args.phrase, num_clips=args.clips)
    elif args.record_negative:
        record_interactive_negative(num_clips=args.clips)
    elif args.train:
        train_verifier()
    elif args.test:
        test_live()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
