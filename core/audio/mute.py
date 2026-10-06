"""
core/audio/mute.py — System microphone mute control and state interrogation.
Supports Windows (pycaw), Linux (pactl), and macOS (osascript).
"""
from __future__ import annotations

import logging
import platform
import subprocess
import sys
from typing import Callable, Optional

logger = logging.getLogger("core.audio.mute")

# ── Named Constants ──────────────────────────────────────────────────────────
MUTE_CONFIRMATION_SPEECH: str = (
    "Microphone muted, sir. You will need to unmute manually to speak to me again."
)
MUTE_OS_LINUX_CMD: list[str] = ["pactl", "set-source-mute", "@DEFAULT_SOURCE@", "1"]
UNMUTE_OS_LINUX_CMD: list[str] = ["pactl", "set-source-mute", "@DEFAULT_SOURCE@", "0"]
MUTE_OS_MAC_CMD: list[str] = ["osascript", "-e", "set volume input volume 0"]
UNMUTE_OS_MAC_CMD: list[str] = ["osascript", "-e", "set volume input volume 100"]

_OS = platform.system()


def mute_system_microphone() -> bool:
    """
    Mute the primary system audio capture/microphone hardware device.
    - Windows: Uses pycaw AudioUtilities.GetMicrophone().
    - Linux: Uses pactl set-source-mute.
    - macOS: Sets input volume to 0.
    """
    sys_name = platform.system()
    if sys_name == "Windows":
        try:
            import comtypes
            comtypes.CoInitialize()
        except Exception:
            pass
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL

            mic = AudioUtilities.GetMicrophone()
            if mic:
                iid = getattr(IAudioEndpointVolume, "_iid_", None)
                interface = mic.Activate(iid, CLSCTX_ALL, None) if iid else mic
                try:
                    volume = interface.QueryInterface(IAudioEndpointVolume)
                except Exception:
                    volume = interface
                volume.SetMute(1, None)
                logger.info("[Mute] System microphone muted via pycaw.")
                return True
        except Exception as exc:
            logger.error(f"[Mute] Failed to mute microphone on Windows: {exc}")
            return False
    elif sys_name == "Linux":
        try:
            r = subprocess.run(MUTE_OS_LINUX_CMD, capture_output=True, timeout=2)
            if r.returncode == 0:
                logger.info("[Mute] Linux microphone muted via pactl.")
                return True
        except Exception as exc:
            logger.error(f"[Mute] Failed to mute microphone on Linux: {exc}")
            return False
    elif sys_name == "Darwin":
        try:
            r = subprocess.run(MUTE_OS_MAC_CMD, capture_output=True, timeout=2)
            if r.returncode == 0:
                logger.info("[Mute] macOS microphone muted via osascript.")
                return True
        except Exception as exc:
            logger.error(f"[Mute] Failed to mute microphone on macOS: {exc}")
            return False
    return False


def unmute_system_microphone() -> bool:
    """Unmute the primary system audio capture/microphone hardware device."""
    sys_name = platform.system()
    if sys_name == "Windows":
        try:
            import comtypes
            comtypes.CoInitialize()
        except Exception:
            pass
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL

            mic = AudioUtilities.GetMicrophone()
            if mic:
                iid = getattr(IAudioEndpointVolume, "_iid_", None)
                interface = mic.Activate(iid, CLSCTX_ALL, None) if iid else mic
                try:
                    volume = interface.QueryInterface(IAudioEndpointVolume)
                except Exception:
                    volume = interface
                volume.SetMute(0, None)
                logger.info("[Mute] System microphone unmuted via pycaw.")
                return True
        except Exception as exc:
            logger.error(f"[Mute] Failed to unmute microphone on Windows: {exc}")
            return False
    elif sys_name == "Linux":
        try:
            r = subprocess.run(UNMUTE_OS_LINUX_CMD, capture_output=True, timeout=2)
            return r.returncode == 0
        except Exception:
            return False
    elif sys_name == "Darwin":
        try:
            r = subprocess.run(UNMUTE_OS_MAC_CMD, capture_output=True, timeout=2)
            return r.returncode == 0
        except Exception:
            return False
    return False


def is_microphone_muted() -> bool:
    """
    Check if the system microphone is currently muted or set to 0 volume.
    Used by HUD system monitor to toggle visual indicators.
    """
    sys_name = platform.system()
    if sys_name == "Windows":
        try:
            import comtypes
            comtypes.CoInitialize()
        except Exception:
            pass
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL

            mic = AudioUtilities.GetMicrophone()
            if mic:
                iid = getattr(IAudioEndpointVolume, "_iid_", None)
                interface = mic.Activate(iid, CLSCTX_ALL, None) if iid else mic
                try:
                    volume = interface.QueryInterface(IAudioEndpointVolume)
                except Exception:
                    volume = interface
                if volume.GetMute():
                    return True
                # Check if level is 0
                return volume.GetMasterVolumeLevelScalar() <= 0.001
        except Exception:
            pass
    elif sys_name == "Linux":
        try:
            r = subprocess.run(["pactl", "get-source-mute", "@DEFAULT_SOURCE@"], capture_output=True, text=True, timeout=1)
            if "yes" in r.stdout.lower():
                return True
            r_vol = subprocess.run(["pactl", "get-source-volume", "@DEFAULT_SOURCE@"], capture_output=True, text=True, timeout=1)
            if "/ 0%" in r_vol.stdout:
                return True
        except Exception:
            pass
    elif sys_name == "Darwin":
        try:
            r = subprocess.run(["osascript", "-e", "input volume of (get volume settings)"], capture_output=True, text=True, timeout=1)
            if r.returncode == 0 and r.stdout.strip().isdigit():
                return int(r.stdout.strip()) == 0
        except Exception:
            pass
    return False


def execute_mute_me(speak_fn: Optional[Callable[[str], None]] = None) -> str:
    """
    Execute the 'Mute Me' intent:
    1. Delivers confirmation speech: 'Microphone muted, sir. You will need to unmute manually to speak to me again.'
    2. Immediately triggers hardware system microphone mute.
    3. Returns confirmation string.
    """
    if speak_fn:
        try:
            speak_fn(MUTE_CONFIRMATION_SPEECH)
        except Exception as exc:
            logger.debug(f"[Mute] speak_fn error: {exc}")
    else:
        try:
            from core.tts import get_engine
            engine = get_engine()
            engine.speak(MUTE_CONFIRMATION_SPEECH)
        except Exception as exc:
            logger.debug(f"[Mute] engine.speak error: {exc}")

    mute_system_microphone()
    return MUTE_CONFIRMATION_SPEECH
