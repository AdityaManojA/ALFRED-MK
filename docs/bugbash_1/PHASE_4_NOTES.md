# Phase 4 — Linux PortAudio Crash (Bug 4)

## Root Cause Analysis
On Linux (Debian / Ubuntu / Raspberry Pi OS), installing Python package `sounddevice` succeeds via pip, but `sounddevice` relies on the C-library `libportaudio.so.2` from APT (`portaudio19-dev`). When missing, importing `sounddevice` raises `OSError: PortAudio library not found`, resulting in an unhandled crash traceback on startup.

## Graphify Nodes Referenced
- `core/audio_portaudio.py` (new module)
- `main.py [src=main.py]`
- `core/tts/engine_default.py [src=core/tts/engine_default.py]`
- `core/audio/stream.py [src=core/audio/stream.py]`
- `setup.py [src=setup.py]`
- `install.sh` (new script)
- `tests/test_linux_portaudio.py [src=tests/test_linux_portaudio.py]`

## Changes Made
1. **Named Constant (`core/audio_portaudio.py`)**:
   - `PORTAUDIO_MISSING_BANNER`: Highly visible ANSI red colorized terminal banner instructing the user to run `sudo apt-get update && sudo apt-get install portaudio19-dev python3-pyaudio`.
2. **Graceful Exception Handling**:
   - Implemented `handle_portaudio_os_error(e: OSError)` in `core/audio_portaudio.py`.
   - Wrapped top-level and entry-point `sounddevice` imports in `main.py`, `core/tts/engine_default.py`, and `core/audio/stream.py` with `try...except OSError as e` blocks.
   - If `portaudio` is found in the exception string, displays the instruction banner and exits gracefully with `sys.exit(1)` rather than dumping an unhandled stack trace.
3. **Setup and Installer Scripts**:
   - Updated `setup.py`: added `_check_and_install_linux_audio_deps()` to detect Linux systems, inspect for `portaudio` C-library, and auto-install via `sudo apt-get` if available.
   - Created `install.sh`: Linux automated bootstrap script that installs `portaudio19-dev`, `python3-pyaudio`, `pulseaudio-utils`, `xdotool`, and executes `setup.py`.
4. **Unit Tests**:
   - Created `tests/test_linux_portaudio.py` testing banner content, clean exit code `1`, and non-PortAudio exception passthrough.
   - All tests passed.

## Verification
- Unit test suite: `py -3.12 -m unittest tests/test_linux_portaudio.py` -> 3 tests OK (0.001s).
