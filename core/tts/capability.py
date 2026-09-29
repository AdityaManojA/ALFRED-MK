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
        # Avoid importing torch synchronously on the UI thread as it causes a 10+ second freeze
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


# Capability cache to prevent UI thread stutter/freezes
_CAPABILITY_CACHE: tuple[bool, Capability] | None = None
_CACHE_TIMESTAMP: float = 0.0
_CACHE_TTL: float = 60.0  # cache for 60 seconds


def check_jarvis_capability(allow_cpu: bool = False, use_cache: bool = True) -> Capability:
    """
    Determine the current capability status for the Jarvis voice option.
    Evaluates sequentially without raising unhandled exceptions.
    Uses cached result when available to prevent UI blocking.
    """
    global _CAPABILITY_CACHE, _CACHE_TIMESTAMP
    import time
    now = time.time()
    if use_cache and _CAPABILITY_CACHE is not None:
        cached_allow_cpu, cached_cap = _CAPABILITY_CACHE
        if cached_allow_cpu == allow_cpu and (now - _CACHE_TIMESTAMP) < _CACHE_TTL:
            return cached_cap

    if not check_python_version():
        res = Capability.PYTHON_VERSION
    elif not check_dependencies():
        res = Capability.MISSING_DEPS
    else:
        has_cuda, has_vram, _ = check_cuda_and_vram()
        if not has_cuda:
            if allow_cpu:
                pass
            else:
                res = Capability.NO_CUDA
                _CAPABILITY_CACHE = (allow_cpu, res)
                _CACHE_TIMESTAMP = now
                return res
        elif not has_vram:
            res = Capability.LOW_VRAM
            _CAPABILITY_CACHE = (allow_cpu, res)
            _CACHE_TIMESTAMP = now
            return res

        # Check whether assets are downloaded
        try:
            from core.tts.jarvis_assets import are_assets_downloaded
            if not are_assets_downloaded():
                res = Capability.NOT_DOWNLOADED
            elif not has_cuda and allow_cpu:
                res = Capability.CPU_ONLY
            else:
                res = Capability.OK
        except Exception:
            res = Capability.NOT_DOWNLOADED

    _CAPABILITY_CACHE = (allow_cpu, res)
    _CACHE_TIMESTAMP = now
    return res
