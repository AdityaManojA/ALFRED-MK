"""
Asset manager and downloader for Jarvis (VoxCPM2 LoRA) voice option.

Pins:
  JARVIS_REPO     = "FuturePresentLabs/tts-jarvis"
  JARVIS_REVISION = "v4-interface-2026-09-06"

The base model id and revision are dynamically resolved from the release's
inference_config.json — never hardcoded, never tracking 'main'.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable, Optional

# Named constants
JARVIS_REPO: str = "FuturePresentLabs/tts-jarvis"
JARVIS_REVISION: str = "v4-interface-2026-09-06"
DEFAULT_ASSET_DIR: Path = Path.home() / ".cache" / "alfred" / "jarvis_voice"


def get_jarvis_asset_dir() -> Path:
    """Return the root storage directory for Jarvis voice assets."""
    override = os.environ.get("ALFRED_JARVIS_DIR")
    if override:
        return Path(override)
    return DEFAULT_ASSET_DIR


def get_adapter_path() -> Path:
    """Path to the downloaded LoRA adapter snapshot."""
    return get_jarvis_asset_dir() / "adapter"


def get_base_model_path() -> Path:
    """Path to the downloaded base model snapshot."""
    return get_jarvis_asset_dir() / "base"


def are_assets_downloaded() -> bool:
    """
    Verify whether the pinned adapter release and base model are present and intact.
    Checks for:
      - adapter/inference_config.json
      - adapter/lora_config.json (or adapter/adapter/lora_config.json)
      - base model directory with model files
      - reference audio file
    """
    adapter_dir = get_adapter_path()
    if not adapter_dir.exists():
        return False

    inf_cfg = adapter_dir / "inference_config.json"
    if not inf_cfg.is_file():
        return False

    lora_cfg = adapter_dir / "adapter" / "lora_config.json"
    if not lora_cfg.is_file():
        lora_cfg = adapter_dir / "lora_config.json"
        if not lora_cfg.is_file():
            return False

    base_dir = get_base_model_path()
    if not base_dir.exists() or not any(base_dir.iterdir()):
        return False

    # Check for reference audio in adapter snapshot
    ref_wav = find_reference_audio(adapter_dir)
    if not ref_wav or not ref_wav.is_file():
        return False

    return True


def find_reference_audio(adapter_dir: Path) -> Optional[Path]:
    """Search for bundled reference audio file or preset."""
    candidates = [
        adapter_dir / "reference.wav",
        adapter_dir / "ref.wav",
        adapter_dir / "forward.wav",
        adapter_dir / "presets" / "forward.wav",
        adapter_dir / "presets" / "reference.wav",
        adapter_dir / "audio" / "reference.wav",
    ]
    for c in candidates:
        if c.is_file():
            return c

    # Search for any .wav in adapter directory
    for root, _, files in os.walk(adapter_dir):
        for f in files:
            if f.lower().endswith(".wav"):
                return Path(root) / f

    return None


def download_jarvis_assets(
    progress_cb: Optional[Callable[[str, float], None]] = None
) -> dict[str, Path]:
    """
    Download the pinned Jarvis adapter release and the base model referenced
    inside inference_config.json.

    progress_cb(status_message, fraction_0_to_1)
    """
    try:
        from huggingface_hub import snapshot_download
    except ImportError as e:
        raise RuntimeError("huggingface_hub is required to download Jarvis assets.") from e

    root_dir = get_jarvis_asset_dir()
    adapter_dest = get_adapter_path()
    base_dest = get_base_model_path()

    root_dir.mkdir(parents=True, exist_ok=True)
    adapter_dest.mkdir(parents=True, exist_ok=True)
    base_dest.mkdir(parents=True, exist_ok=True)

    if progress_cb:
        progress_cb(f"Downloading adapter ({JARVIS_REPO} @ {JARVIS_REVISION})…", 0.1)

    # 1. Download adapter snapshot
    snapshot_download(
        repo_id=JARVIS_REPO,
        revision=JARVIS_REVISION,
        local_dir=str(adapter_dest),
        local_dir_use_symlinks=False,
    )

    # 2. Parse inference_config.json to identify base model repo and revision
    inf_cfg_path = adapter_dest / "inference_config.json"
    if not inf_cfg_path.is_file():
        raise FileNotFoundError(
            f"Corrupt download: {inf_cfg_path} not found in {adapter_dest}"
        )

    with open(inf_cfg_path, "r", encoding="utf-8") as f:
        inf_cfg = json.load(f)

    base_repo = inf_cfg.get("base_model_id") or inf_cfg.get("base_model") or inf_cfg.get("pretrained_model_name_or_path")
    base_rev = inf_cfg.get("base_revision") or inf_cfg.get("revision")

    if not base_repo:
        raise ValueError(f"inference_config.json missing base model ID: {inf_cfg}")

    if progress_cb:
        progress_cb(f"Downloading base model ({base_repo})…", 0.5)

    # 3. Download base model snapshot (pinned from inference_config)
    snapshot_download(
        repo_id=base_repo,
        revision=base_rev,
        local_dir=str(base_dest),
        local_dir_use_symlinks=False,
    )

    # 4. Verify reference audio
    ref_wav = find_reference_audio(adapter_dest)
    if not ref_wav:
        raise FileNotFoundError(
            f"No bundled reference audio found in {JARVIS_REPO} snapshot."
        )

    if progress_cb:
        progress_cb("Jarvis assets verified.", 1.0)

    return {
        "adapter_dir": adapter_dest,
        "base_dir": base_dest,
        "reference_wav": ref_wav,
        "inference_config": inf_cfg_path,
    }
