# ALFRED-MK-V: Cross-Platform Parity (macOS + Linux)
## Phase 5 Implementation Notes: System API Parity

**Corpus & Graph References:**
- `core/platform/` (`PlatformBackend`)
- `actions/computer_settings.py` (`volume_up`, `volume_down`, `volume_get`, `brightness_get`)
- `core/sentry/focus/reader.py` (`MacPlatformReader`, `LinuxPlatformReader`, `WinPlatformReader`)

---

## 1. System Control & Media Dispatch

- Master volume inspection (`volume_get()`) and adjustment (`volume_up()`, `volume_down()`) now route through the unified `PlatformBackend` interface.
- Screen capture routes through `backend.capture_screen()` with fallbacks to `screencapture -x` (macOS), `maim`/`grim` (Linux), and `mss` (Windows).
- System audio pause/resume control routes through `playerctl` (Linux), AppleScript (macOS), and `WM_APPCOMMAND` (Windows).
