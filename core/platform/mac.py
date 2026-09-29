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
        return "mac"

    def window_flags(self) -> Qt.WindowType:
        return (
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

    def make_toplevel(self, widget: QWidget) -> None:
        widget.setWindowFlags(self.window_flags())
        widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def tts_speak(self, text: str, voice: Optional[str] = None, speed: float = 1.0) -> bool:
        v = voice or TTS_VOICE_MAC
        rate = int(175 * speed)
        try:
            subprocess.Popen(["say", "-v", v, "-r", str(rate), text])
            return True
        except Exception as e:
            log.debug("[PlatformMac] say command failed: %s", e)
            return False

    def stt_listen(self) -> None:
        pass

    def frontmost(self) -> dict[str, Any]:
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
        dest = save_path or (Path.home() / "Desktop" / f"alfred_shot_{int(time.time())}.png")
        try:
            res = subprocess.run(["screencapture", "-x", str(dest)], capture_output=True, timeout=5)
            if res.returncode == 0 and dest.exists():
                return dest
        except Exception as e:
            log.debug("[PlatformMac] screencapture failed: %s", e)
        return None

    def set_volume(self, pct: int) -> bool:
        try:
            vol = max(0, min(100, int(pct)))
            subprocess.run(["osascript", "-e", f"set volume output volume {vol}"], capture_output=True, timeout=3)
            return True
        except Exception as e:
            log.debug("[PlatformMac] set_volume failed: %s", e)
            return False

    def get_volume(self) -> Optional[int]:
        try:
            r = subprocess.run(["osascript", "-e", "output volume of (get volume settings)"],
                               capture_output=True, text=True, timeout=3)
            return max(0, min(100, int(r.stdout.strip())))
        except Exception:
            return None

    def pause_audio(self) -> bool:
        try:
            subprocess.run(["osascript", "-e", 'tell application "Music" to pause'], capture_output=True, timeout=2)
            subprocess.run(["osascript", "-e", 'tell application "Spotify" to pause'], capture_output=True, timeout=2)
            return True
        except Exception:
            return False

    def resume_audio(self) -> bool:
        try:
            subprocess.run(["osascript", "-e", 'tell application "Music" to play'], capture_output=True, timeout=2)
            return True
        except Exception:
            return False

    def paste(self, text: str) -> bool:
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
        try:
            import pyautogui
            pyautogui.hotkey(*keys)
            return True
        except Exception:
            return False
