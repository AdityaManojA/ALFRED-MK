# ALFRED-MK-V: Cross-Platform Parity (macOS + Linux)
## Phase 1 Implementation Notes

**Corpus & Graph References:**
- `core/platform/base.py` (`PlatformBackend` abstract interface)
- `core/platform/win.py` (`WindowsPlatformBackend`)
- `core/platform/mac.py` (`MacPlatformBackend`)
- `core/platform/linux.py` (`LinuxPlatformBackend`)
- `core/platform/__init__.py` (`get_backend` factory)

---

## 1. Centralized OS Dispatch Architecture

We created the centralized `core/platform/` abstraction layer implementing:
- `window_flags()`: Returns frameless and stay-on-top flags tailored per OS.
- `make_toplevel(widget)`: Establishes top-level floating window behavior.
- `tts_speak(text, voice, speed)`:
  - Windows: SAPI / PowerShell / pyttsx3 fallback.
  - macOS: Native `say -v Daniel -r <rate>` synthesis.
  - Linux: `espeak-ng`, `espeak`, or `piper` CLI dispatch.
- `stt_listen()`: Microphone stream interface.
- `frontmost()`: Queries OS foreground application via `MacPlatformReader` / `LinuxPlatformReader` / `WinPlatformReader`.
- `capture_screen(save_path)`: Native OS screen capture (`screencapture` on Mac, `maim`/`grim`/`gnome-screenshot` on Linux, `mss` on Windows).
- `set_volume(pct)` / `get_volume()`: Volume controls using `osascript` (macOS), `pactl` (Linux), and `pycaw` (Windows).
- `pause_audio()` / `resume_audio()`: Media pause using `playerctl` on Linux, AppleScript on Mac, `WM_APPCOMMAND` on Windows.
- `paste(text)` / `hotkey(*keys)`: Cross-platform input automation.

---

## 2. Unit Testing & Verification

- Tested backend resolution and platform instantiation across simulated OS targets (`win32`, `darwin`, `linux`) in `tests/test_crossplatform_backend.py`.
