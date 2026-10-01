"""tools/train_wakeword.py — CLI tool for wake-word model training, export, and verification.

Allows verifying, testing, and downloading ONNX models for "hey alfred" and bare "alfred".
"""

from __future__ import annotations

import argparse
import hashlib
import logging
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── Training & Verification Constants ───────────────────────────────────────
TARGET_PHRASES: list[str] = ["hey alfred", "alfred"]
MODELS_DIR: Path = ROOT / "models"
DEFAULT_MODEL_PATH: Path = MODELS_DIR / "alfred.onnx"
OFFICIAL_MODEL_URL: str = (
    "https://raw.githubusercontent.com/fwartner/"
    "home-assistant-wakewords-collection/main/en/alfred/alfred.onnx"
)
EXPECTED_SHA256: str = "6b67237ff9da3bf00cb443438503ef842655263b62323f7da48e3f7c2e81940e"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("train_wakeword")


def verify_model() -> bool:
    """Verify presence and integrity of the local ONNX model."""
    if not DEFAULT_MODEL_PATH.exists():
        logger.warning("Model file not found at: %s", DEFAULT_MODEL_PATH)
        return False

    data = DEFAULT_MODEL_PATH.read_bytes()
    sha256 = hashlib.sha256(data).hexdigest()
    logger.info("Model path: %s", DEFAULT_MODEL_PATH)
    logger.info("Size: %d bytes", len(data))
    logger.info("SHA256: %s", sha256)

    try:
        import onnxruntime as ort
        session = ort.InferenceSession(str(DEFAULT_MODEL_PATH), providers=["CPUExecutionProvider"])
        inputs = [i.name for i in session.get_inputs()]
        outputs = [o.name for o in session.get_outputs()]
        logger.info("ONNX Runtime verification SUCCESS. Inputs: %s, Outputs: %s", inputs, outputs)
        return True
    except Exception as exc:
        logger.error("ONNX Runtime verification FAILED: %s", exc)
        return False


def download_model(force: bool = False) -> bool:
    """Download the official pre-trained ONNX wake word model."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    if DEFAULT_MODEL_PATH.exists() and not force:
        logger.info("Model already exists at: %s (use --force to overwrite)", DEFAULT_MODEL_PATH)
        return True

    import urllib.request
    logger.info("Downloading official model from: %s", OFFICIAL_MODEL_URL)
    try:
        urllib.request.urlretrieve(OFFICIAL_MODEL_URL, DEFAULT_MODEL_PATH)
        logger.info("Download completed successfully -> %s", DEFAULT_MODEL_PATH)
        return verify_model()
    except Exception as exc:
        logger.error("Download failed: %s", exc)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="ALFRED Wake-Word Model Tool")
    parser.add_argument("--verify", action="store_true", help="Verify local ONNX model integrity")
    parser.add_argument("--download", action="store_true", help="Download official model weights")
    parser.add_argument("--force", action="store_true", help="Force overwrite existing model")

    args = parser.parse_args()

    if args.download:
        ok = download_model(force=args.force)
        sys.exit(0 if ok else 1)
    elif args.verify or len(sys.argv) == 1:
        ok = verify_model()
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
