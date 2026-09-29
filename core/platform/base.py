"""
core/platform/base.py — Abstract base class for Cross-Platform OS Backends.
"""
from __future__ import annotations

import abc
from pathlib import Path
from typing import Any, Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget

# ── Named Constants ──────────────────────────────────────────────────────────
PLATFORM_FALLBACK_ORDER: tuple[str, ...] = ("win32", "darwin", "linux")
DEFAULT_SCREENSHOT_FORMAT: str = "png"


class PlatformBackend(abc.ABC):
    """Abstract interface for all OS-specific integrations."""

    @abc.abstractmethod
    def platform_name(self) -> str:
        """Return standardized platform name: 'windows' | 'mac' | 'linux'."""
        raise NotImplementedError

    @abc.abstractmethod
    def window_flags(self) -> Qt.WindowType:
        """Return standard top-level / overlay window flags for this OS."""
        raise NotImplementedError

    @abc.abstractmethod
    def make_toplevel(self, widget: QWidget) -> None:
        """Configure widget as a frameless floating top-level on this OS."""
        raise NotImplementedError

    @abc.abstractmethod
    def tts_speak(self, text: str, voice: Optional[str] = None, speed: float = 1.0) -> bool:
        """Invoke native OS speech synthesis if available."""
        raise NotImplementedError

    @abc.abstractmethod
    def stt_listen(self) -> None:
        """Initialize native speech capture if available."""
        raise NotImplementedError

    @abc.abstractmethod
    def frontmost(self) -> dict[str, Any]:
        """Return frontmost application and window telemetry."""
        raise NotImplementedError

    @abc.abstractmethod
    def capture_screen(self, save_path: Optional[Path] = None) -> Optional[Path]:
        """Capture screenshot via native OS facility."""
        raise NotImplementedError

    @abc.abstractmethod
    def set_volume(self, pct: int) -> bool:
        """Set master audio output volume (0-100)."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_volume(self) -> Optional[int]:
        """Get current master audio volume (0-100)."""
        raise NotImplementedError

    @abc.abstractmethod
    def pause_audio(self) -> bool:
        """Pause system media playback."""
        raise NotImplementedError

    @abc.abstractmethod
    def resume_audio(self) -> bool:
        """Resume system media playback."""
        raise NotImplementedError

    @abc.abstractmethod
    def paste(self, text: str) -> bool:
        """Paste text into active application."""
        raise NotImplementedError

    @abc.abstractmethod
    def hotkey(self, *keys: str) -> bool:
        """Simulate hotkey combination."""
        raise NotImplementedError
