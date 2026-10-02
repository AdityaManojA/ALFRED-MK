"""tools/record_training_samples.py — Record and package multi-user voice samples for model training.

Workflow:
  1. Record User's voice:
     py tools/record_training_samples.py --speaker aditya --clips 15
  2. Record Friend's voice:
     py tools/record_training_samples.py --speaker friend --clips 15
  3. Record Background Noise / Chatter:
     py tools/record_training_samples.py --negative --clips 10
  4. Package into alfred_training_data.zip:
     py tools/record_training_samples.py --zip
  5. (Optional) Train ONNX directly on your local machine:
     py tools/record_training_samples.py --train-local
"""

from __future__ import annotations

import argparse
import glob
import os
from pathlib import Path
import sys
import time
import zipfile

# Prevent cp1252 UnicodeEncodeError on Windows terminals
for stream in (sys.stdout, sys.stderr):
    if stream and hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "data" / "wakeword_samples"
POS_DIR = DATA_DIR / "positive"
NEG_DIR = DATA_DIR / "negative"
MODELS_DIR = ROOT / "models"
ZIP_PATH = ROOT / "alfred_training_data.zip"

SAMPLE_RATE = 16000
RECORD_SECONDS = 2.0


def record_clip(duration_s: float = RECORD_SECONDS) -> any:
    """Record mono 16 kHz int16 audio from microphone."""
    import numpy as np
    import sounddevice as sd

    samples = int(duration_s * SAMPLE_RATE)
    recording = sd.rec(samples, samplerate=SAMPLE_RATE, channels=1, dtype="int16")
    sd.wait()
    return recording.flatten()


def record_positive(speaker: str, phrase: str = "Hey Alfred", num_clips: int = 15) -> None:
    """Interactively record wake word audio clips for a specific speaker."""
    import scipy.io.wavfile as wavfile

    POS_DIR.mkdir(parents=True, exist_ok=True)
    speaker_clean = speaker.strip().lower().replace(" ", "_")
    phrase_clean = phrase.strip().lower().replace(" ", "_")

    print(f"\n🎙️ Recording {num_clips} clips for Speaker '{speaker}' saying '{phrase}'")
    print("=" * 65)
    print("Instructions: Speak into your mic naturally.")
    print("Vary your tone slightly across clips (quiet, enthusiastic, normal, far away).\n")

    for i in range(1, num_clips + 1):
        input(f"[{i}/{num_clips}] Press ENTER, then say '{phrase}' immediately...")
        print("  🔴 Recording (2.0s)... ", end="", flush=True)
        audio = record_clip(RECORD_SECONDS)
        print("Done!")

        filename = f"{speaker_clean}_{phrase_clean}_{int(time.time())}_{i:02d}.wav"
        filepath = POS_DIR / filename
        wavfile.write(str(filepath), SAMPLE_RATE, audio)
        print(f"  ✓ Saved: {filepath.name}\n")

    print(f"🎉 Successfully recorded {num_clips} clips for {speaker}!")


def record_negative(num_clips: int = 10) -> None:
    """Record ambient sounds, keyboard typing, or random conversation."""
    import scipy.io.wavfile as wavfile

    NEG_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n🎙️ Recording {num_clips} NEGATIVE ambient/speech clips (2.0s each)")
    print("=" * 65)
    print("Instructions: Speak random phrases ('Hello', 'Computer', 'Wayne', 'Batman'),")
    print("type on your keyboard, play music, or record room silence.\n")

    for i in range(1, num_clips + 1):
        input(f"[{i}/{num_clips}] Press ENTER to record background sound / chatter...")
        print("  🔴 Recording (2.0s)... ", end="", flush=True)
        audio = record_clip(RECORD_SECONDS)
        print("Done!")

        filename = f"neg_{int(time.time())}_{i:02d}.wav"
        filepath = NEG_DIR / filename
        wavfile.write(str(filepath), SAMPLE_RATE, audio)
        print(f"  ✓ Saved: {filepath.name}\n")

    print(f"🎉 Successfully recorded {num_clips} negative clips!")


def package_zip() -> None:
    """Create alfred_training_data.zip containing positive and negative recordings."""
    pos_files = sorted(glob.glob(str(POS_DIR / "*.wav")))
    neg_files = sorted(glob.glob(str(NEG_DIR / "*.wav")))

    if not pos_files:
        print(f"❌ Error: No positive WAV files found in {POS_DIR}")
        print("Record samples first using: py tools/record_training_samples.py --speaker <name>")
        return

    print(f"\n📦 Packaging training dataset into {ZIP_PATH.name}...")
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for pf in pos_files:
            zf.write(pf, arcname=f"positive/{Path(pf).name}")
        for nf in neg_files:
            zf.write(nf, arcname=f"negative/{Path(nf).name}")

    print(f"✅ Created: {ZIP_PATH}")
    print(f"  • Positive clips: {len(pos_files)}")
    print(f"  • Negative clips: {len(neg_files)}")
    print(f"  • Size: {ZIP_PATH.stat().st_size / 1024:.1f} KB")
    print("\n🚀 Ready to upload to Google Colab (`train_alfred_colab.ipynb`)!")


def train_local() -> None:
    """Train ONNX neural network directly on this machine without Google Colab."""
    import numpy as np
    import scipy.io.wavfile as wavfile
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset

    pos_files = sorted(glob.glob(str(POS_DIR / "*.wav")))
    neg_files = sorted(glob.glob(str(NEG_DIR / "*.wav")))

    if not pos_files:
        print("❌ Error: No positive audio files found. Record samples first!")
        return

    print("\n🚀 Training Custom ALFRED Neural Network (Local PyTorch -> ONNX)")
    print(f"  • Positive clips: {len(pos_files)}")
    print(f"  • Negative clips: {len(neg_files)}")

    # Add synthetic noise if negative set is small
    if len(neg_files) < 30:
        NEG_DIR.mkdir(parents=True, exist_ok=True)
        for i in range(40):
            noise = (np.random.randn(int(RECORD_SECONDS * SAMPLE_RATE)) * np.random.uniform(50, 350)).astype(np.int16)
            wavfile.write(str(NEG_DIR / f"synthetic_noise_{i:02d}.wav"), SAMPLE_RATE, noise)
        neg_files = sorted(glob.glob(str(NEG_DIR / "*.wav")))

    from core.wake_word import _ensure_openwakeword, _MODEL_INIT_LOCK
    with _MODEL_INIT_LOCK:
        _ensure_openwakeword()
        from openwakeword.model import Model
        base_onnx = str((MODELS_DIR / "alfred.onnx").resolve())
        oww = Model(wakeword_models=[base_onnx], inference_framework="onnx")

    preprocessor = oww.preprocessor
    X_list, y_list = [], []
    step_size = 1280

    print("⏳ Extracting acoustic feature embeddings...")
    for pf in pos_files:
        sr, dat = wavfile.read(pf)
        if dat.ndim > 1:
            dat = dat[:, 0]
        for offset in [0, 320, 640, 960]:
            sliced = dat[offset:]
            frames = []
            for i in range(0, len(sliced) - step_size, step_size):
                chunk = sliced[i:i + step_size]
                oww.predict(chunk)
                feat = preprocessor.get_features(16)
                if feat.shape == (1, 16, 96):
                    frames.append(feat)
            if frames:
                for f in frames[len(frames) // 3 : (2 * len(frames)) // 3 + 1]:
                    X_list.append(f)
                    y_list.append(1.0)

    for nf in neg_files:
        sr, dat = wavfile.read(nf)
        if dat.ndim > 1:
            dat = dat[:, 0]
        for i in range(0, len(dat) - step_size, step_size * 2):
            chunk = dat[i:i + step_size]
            oww.predict(chunk)
            feat = preprocessor.get_features(16)
            if feat.shape == (1, 16, 96):
                X_list.append(feat)
                y_list.append(0.0)

    X = np.vstack(X_list).astype(np.float32)
    y = np.array(y_list, dtype=np.float32).reshape(-1, 1)

    print(f"  ✓ Prepared dataset: {len(y)} samples ({int((y==1).sum())} positive, {int((y==0).sum())} negative)")

    class AlfredWakeNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.fc1 = nn.Linear(1536, 32)
            self.norm1 = nn.LayerNorm(32)
            self.relu1 = nn.ReLU()
            self.fc2 = nn.Linear(32, 32)
            self.norm2 = nn.LayerNorm(32)
            self.relu2 = nn.ReLU()
            self.fc3 = nn.Linear(32, 1)
            self.sig = nn.Sigmoid()

        def forward(self, x):
            x = x.reshape(x.shape[0], -1)
            x = self.relu1(self.norm1(self.fc1(x)))
            x = self.relu2(self.norm2(self.fc2(x)))
            return self.sig(self.fc3(x))

    dataset = TensorDataset(torch.from_numpy(X), torch.from_numpy(y))
    loader = DataLoader(dataset, batch_size=32, shuffle=True)
    model = AlfredWakeNet()

    # Transfer Learning: Initialize from base alfred.onnx weights if present
    base_model_path = MODELS_DIR / "alfred.onnx"
    if base_model_path.exists():
        try:
            import onnx
            from onnx import numpy_helper
            m_onnx = onnx.load(str(base_model_path))
            inits = {init.name: numpy_helper.to_array(init) for init in m_onnx.graph.initializer}
            if "const_fold_opt__20" in inits and "const_fold_opt__22" in inits and "const_fold_opt__23" in inits:
                with torch.no_grad():
                    model.fc1.weight.copy_(torch.from_numpy(inits["const_fold_opt__20"].T))
                    model.fc2.weight.copy_(torch.from_numpy(inits["const_fold_opt__22"].T))
                    model.fc3.weight.copy_(torch.from_numpy(inits["const_fold_opt__23"].T))
                print("  ✓ Preloaded base 'alfred.onnx' weights for Transfer Learning (combining general + real voices)!")
        except Exception as wex:
            print(f"  Notice: Training from standard initialization ({wex})")

    criterion = nn.BCELoss()
    optimizer = optim.AdamW(model.parameters(), lr=5e-4, weight_decay=1e-4)

    print("\n⚙️ Fine-tuning neural network (25 epochs)...")
    epochs = 25
    for epoch in range(1, epochs + 1):
        model.train()
        total_loss, correct, total = 0.0, 0, 0
        for bx, by in loader:
            optimizer.zero_grad()
            preds = model(bx)
            loss = criterion(preds, by)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * len(by)
            correct += ((preds >= 0.5) == (by >= 0.5)).sum().item()
            total += len(by)
        if epoch % 5 == 0 or epoch == epochs:
            print(f"  Epoch {epoch:02d}/{epochs:02d} - Loss: {total_loss/total:.4f} - Accuracy: {correct/total*100:.1f}%")

    # Export to models/alfred.onnx
    model.eval()
    dummy_input = torch.randn(1, 16, 96, dtype=torch.float32)
    output_onnx = MODELS_DIR / "alfred.onnx"

    # Backup original model if not backed up
    backup_path = MODELS_DIR / "alfred.onnx.original"
    if output_onnx.exists() and not backup_path.exists():
        import shutil
        shutil.copyfile(output_onnx, backup_path)
        print(f"  ✓ Backed up original model to: {backup_path.name}")

    torch.onnx.export(
        model,
        dummy_input,
        str(output_onnx),
        input_names=["serving_default_onnx_tf__tf_Flatten_0_eceb4355:0"],
        output_names=["PartitionedCall:0"],
        dynamic_axes={
            "serving_default_onnx_tf__tf_Flatten_0_eceb4355:0": {0: "batch"},
            "PartitionedCall:0": {0: "batch"},
        },
        opset_version=14,
        dynamo=False,
    )
    print(f"\n🎉 Successfully trained and exported '{output_onnx.name}'!")
    print(f"Location: {output_onnx}")
    print("ALFRED will now wake up specifically to your and your friend's voices!")


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-User Voice Dataset Recorder & Trainer")
    parser.add_argument("--speaker", type=str, default="user", help="Speaker name (e.g. aditya, friend)")
    parser.add_argument("--record-positive", action="store_true", help="Record positive wake-word utterances")
    parser.add_argument("--phrase", type=str, default="Hey Alfred", help="Phrase to record")
    parser.add_argument("--clips", type=int, default=15, help="Number of clips to record")
    parser.add_argument("--negative", action="store_true", help="Record negative ambient/chatter samples")
    parser.add_argument("--zip", action="store_true", help="Package recorded data into alfred_training_data.zip for Colab")
    parser.add_argument("--train-local", action="store_true", help="Train the ONNX neural network directly on this machine")

    args = parser.parse_args()

    if args.record_positive or (args.speaker and args.speaker != "user"):
        record_positive(speaker=args.speaker, phrase=args.phrase, num_clips=args.clips)
    elif args.negative:
        record_negative(num_clips=args.clips)
    elif args.zip:
        package_zip()
    elif args.train_local:
        train_local()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
