"""
core/platform/linux.py — Linux native platform backend.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget

from core.platform.base import PlatformBackend

log = logging.getLogger(__name__)


class LinuxPlatformBackend(PlatformBackend):
    """Linux implementation using pactl, playerctl, xdotool, and standard utilities."""

    def platform_name(self) -> str:
        return "linux"

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
        if shutil.which("espeak-ng"):
            try:
                subprocess.Popen(["espeak-ng", text])
                return True
            except Exception:
                pass
        elif shutil.which("espeak"):
            try:
                subprocess.Popen(["espeak", text])
                return True
            except Exception:
                pass
        elif shutil.which("piper"):
            try:
                subprocess.Popen(["piper", "--output_file", "-", text])
                return True
            except Exception:
                pass
        return False

    def stt_listen(self) -> None:
        pass

    def frontmost(self) -> dict[str, Any]:
        try:
            from core.sentry.focus.platform.linux import LinuxPlatformReader
            reader = LinuxPlatformReader()
            surface = reader.get_frontmost_surface()
            return {
                "app_id": surface.app_id,
                "label": surface.spoken_label,
                "is_browser": surface.is_browser,
                "is_home_base": surface.is_home_base,
            }
        except Exception as e:
            log.debug("[PlatformLinux] frontmost query failed: %s", e)
            return {}

    def capture_screen(self, save_path: Optional[Path] = None) -> Optional[Path]:
        dest = save_path or (Path.home() / "Desktop" / f"alfred_shot_{int(time.time())}.png")
        for cmd in [["maim", str(dest)], ["grim", str(dest)], ["gnome-screenshot", "-f", str(dest)]]:
            if shutil.which(cmd[0]):
                try:
                    res = subprocess.run(cmd, capture_output=True, timeout=5)
                    if res.returncode == 0 and dest.exists():
                        return dest
                except Exception:
                    pass
        return None

    def set_volume(self, pct: int) -> bool:
        try:
            vol = max(0, min(100, int(pct)))
            subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{vol}%"], capture_output=True, timeout=3)
            return True
        except Exception as e:
            log.debug("[PlatformLinux] set_volume failed: %s", e)
            return False

    def get_volume(self) -> Optional[int]:
        try:
            r = subprocess.run(["pactl", "get-sink-volume", "@DEFAULT_SINK@"],
                               capture_output=True, text=True, timeout=3)
            import re
            m = re.search(r"(\d+)%", r.stdout)
            return max(0, min(100, int(m.group(1)))) if m else None
        except Exception:
            return None

    def pause_audio(self) -> bool:
        if shutil.which("playerctl"):
            try:
                subprocess.run(["playerctl", "pause"], capture_output=True, timeout=2)
                return True
            except Exception:
                pass
        return False

    def resume_audio(self) -> bool:
        if shutil.which("playerctl"):
            try:
                subprocess.run(["playerctl", "play"], capture_output=True, timeout=2)
                return True
            except Exception:
                pass
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
