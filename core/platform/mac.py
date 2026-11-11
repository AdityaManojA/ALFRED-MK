"""
core/platform/mac.py — macOS native platform backend.
"""
from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget

from core.platform.base import PlatformBackend

log = logging.getLogger(__name__)

TTS_VOICE_MAC: str = "Daniel"  # UK English or Samantha


class MacPlatformBackend(PlatformBackend):
    """macOS implementation utilizing AppleScript, lsappinfo, and Quartz APIs."""

    def platform_name(self) -> str:
        """Return the platform identifier string 'mac'."""
        return "mac"

    def window_flags(self) -> Qt.WindowType:
        """Return the Qt window flags for a frameless, always-on-top top-level window."""
        return (
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

    def make_toplevel(self, widget: QWidget) -> None:
        """Apply the platform window flags and a translucent background to the widget."""
        widget.setWindowFlags(self.window_flags())
        widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def tts_speak(self, text: str, voice: Optional[str] = None, speed: float = 1.0) -> bool:
        """Speak text asynchronously with the macOS say command at a rate scaled by speed.
        Returns True if the process was launched.
        """
        v = voice or TTS_VOICE_MAC
        rate = int(175 * speed)
        try:
            subprocess.Popen(["say", "-v", v, "-r", str(rate), text])
            return True
        except Exception as e:
            log.debug("[PlatformMac] say command failed: %s", e)
            return False

    def stt_listen(self) -> None:
        """No-op placeholder for platform speech-to-text listening."""
        pass

    def frontmost(self) -> dict[str, Any]:
        """Return app id, spoken label and browser/home-base flags of the frontmost surface, or {} on failure."""
        try:
            from core.sentry.focus.platform.mac import MacPlatformReader
            reader = MacPlatformReader()
            surface = reader.get_frontmost_surface()
            return {
                "app_id": surface.app_id,
                "label": surface.spoken_label,
                "is_browser": surface.is_browser,
                "is_home_base": surface.is_home_base,
            }
        except Exception as e:
            log.debug("[PlatformMac] frontmost query failed: %s", e)
            return {}

    def capture_screen(self, save_path: Optional[Path] = None) -> Optional[Path]:
        """Take a silent screenshot with screencapture.
        Saves to save_path or a timestamped file on the Desktop; returns the path or None.
        """
        dest = save_path or (Path.home() / "Desktop" / f"alfred_shot_{int(time.time())}.png")
        try:
            res = subprocess.run(["screencapture", "-x", str(dest)], capture_output=True, timeout=5)
            if res.returncode == 0 and dest.exists():
                return dest
        except Exception as e:
            log.debug("[PlatformMac] screencapture failed: %s", e)
        return None

    def set_volume(self, pct: int) -> bool:
        """Set the system output volume (clamped to 0-100) via osascript; returns success."""
        try:
            vol = max(0, min(100, int(pct)))
            subprocess.run(["osascript", "-e", f"set volume output volume {vol}"], capture_output=True, timeout=3)
            return True
        except Exception as e:
            log.debug("[PlatformMac] set_volume failed: %s", e)
            return False

    def get_volume(self) -> Optional[int]:
        """Return the system output volume percentage via osascript, or None on failure."""
        try:
            r = subprocess.run(["osascript", "-e", "output volume of (get volume settings)"],
                               capture_output=True, text=True, timeout=3)
            return max(0, min(100, int(r.stdout.strip())))
        except Exception:
            return None

    def pause_audio(self) -> bool:
        """Pause the Music and Spotify apps via osascript; returns success."""
        try:
            subprocess.run(["osascript", "-e", 'tell application "Music" to pause'], capture_output=True, timeout=2)
            subprocess.run(["osascript", "-e", 'tell application "Spotify" to pause'], capture_output=True, timeout=2)
            return True
        except Exception:
            return False

    def resume_audio(self) -> bool:
        """Resume playback in the Music app via osascript; returns success."""
        try:
            subprocess.run(["osascript", "-e", 'tell application "Music" to play'], capture_output=True, timeout=2)
            return True
        except Exception:
            return False

    def paste(self, text: str) -> bool:
        """Copy text to the clipboard and send Command+V; returns False on any error."""
        try:
            import pyperclip
            import pyautogui
            pyperclip.copy(text)
            time.sleep(0.05)
            pyautogui.hotkey("command", "v")
            return True
        except Exception:
            return False

    def hotkey(self, *keys: str) -> bool:
        """Press the given key combination with pyautogui; returns False on any error."""
        try:
            import pyautogui
            pyautogui.hotkey(*keys)
            return True
        except Exception:
            return False
