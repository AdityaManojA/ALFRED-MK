# Phase 5 — "Mute Me" Intent (Feature 5)

## Feature Overview
Added native system-wide microphone muting triggered by voice commands such as `"mute me"`, `"mute my mic"`, `"mute microphone"`. The assistant responds verbally with *"Microphone muted, sir. You will need to unmute manually to speak to me again."*, then engages OS hardware-level input capture muting across Windows, Linux, and macOS. The HUD periodically checks microphone mute / volume level and renders a visual silence indicator with a red crossed-out mic icon (`⊘`).

## Graphify Nodes Referenced
- `core/audio/mute.py` (new module)
- `mute_system_microphone() [src=core/audio/mute.py]`
- `unmute_system_microphone() [src=core/audio/mute.py]`
- `is_microphone_muted() [src=core/audio/mute.py]`
- `execute_mute_me() [src=core/audio/mute.py]`
- `core/audio/__init__.py [src=core/audio/__init__.py]`
- `core/intents/router.py [src=core/intents/router.py]`
- `actions/computer_settings.py [src=actions/computer_settings.py]`
- `main.py [src=main.py: _run_system_monitor]`
- `ui.py [src=ui.py: MainWindow.set_hardware_mic_muted]`
- `tests/test_audio_mute.py [src=tests/test_audio_mute.py]`

## Changes Made
1. **Created `core/audio/mute.py`**:
   - Named constants defined at top of file:
     - `MUTE_CONFIRMATION_SPEECH = "Microphone muted, sir. You will need to unmute manually to speak to me again."`
     - `MUTE_OS_LINUX_CMD = ["pactl", "set-source-mute", "@DEFAULT_SOURCE@", "1"]`
     - `UNMUTE_OS_LINUX_CMD = ["pactl", "set-source-mute", "@DEFAULT_SOURCE@", "0"]`
     - `MUTE_OS_MAC_CMD = ["osascript", "-e", "set volume input volume 0"]`
     - `UNMUTE_OS_MAC_CMD = ["osascript", "-e", "set volume input volume 100"]`
   - Windows: Used `pycaw.AudioUtilities.GetMicrophone()` with `IAudioEndpointVolume.SetMute(1, None)`.
   - Linux: Used `pactl set-source-mute @DEFAULT_SOURCE@ 1`.
   - macOS: Used `osascript set volume input volume 0`.
   - Implemented `is_microphone_muted()` to query Windows `GetMute()` / scalar volume, Linux `pactl get-source-mute`, and macOS input volume.
   - Implemented `execute_mute_me()` to deliver confirmation speech followed by hardware mute.
2. **Intent Routing Fast-Path (`core/intents/router.py`)**:
   - Added `(re.compile(r"^(mute me|mute my mic|mute( the)? microphone)\b", re.I), "mute_me", "mute_system_microphone")` ahead of general media mute in `FAST_PATTERNS`.
3. **Action Mapping (`actions/computer_settings.py`)**:
   - Added `mute_microphone()`, `unmute_microphone()`, and `toggle_microphone()`.
   - Connected `mute_mic`, `unmute_mic`, `toggle_mic`, `mute_me`, `mute_microphone` in `ACTION_MAP`.
4. **HUD Visual Indicator Synchronization (`ui.py` & `main.py`)**:
   - Added `set_hardware_mic_muted(muted: bool)` on `MainWindow` and `AlfredUI`.
   - Updated `main.py: _run_system_monitor` loop to periodically query `is_microphone_muted()` and update the HUD, rendering neon red `[ ⊘ ] SILENCE PROTOCOL : ENGAGED // COWL MUTED` and `C.MUTED_C` status banner.
5. **Unit Tests**:
   - Created `tests/test_audio_mute.py` verifying cross-platform muting, verbal confirmation ordering, fast-path intent matching, and alias resolution.
   - All 8 tests passed.

## Verification
- Unit test suite: `py -3.12 -m unittest tests/test_audio_mute.py` -> 8 tests OK (0.075s).
