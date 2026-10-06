"""
core/audio_portaudio.py — Safe sounddevice / PortAudio loader with clean Linux diagnostic banner.
"""
from __future__ import annotations

import sys
from typing import Any

# ── Named Constants ──────────────────────────────────────────────────────────
PORTAUDIO_MISSING_BANNER: str = """\033[91m
=============================================================
CRITICAL DEPENDENCY MISSING: PortAudio
ALFRED requires the system audio library to use the microphone.

To fix this on Linux (Ubuntu/Debian), run:
    sudo apt-get update
    sudo apt-get install portaudio19-dev python3-pyaudio
=============================================================\033[0m"""


def handle_portaudio_os_error(e: OSError) -> bool:
    """
    Check if an OSError corresponds to a missing PortAudio shared library.
    If so, print the critical dependency banner and exit gracefully with code 1.
    Returns True if handled (before exiting), or False if unrelated OSError.
    """
    err_str = str(e).lower()
    if "portaudio" in err_str:
        sys.stderr.write(PORTAUDIO_MISSING_BANNER + "\n")
        sys.stderr.flush()
        sys.exit(1)
    return False


def safe_import_sounddevice() -> Any:
    """
    Import sounddevice safely. On missing PortAudio C-library, exits gracefully
    with the diagnostic terminal banner instead of a cascading traceback.
    """
    try:
        import sounddevice as sd
        return sd
    except OSError as e:
        handle_portaudio_os_error(e)
        raise
