"""
core/platform/win.py — Windows native platform backend.
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


class WindowsPlatformBackend(PlatformBackend):
    """Windows implementation delegating to existing Win32, pycaw, and UI Automation mechanisms."""

    def platform_name(self) -> str:
        return "windows"

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
        # Standard SAPI / PowerShell / pyttsx3 fallback
        try:
            cmd = f"Add-Type -AssemblyName System.speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{text.replace('\'', '\'\'')}')"
            subprocess.Popen(["powershell", "-Command", cmd], creationflags=subprocess.CREATE_NO_WINDOW)
            return True
        except Exception as e:
            log.debug("[PlatformWin] TTS speak failed: %s", e)
            return False

    def stt_listen(self) -> None:
        pass

    def frontmost(self) -> dict[str, Any]:
        try:
            from core.sentry.focus.platform.win import WinPlatformReader
            reader = WinPlatformReader()
            surface = reader.get_frontmost_surface()
            return {
                "app_id": surface.app_id,
                "label": surface.spoken_label,
                "is_browser": surface.is_browser,
                "is_home_base": surface.is_home_base,
            }
        except Exception as e:
            log.debug("[PlatformWin] frontmost query failed: %s", e)
            return {}

    def capture_screen(self, save_path: Optional[Path] = None) -> Optional[Path]:
        try:
            from actions.screen_processor import capture_screen
            dest = save_path or (Path.home() / "Desktop" / f"alfred_shot_{int(time.time())}.png")
            shot = capture_screen(monitor=1)
            if shot:
                shot.save(str(dest))
                return dest
        except Exception as e:
            log.debug("[PlatformWin] capture_screen failed: %s", e)
        return None

    def set_volume(self, pct: int) -> bool:
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(IAudioEndpointVolume)
            volume.SetMasterVolumeLevelScalar(max(0.0, min(1.0, pct / 100.0)), None)
            return True
        except Exception as e:
            log.debug("[PlatformWin] set_volume failed: %s", e)
            return False

    def get_volume(self) -> Optional[int]:
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(IAudioEndpointVolume)
            return max(0, min(100, round(volume.GetMasterVolumeLevelScalar() * 100)))
        except Exception:
            return None

    def pause_audio(self) -> bool:
        try:
            import ctypes
            ctypes.windll.user32.PostMessageW(0xFFFF, 0x0319, 0, 47 << 16) # WM_APPCOMMAND APPCOMMAND_MEDIA_PAUSE
            return True
        except Exception:
            return False

    def resume_audio(self) -> bool:
        try:
            import ctypes
            ctypes.windll.user32.PostMessageW(0xFFFF, 0x0319, 0, 46 << 16) # WM_APPCOMMAND APPCOMMAND_MEDIA_PLAY
            return True
        except Exception:
            return False

    def paste(self, text: str) -> bool:
        try:
            import pyperclip
            import pyautogui
            pyperclip.copy(text)
            time.sleep(0.05)
            pyautogui.hotkey("ctrl", "v")
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
