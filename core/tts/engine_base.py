"""
Abstract base class and capability contracts for ALFRED TTS engines.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any
import numpy as np


class Capability(Enum):
    """Capability states for TTS engines."""
    OK = "available"
    MISSING_DEPS = "missing_deps"
    NO_CUDA = "no_cuda"
    LOW_VRAM = "low_vram"
    PYTHON_VERSION = "unsupported_python"
    NOT_DOWNLOADED = "needs_download"
    CPU_ONLY = "cpu_only"
    ERROR = "error"

    def is_usable(self, allow_cpu: bool = False) -> bool:
        """Return True if this capability state permits voice synthesis."""
        if self == Capability.OK:
            return True
        if self == Capability.CPU_ONLY and allow_cpu:
            return True
        return False

    def display_status(self) -> str:
        """Human-readable status description for UI display."""
        if self == Capability.OK:
            return "Available"
        if self == Capability.NOT_DOWNLOADED:
            return "Needs download (~5 GB)"
        if self == Capability.MISSING_DEPS:
            return "Missing dependencies (pip install .[jarvis-voice])"
        if self == Capability.NO_CUDA:
            return "Unsupported on this hardware (No CUDA GPU detected)"
        if self == Capability.LOW_VRAM:
            return "Unsupported on this hardware (< 8 GB VRAM)"
        if self == Capability.PYTHON_VERSION:
            return "Unsupported Python version (requires Python 3.10 - 3.12)"
        if self == Capability.CPU_ONLY:
            return "CPU only (Slow inference - toggle CPU to enable)"
        return "Error"


class TTSEngine(ABC):
    """Abstract base interface for all TTS engines in ALFRED."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique engine identifier ('default', 'jarvis')."""
        ...

    @abstractmethod
    def is_available(self) -> Capability:
        """Inspect environment, dependencies, and hardware capability."""
        ...

    @abstractmethod
    def warm_up(self) -> None:
        """Pre-warm or compile the model off-thread before first synthesis."""
        ...

    @abstractmethod
    def synthesize(self, text: str) -> tuple[np.ndarray, int]:
        """Synthesize text and return (pcm_float32_array, sample_rate)."""
        ...

    @abstractmethod
    def speak(self, text: str) -> None:
        """Synthesize and play audio synchronously (designed for background workers)."""
        ...

    @abstractmethod
    def shutdown(self) -> None:
        """Release resources, caches, and GPU VRAM."""
        ...
