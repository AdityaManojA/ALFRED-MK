"""
Capability inspector for Jarvis VoxCPM2 TTS engine.

Validates:
- Python runtime version (requires >= 3.10 and < 3.13)
- Optional dependencies (voxcpm, torch, soundfile, huggingface_hub)
- CUDA GPU presence and minimum VRAM (>= 8 GB)
- CPU-only execution fallback gating
- Model asset download status
"""
from __future__ import annotations

import sys
from typing import Optional

from core.tts.engine_base import Capability

JARVIS_MIN_VRAM_GB: float = 8.0
JARVIS_ALLOW_CPU_DEFAULT: bool = False
JARVIS_PYTHON_MIN: tuple[int, int] = (3, 10)
JARVIS_PYTHON_MAX: tuple[int, int] = (3, 13)

# Pinned HuggingFace repository and revision constants
JARVIS_REPO: str = "FuturePresentLabs/tts-jarvis"
JARVIS_REVISION: str = "v4-interface-2026-09-06"


def check_python_version() -> bool:
    """Validate Python runtime version: >= 3.10 and < 3.13."""
    return JARVIS_PYTHON_MIN <= sys.version_info[:2] < JARVIS_PYTHON_MAX


def check_dependencies() -> bool:
    """Check if all optional packages required for Jarvis are installed without full import."""
    import importlib.util
    required = ("torch", "soundfile", "huggingface_hub", "voxcpm")
    for mod in required:
        try:
            if mod in sys.modules:
                continue
            spec = importlib.util.find_spec(mod)
            if spec is None:
                return False
        except Exception:
            return False
    return True


def check_cuda_and_vram() -> tuple[bool, bool, float]:
    """
    Check CUDA availability and device 0 total memory in GB.
    Returns (has_cuda, has_min_vram, vram_gb).
    """
    if "torch" not in sys.modules:
        # Don't import torch synchronously during UI boot if not already loaded
        import importlib.util
        if importlib.util.find_spec("torch") is None:
            return False, False, 0.0
    try:
        import torch
        if not torch.cuda.is_available():
            return False, False, 0.0
        vram_bytes = torch.cuda.get_device_properties(0).total_memory
        vram_gb = vram_bytes / (1024.0 ** 3)
        return True, (vram_gb >= JARVIS_MIN_VRAM_GB), vram_gb
    except Exception:
        return False, False, 0.0


def check_jarvis_capability(allow_cpu: bool = False) -> Capability:
    """
    Determine the current capability status for the Jarvis voice option.
    Evaluates sequentially without raising unhandled exceptions.
    """
    if not check_python_version():
        return Capability.PYTHON_VERSION

    if not check_dependencies():
        return Capability.MISSING_DEPS

    has_cuda, has_vram, _ = check_cuda_and_vram()
    if not has_cuda:
        if allow_cpu:
            # CPU allowed explicitly
            pass
        else:
            return Capability.NO_CUDA
    elif not has_vram:
        return Capability.LOW_VRAM

    # Check whether assets are downloaded
    try:
        from core.tts.jarvis_assets import are_assets_downloaded
        if not are_assets_downloaded():
            return Capability.NOT_DOWNLOADED
    except Exception:
        return Capability.NOT_DOWNLOADED

    if not has_cuda and allow_cpu:
        return Capability.CPU_ONLY

    return Capability.OK
