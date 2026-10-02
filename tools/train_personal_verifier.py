"""tools/train_personal_verifier.py — Record voice samples and train multi-user custom verifier.

Allows you and your friend to record short audio clips of "Hey Alfred" / "Alfred"
and trains a lightweight, voice-specific verifier model (models/alfred_verifier.pkl).
Only authorized voices will be permitted to wake ALFRED.
"""

from __future__ import annotations

import argparse
import glob
import os
from pathlib import Path
import pickle
import sys
import time

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


def extract_positive_features(wav_path: str, model: any, model_name: str, threshold: float = 0.02, N: int = 3) -> any:
    import numpy as np
    import scipy.io.wavfile as wavfile

    sr, dat = wavfile.read(wav_path)
    if dat.ndim > 1:
        dat = dat[:, 0]
    features_list = []
    step_size = 1280
    for _ in range(N):
        start_offset = np.random.randint(0, min(1280, len(dat))) if N > 1 else 0
        sliced = dat[start_offset:]
        peak_score = -1.0
        peak_feat = None
        for i in range(0, len(sliced) - step_size, step_size):
            chunk = sliced[i:i + step_size]
            preds = model.predict(chunk)
            score = max(float(v) for v in preds.values()) if preds else 0.0
            feat = model.preprocessor.get_features(model.model_inputs[model_name])
            if score >= threshold:
                features_list.append(feat)
            if score > peak_score:
                peak_score = score
                peak_feat = feat
        if not features_list and peak_feat is not None:
            features_list.append(peak_feat)
    if not features_list:
        import numpy as np
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
    for i in range(0, len(dat) - step_size, step_size):
        chunk = dat[i:i + step_size]
        _ = model.predict(chunk)
        feat = model.preprocessor.get_features(model.model_inputs[model_name])
        features_list.append(feat)
    if not features_list:
        import numpy as np
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
    """Live microphone test showing base model activation score + personal voice verification probability."""
    if not VERIFIER_PATH.exists():
        print(f"❌ Verifier model not found at {VERIFIER_PATH}.")
        print("Train one first with: py tools/train_personal_verifier.py --train")
        return

    import numpy as np
    import sounddevice as sd
    from core.wake_word import _ensure_openwakeword, _MODEL_INIT_LOCK

    with _MODEL_INIT_LOCK:
        _ensure_openwakeword()
        from openwakeword.model import Model

        print(f"Loading base wake model: {MODEL_PATH}...")
        model = Model(wakeword_models=[str(MODEL_PATH)], inference_framework="onnx")

    print(f"Loading custom verifier: {VERIFIER_PATH}...")
    with open(VERIFIER_PATH, "rb") as f:
        verifier = pickle.load(f)

    print("\n🎧 Listening live... Speak 'Hey Alfred' or 'Alfred' into your microphone.")
    print("Press Ctrl+C to stop.\n")

    step_size = 1280  # 80ms at 16kHz
    buffer = bytearray()

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

                    if score >= 0.038:
                        # Extract embeddings and score via verifier
                        model_name = list(model.models.keys())[0]
                        features = model.preprocessor.get_features(model.model_inputs[model_name])
                        feat_flat = features.flatten().reshape(1, -1)
                        prob = float(verifier.predict_proba(feat_flat)[0][1])

                        status = "AUTHORIZED (MATCH)" if prob >= 0.5 else "REJECTED (STRANGER / MEDIA)"
                        print(f"🎯 Detection: Base Score={score:.3f} | Voice Match={prob * 100:.1f}% -> {status}")
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
