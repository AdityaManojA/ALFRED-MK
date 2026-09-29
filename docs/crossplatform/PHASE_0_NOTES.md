# ALFRED-MK-V: Cross-Platform Parity (macOS + Linux)
## Phase 0 Reconnaissance Notes

**Corpus & Graph References:**
- `graphify-out/GRAPH_REPORT.md` (Commit: `08eca974`)
- Nodes: `WinPlatformReader`, `MacPlatformReader`, `LinuxPlatformReader`, `BasePlatformReader`, `HudVideoSurface`, `MinimizedHudOverlay`, `raise_overlay`, `LocalTTSManager`, `LocalSTTManager`, `capture_screen`, `window_manager.py`, `computer_settings.py`, `computer_control.py`

---

## 1. OS Gates & Imports Mapping

### OS Branches & System Calls:
| Component / File | Current OS Checks / Native Calls | Node / Symbol |
| :--- | :--- | :--- |
| `core/sentry/focus/reader.py` | `sys.platform == "win32"` / `"darwin"` / Linux fallback | `get_platform_reader` |
| `core/sentry/focus/platform/win.py` | `ctypes.windll.user32`, `uiautomation`, `win32gui`, `win32process` | `WinPlatformReader` |
| `core/sentry/focus/platform/mac.py` | `lsappinfo`, `osascript` (AppleScript for Chrome/Brave/Edge URL) | `MacPlatformReader` |
| `core/sentry/focus/platform/linux.py` | `xdotool`, `xprop`, `_NET_WM_PID`, Wayland detection | `LinuxPlatformReader` |
| `actions/window_manager.py` | `sys.platform == "win32"` guarded `user32` EnumWindows / SetWindowPos | `window_manager_action` |
| `actions/computer_settings.py` | `platform.system()` → `osascript` (Mac), `pactl`/`brightnessctl` (Linux), PowerShell/WMI (Win) | `volume_up`, `brightness_get`, etc. |
| `actions/computer_control.py` | `pyautogui`, `pyperclip`, `_safe_screenshot_path` | `_hotkey`, `_clipboard_paste` |
| `actions/screen_processor.py` | `sys.platform.startswith("win")` (`win32gui`, `win32process`), `mss`, `cv2`, `PIL` | `capture_screen` |
| `actions/spotify_control.py` | `ctypes.windll.user32` WM_APPCOMMAND on Windows; `pyautogui` fallback | `_send_app_command` |
| `ui.py` | `SetCurrentProcessExplicitAppUserModelID` on win32; `sys.platform == "win32"` taskbar icon injection | `JarvisUI`, `MainWindow.set_app_icon` |

---

## 2. Visual HUD Backend & Multimedia

### Pipeline & Windowing:
- **Qt Multimedia Framework:** Uses `PyQt6.QtMultimedia.QMediaPlayer` and `QAudioOutput`, outputting to `QVideoWidget` inside `HudVideoSurface` (`core/hud_video/surface.py`).
- **Decoder Plugins per OS:**
  - **Windows:** Media Foundation (`H264 Encoder MFT`, `HEVCVideoExtensionEncoder`, `WMVideoDecoder`).
  - **macOS:** AVFoundation backend natively handles VP9/H.264/AAC.
  - **Linux:** GStreamer backend (`gst-plugins-base`, `gst-plugins-good`, `gst-plugins-bad`, `gst-libav`).
- **Surface Construction:** `HudVideoSurface` is a normal child widget in slot 2 of `MainWindow._hud_cam_stack` (QStackedWidget).
- **Translucency & Layering:** Child widgets over native surfaces are elevated via `core/hud_video/layering.py` using `raise_overlay(widget, parent)`.

---

## 3. Minimised HUD

### Implementation Details:
- **Class:** `MinimizedHudOverlay` (`ui.py` line 3883).
- **Window Flags:**
  ```python
  Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
  ```
- **Attributes:** `WA_TranslucentBackground`, `WA_ShowWithoutActivating`.
- **Geometry & Persistence:** Saved in `config/hud_overlay_pos.json`. Restores using `QApplication.screenAt(position)` and `screen.availableGeometry()`.
- **Platform Behavior:**
  - On macOS: Frameless window with `WindowStaysOnTopHint` floats over regular windows. For full-screen native apps, floating windows may be assigned to active Spaces.
  - On Linux: Under tiling WMs (i3, sway, bspwm), `FramelessWindowHint` + `WindowStaysOnTopHint` may require WM rules (`for_window [class="alfred"] floating enable`).

---

## 4. Z-Order & Layering

### Single Source of Truth (`core/hud_video/layering.py`):
```python
Z_VISUAL_HUD: int = 10
Z_HUD_BUTTONS: int = 20
Z_DROPDOWN_CARD_TOAST: int = 30
Z_SETTINGS_MODAL: int = 40
```
- Overlays (`RemoteKeyOverlay`, `AudioDeviceOverlay`, `MemoryOverlay`, `ConfirmBanner`, `SetupOverlay`, `CapabilitiesOverlay`, `PluginManagerOverlay`) inherit `_HudOverlay` or use `raise_overlay()`.
- Top-level `Tool` / `Window` separation ensures dropdowns and modals paint cleanly over native QVideoWidget surfaces on all compositors (Windows DWM, macOS Quartz Compositor, Linux Wayland/X11 Compositor).

---

## 5. TTS / STT Backends

### Speech-to-Text (STT):
- **Implementation:** `LocalSTTManager` (`core/local_stt.py`) + `sounddevice` microphone stream.
- **Engines:** Faster-Whisper / Whisper (Cross-platform) & Vosk (Cross-platform).
- **Audio Capture:** Uses `sounddevice` (PortAudio C-bindings bundled with wheels on Win/Mac/Linux).

### Text-to-Speech (TTS):
- **Engines:**
  - **EdgeTTS:** Cloud streaming (`edge-tts` asyncio, cross-platform).
  - **Kokoro:** Local neural model (`kokoro-onnx` / `kokoro >= 0.9`, PyTorch/ONNX CPU/GPU, cross-platform).
  - **ElevenLabs:** Cloud API (cross-platform).
  - **Native OS Fallback:**
    - macOS: `say -r <rate> "<text>"`
    - Linux: `espeak-ng` or `piper`
    - Windows: SAPI via `pyttsx3` / sounddevice

### Audio Ducking:
- **Audio Core:** `TronScoreBackgroundPlayer` (`ui.py`) controls internal background track volume smoothly via QAudioOutput volume interpolation during speech.
- **System Audio Ducking:**
  - Windows: `pycaw` (WASAPI endpoint volume).
  - macOS: `osascript` (AppleScript system output volume).
  - Linux: `pactl set-sink-volume @DEFAULT_SINK@`.

---

## 6. System APIs Matrix

| Feature | Windows Backend | macOS Backend | Linux Backend | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Frontmost App / Tab** | `WinPlatformReader` (Win32 + UIAutomation) | `MacPlatformReader` (`lsappinfo` + AppleScript) | `LinuxPlatformReader` (`xdotool`/`xprop` + Wayland) | **Parity Ready** |
| **Screen Capture** | `mss` / `cv2` | `mss` + `screencapture -x` fallback | `mss` + `maim`/`grim` fallback | **Parity Ready** |
| **System Audio Pause** | `pycaw` / `WM_APPCOMMAND` | `osascript` (`tell application "Music" to pause`) | `playerctl pause` / `pactl` | **Needs P1 Shim** |
| **Input Automation** | `pyautogui` | `pyautogui` (needs Accessibility TCC) | `pyautogui` (X11 / Wayland) | **Parity Ready** |
| **Clipboard** | `pyperclip` + `QClipboard` | `pyperclip` (`pbcopy`/`pbpaste`) + `QClipboard` | `pyperclip` (`xclip`/`wl-copy`) + `QClipboard` | **Parity Ready** |
| **Window Management** | `actions/window_manager.py` (Win32) | Stubs / `osascript` | Stubs / `wmctrl` | **Needs P1 Shim** |

---

## 7. Persistence Paths

- **Current Config Directory:** `CONFIG_DIR = Path.home() / ".alfred"` or local project `config/` / `memory/`.
- **Absolute Paths Verification:**
  - Hardcoded Windows absolute paths (`D:/`, `C:\`) have been cleaned in favor of `Path(__file__).resolve().parent` and `Path.home()`.
  - All temp files and screenshot saves resolve relative to `Path.home() / "Desktop"` or project scratch directories.

---

## 8. External Dependencies & Tools

- `sounddevice`: Bundles PortAudio binaries on macOS/Linux wheels.
- `yt-dlp`: Pure Python CLI / library.
- `ffmpeg`: Detected via `shutil.which("ffmpeg")` (optional for local format transcoding).
- `mss`: Pure Python + X11/Quartz bindings for screen capture.

---

## Exact Files to Implement / Modify Across Phases:

1. **`core/platform/` (P1)**:
   - `core/platform/__init__.py`
   - `core/platform/base.py` (Abstract `PlatformBackend`)
   - `core/platform/win.py`
   - `core/platform/mac.py`
   - `core/platform/linux.py`
2. **`core/hud_video/` (P2)**:
   - `core/hud_video/surface.py` (GStreamer & AVFoundation error reporting / decode checks)
3. **`ui.py` (P3, P4)**:
   - `MinimizedHudOverlay` (Screen bounds, window level & WM hint compatibility)
   - `JarvisUI` (AppUserModelID and cross-platform process isolation)
4. **`core/tts/` & `core/local_stt.py` (P4)**:
   - Platform backend hook for OS-native speech fallbacks
5. **`actions/` (P5)**:
   - `actions/computer_settings.py` (Centralise OS dispatch via `core/platform/`)
   - `actions/window_manager.py` (Clean cross-platform fallback)
