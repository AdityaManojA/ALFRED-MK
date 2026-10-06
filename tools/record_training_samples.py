"""tools/record_training_samples.py — Record training samples for generic wake phrase detector.

IMPORTANT ARCHITECTURAL NOTE:
  This tool is used to record and compile multi-speaker audio clips to train or fine-tune
  the generic speaker-independent wake-word phrase detector (models/alfred.onnx).

  Do NOT use this tool to create per-user voiceprints!
  For per-user speaker verification (ensuring only you can wake ALFRED), use:
      python tools/enroll_voice.py --enroll <your_name>
  or open the in-app tactical HUD drawer: [VOICE BIOMETRICS].
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

    # ── Ensure sufficient & diverse negative samples ──────────────────────────
    # Three synthetic categories are critical:
    #   1. Gaussian noise at various amplitudes  (handles loud room noise)
    #   2. Near-silence / microphone hiss        (the most commonly missed case)
    #   3. Pure zeros                            (baseline silence sanity check)
    NEG_DIR.mkdir(parents=True, exist_ok=True)
    for i in range(40):
        amp = np.random.uniform(30, 300)
        noise = (np.random.randn(int(RECORD_SECONDS * SAMPLE_RATE)) * amp).astype(np.int16)
        wavfile.write(str(NEG_DIR / f"synthetic_noise_{i:02d}.wav"), SAMPLE_RATE, noise)
    for i in range(20):
        amp = np.random.uniform(1, 20)
        hiss = (np.random.randn(int(RECORD_SECONDS * SAMPLE_RATE)) * amp).astype(np.int16)
        wavfile.write(str(NEG_DIR / f"synthetic_silence_{i:02d}.wav"), SAMPLE_RATE, hiss)
    for i in range(10):
        wavfile.write(str(NEG_DIR / f"pure_silence_{i:02d}.wav"), SAMPLE_RATE,
                      np.zeros(int(RECORD_SECONDS * SAMPLE_RATE), dtype=np.int16))
    neg_files = sorted(glob.glob(str(NEG_DIR / "*.wav")))
    print(f"  \u2022 Negative clips (after synthetic augment): {len(neg_files)}")

    # ── Load OWW feature extractor using the ORIGINAL (backup) model ──────────
    # Always prefer the backup so a corrupted alfred.onnx can't poison features.
    from core.wake_word import _ensure_openwakeword, _MODEL_INIT_LOCK
    backup_path = MODELS_DIR / "alfred.onnx.original"
    feature_model_path = backup_path if backup_path.exists() else MODELS_DIR / "alfred.onnx"
    print(f"  \u2022 Feature extractor: {feature_model_path.name}")
    with _MODEL_INIT_LOCK:
        _ensure_openwakeword()
        from openwakeword.model import Model
        oww = Model(wakeword_models=[str(feature_model_path)], inference_framework="onnx")

    preprocessor = oww.preprocessor
    X_list, y_list = [], []
    step_size = 1280

    print("Extracting acoustic feature embeddings...")
    for pf in pos_files:
        sr, dat = wavfile.read(pf)
        if dat.ndim > 1:
            dat = dat[:, 0]
        # CRITICAL: reset OWW state between clips -- model is stateful and
        # bleeds audio context across files, contaminating extracted features.
        if hasattr(oww, "reset"):
            oww.reset()
        for offset in [0, 320, 640, 960]:
            sliced = dat[offset:]
            frames = []
            for i in range(0, len(sliced) - step_size, step_size):
                chunk = sliced[i:i + step_size]
                oww.predict(chunk)
                feat = preprocessor.get_features(16)
                if feat.shape == (1, 16, 96):
                    frames.append(feat)
            # Only the middle third of frames is reliably on-keyword
            if len(frames) >= 3:
                start = len(frames) // 3
                end   = (2 * len(frames)) // 3 + 1
                for f in frames[start:end]:
                    X_list.append(f)
                    y_list.append(1.0)

    for nf in neg_files:
        sr, dat = wavfile.read(nf)
        if dat.ndim > 1:
            dat = dat[:, 0]
        if hasattr(oww, "reset"):
            oww.reset()
        for i in range(0, len(dat) - step_size, step_size * 2):
            chunk = dat[i:i + step_size]
            oww.predict(chunk)
            feat = preprocessor.get_features(16)
            if feat.shape == (1, 16, 96):
                X_list.append(feat)
                y_list.append(0.0)

    X = np.vstack(X_list).astype(np.float32)
    y = np.array(y_list, dtype=np.float32).reshape(-1, 1)

    n_pos = int((y == 1).sum())
    n_neg = int((y == 0).sum())
    print(f"  Prepared dataset: {len(y)} samples  ({n_pos} positive / {n_neg} negative)")
    if n_pos == 0 or n_neg == 0:
        print("Error: no positive or no negative samples.")
        return

    # Stratified 80/20 train/val split
    rng = np.random.default_rng(42)
    pos_idx = np.where(y[:, 0] == 1)[0]
    neg_idx = np.where(y[:, 0] == 0)[0]
    rng.shuffle(pos_idx)
    rng.shuffle(neg_idx)
    pos_split = max(1, int(len(pos_idx) * 0.8))
    neg_split = max(1, int(len(neg_idx) * 0.8))
    train_idx = np.concatenate([pos_idx[:pos_split], neg_idx[:neg_split]])
    val_idx   = np.concatenate([pos_idx[pos_split:], neg_idx[neg_split:]])
    rng.shuffle(train_idx)
    X_tr, y_tr   = X[train_idx], y[train_idx]
    X_val, y_val = X[val_idx],   y[val_idx]
    print(f"  Train: {len(train_idx)}  Val: {len(val_idx)}")

    class AlfredWakeNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.fc1   = nn.Linear(1536, 64)
            self.norm1 = nn.LayerNorm(64)
            self.drop1 = nn.Dropout(0.3)
            self.relu1 = nn.ReLU()
            self.fc2   = nn.Linear(64, 32)
            self.norm2 = nn.LayerNorm(32)
            self.drop2 = nn.Dropout(0.2)
            self.relu2 = nn.ReLU()
            self.fc3   = nn.Linear(32, 1)
            self.sig   = nn.Sigmoid()

        def forward(self, x):
            x = x.reshape(x.shape[0], -1)
            x = self.drop1(self.relu1(self.norm1(self.fc1(x))))
            x = self.drop2(self.relu2(self.norm2(self.fc2(x))))
            return self.sig(self.fc3(x))

    tr_ds  = TensorDataset(torch.from_numpy(X_tr),  torch.from_numpy(y_tr))
    val_ds = TensorDataset(torch.from_numpy(X_val), torch.from_numpy(y_val))
    loader     = DataLoader(tr_ds,  batch_size=32, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=64, shuffle=False)
    net = AlfredWakeNet()
    criterion = nn.BCELoss()
    optimizer = optim.AdamW(net.parameters(), lr=3e-4, weight_decay=5e-4)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=3, factor=0.5)

    print("\nFine-tuning (up to 60 epochs, early stop on val loss)...")
    best_val_loss, best_state, patience_left = float("inf"), None, 10
    for epoch in range(1, 61):
        net.train()
        tr_loss = 0.0
        for bx, by in loader:
            optimizer.zero_grad()
            loss = criterion(net(bx), by)
            loss.backward()
            optimizer.step()
            tr_loss += loss.item() * len(by)
        tr_loss /= len(tr_ds)
        net.eval()
        val_loss, val_correct = 0.0, 0
        with torch.no_grad():
            for bx, by in val_loader:
                preds = net(bx)
                val_loss    += criterion(preds, by).item() * len(by)
                val_correct += ((preds >= 0.5) == (by >= 0.5)).sum().item()
        val_loss /= len(val_ds)
        val_acc = val_correct / len(val_ds) * 100
        scheduler.step(val_loss)
        if epoch % 5 == 0 or epoch <= 5:
            print(f"  Epoch {epoch:02d}/60 - tr={tr_loss:.4f}  val={val_loss:.4f}  val_acc={val_acc:.1f}%")
        if val_loss < best_val_loss - 1e-5:
            best_val_loss = val_loss
            best_state = {k: v.clone() for k, v in net.state_dict().items()}
            patience_left = 10
        else:
            patience_left -= 1
            if patience_left == 0:
                print(f"  Early stop at epoch {epoch}.")
                break
    if best_state:
        net.load_state_dict(best_state)

    net.eval()
    with torch.no_grad():
        val_preds = net(torch.from_numpy(X_val)).numpy()
    val_acc_final = float(((val_preds >= 0.5) == (y_val >= 0.5)).mean() * 100)

    # Silence false-positive test
    if hasattr(oww, "reset"):
        oww.reset()
    sil_feats = []
    for _ in range(120):
        oww.predict(np.zeros(step_size, dtype=np.int16))
        feat = preprocessor.get_features(16)
        if feat.shape == (1, 16, 96):
            sil_feats.append(feat)
    if sil_feats:
        with torch.no_grad():
            sil_scores = net(torch.from_numpy(np.vstack(sil_feats).astype(np.float32))).numpy()
        fp_rate = float((sil_scores >= 0.5).mean() * 100)
    else:
        fp_rate = 0.0

    print(f"\nDeployment safety check:")
    print(f"  Val accuracy (held-out):  {val_acc_final:.1f}%  (required >= 85%)")
    print(f"  Silence false-pos rate:   {fp_rate:.1f}%   (required <  5%)")

    if val_acc_final < 85.0:
        print(f"\nDEPLOY BLOCKED - val accuracy {val_acc_final:.1f}% < 85%.")
        print("   Original alfred.onnx unchanged. Record more diverse clips and retry.")
        return
    if fp_rate >= 5.0:
        print(f"\nDEPLOY BLOCKED - silence FP rate {fp_rate:.1f}% >= 5%.")
        print("   This model fires on silence. Add more silence negatives and retry.")
        return

    output_onnx = MODELS_DIR / "alfred.onnx"
    backup_dest = MODELS_DIR / "alfred.onnx.original"
    if output_onnx.exists() and not backup_dest.exists():
        import shutil
        shutil.copyfile(output_onnx, backup_dest)
        print(f"  Backed up original to: {backup_dest.name}")
    torch.onnx.export(
        net, torch.randn(1, 16, 96, dtype=torch.float32), str(output_onnx),
        input_names=["serving_default_onnx_tf__tf_Flatten_0_eceb4355:0"],
        output_names=["PartitionedCall:0"],
        dynamic_axes={
            "serving_default_onnx_tf__tf_Flatten_0_eceb4355:0": {0: "batch"},
            "PartitionedCall:0": {0: "batch"},
        },
        opset_version=14, dynamo=False,
    )
    root_onnx = ROOT / "alfred.onnx"
    if root_onnx.exists():
        try:
            import shutil
            shutil.copyfile(output_onnx, root_onnx)
        except Exception:
            pass
    print(f"\nDeployed '{output_onnx.name}'  val_acc={val_acc_final:.1f}%  silence_fp={fp_rate:.1f}%")
    print(f"   Location: {output_onnx}")


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
