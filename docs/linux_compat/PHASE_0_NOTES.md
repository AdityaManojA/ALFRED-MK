# ALFRED-MK-V — Linux Compatibility + Application Selection
## Phase 0 Reconnaissance & Audit Report

**Date:** 2026-10-06  
**Status:** Recon Complete (No code changes in P0)  
**Acceptance Target:** Detailed platform matrix, dependency map, intent routes, Spotify readiness audit, screenshot paths, and proposed test target matrix.

---

## 1. Current Platform Support & OS Conditionals

### 1.1 OS Conditionals & Platform Split
The repository actively discriminates OS environments using `sys.platform` and `platform.system()` across core drivers:
- **`core/platform/`** ([`core/platform/__init__.py:20-29`](file:///d:/Projects/Alfred-Mark-VIII/core/platform/__init__.py#L20-L29), `NODE: core_platform_init_get_backend`):
  - Returns `WindowsPlatformBackend` on `win32`, `MacPlatformBackend` on `darwin`, and `LinuxPlatformBackend` (`NODE: core_platform_linux_linuxplatformbackend`) on Linux.
- **`core/browser/platform/`** ([`core/browser/platform/linux.py:33`](file:///d:/Projects/Alfred-Mark-VIII/core/browser/platform/linux.py#L33), `NODE: core_browser_platform_linux_linuxbrowserdriver`):
  - Driver dispatcher for browser control and tab closing.
- **`core/sentry/focus/platform/`** ([`core/sentry/focus/platform/linux.py:29`](file:///d:/Projects/Alfred-Mark-VIII/core/sentry/focus/platform/linux.py#L29), `NODE: core_sentry_focus_platform_linux_linuxplatformreader`):
  - Inspects frontmost window on X11 and Wayland (hyprctl only).
- **`core/media/suppress/`** ([`core/media/suppress/linux.py:6`](file:///d:/Projects/Alfred-Mark-VIII/core/media/suppress/linux.py#L6)):
  - Defines `LinuxSuppressor(NullSuppressor)` — currently an empty placeholder class with zero implementation (`NODE: core_media_suppress_base_nullsuppressor`).

### 1.2 Windows-Only Imports & APIs
The following libraries are declared with `sys_platform == "win32"` in [`requirements.txt`](file:///d:/Projects/Alfred-Mark-VIII/requirements.txt#L57-L64) and called in Windows code paths:
- `pywin32` / `win32gui`, `win32process`, `win32con`, `win32api`: Used in [`actions/screen_processor.py:28`](file:///d:/Projects/Alfred-Mark-VIII/actions/screen_processor.py#L28) for window handle inspection and [`core/platform/win.py`](file:///d:/Projects/Alfred-Mark-VIII/core/platform/win.py).
- `pycaw`: Windows Core Audio APIs for volume and session manipulation in [`core/media/suppress/win.py:21`](file:///d:/Projects/Alfred-Mark-VIII/core/media/suppress/win.py#L21) (`NODE: core_media_suppress_win_windowssuppressor`).
- `winsdk`: Windows Runtime APIs for SMTC (System Media Transport Controls) in [`core/media/suppress/win.py:26`](file:///d:/Projects/Alfred-Mark-VIII/core/media/suppress/win.py#L26).
- `wmi`: Windows Management Instrumentation used in [`actions/system_monitor.py:165`](file:///d:/Projects/Alfred-Mark-VIII/actions/system_monitor.py#L165) for thermal zones.
- `pygetwindow`: Used for window geometry on Windows.
- `win10toast`: Toast notifications on Windows.
- `comtypes`: COM interfaces for audio and shell shortcuts.

### 1.3 macOS-Only APIs
- `osascript` (AppleScript) and `Quartz` (`CGWindowListCopyWindowInfo`) in [`actions/screen_processor.py:177`](file:///d:/Projects/Alfred-Mark-VIII/actions/screen_processor.py#L177) and [`core/platform/mac.py`](file:///d:/Projects/Alfred-Mark-VIII/core/platform/mac.py).

### 1.4 Linux-Specific Assumptions & External Executables
Existing Linux code paths assume the availability of specific command-line utilities without verified fallback:
- **Audio control:** `pactl` ([`core/platform/linux.py:92`](file:///d:/Projects/Alfred-Mark-VIII/core/platform/linux.py#L92)) for `set-sink-volume` and `get-sink-volume`.
- **Media control:** `playerctl` ([`core/platform/linux.py:111`](file:///d:/Projects/Alfred-Mark-VIII/core/platform/linux.py#L111)) for MPRIS playback pause/resume.
- **Audio ducking:** `pulsectl` Python library ([`core/audio_ducker.py:303`](file:///d:/Projects/Alfred-Mark-VIII/core/audio_ducker.py#L303)) accessing the PulseAudio/PipeWire-pulse socket.
- **Window queries & X11 Automation:** `xdotool`, `wmctrl`, `xprop` ([`core/browser/platform/linux.py:42`](file:///d:/Projects/Alfred-Mark-VIII/core/browser/platform/linux.py#L42), [`core/sentry/focus/platform/linux.py:44`](file:///d:/Projects/Alfred-Mark-VIII/core/sentry/focus/platform/linux.py#L44), [`actions/screen_processor.py:218`](file:///d:/Projects/Alfred-Mark-VIII/actions/screen_processor.py#L218)).
- **Screenshots:** `maim`, `grim`, `gnome-screenshot` ([`core/platform/linux.py:79`](file:///d:/Projects/Alfred-Mark-VIII/core/platform/linux.py#L79)), and `mss` (X11 Xlib client) in [`actions/screen_processor.py:47`](file:///d:/Projects/Alfred-Mark-VIII/actions/screen_processor.py#L47).
- **URL Launching:** `xdg-open` ([`core/browser/platform/linux.py:120`](file:///d:/Projects/Alfred-Mark-VIII/core/browser/platform/linux.py#L120)).
- **TTS fallbacks:** `espeak-ng`, `espeak`, `piper` ([`core/platform/linux.py:39-56`](file:///d:/Projects/Alfred-Mark-VIII/core/platform/linux.py#L39-L56)).
- **Setup script assumption:** [`setup.py:108`](file:///d:/Projects/Alfred-Mark-VIII/setup.py#L108) invokes `sudo apt-get install -y portaudio19-dev python3-pyaudio pulseaudio-utils` automatically, violating non-interactive / non-sudo principles.
- **PortAudio failure mode:** [`core/audio_portaudio.py:31`](file:///d:/Projects/Alfred-Mark-VIII/core/audio_portaudio.py#L31) (`NODE: core_audio_portaudio_handle_portaudio_os_error`) executes `sys.exit(1)`, crashing application launch instead of allowing graceful fallback to typed chat / degraded mode.

---

## 2. Feature Inventory Matrix

| Feature | Entry Point | Backend / Subsystem | Linux Dependencies | Status on Linux |
| :--- | :--- | :--- | :--- | :--- |
| **App Boot & GUI** | `main.py` -> `MainWindow` | PyQt6 (`ui.py`) | `libGL.so`, `libegl.so`, Qt platform plugin (`xcb` or `wayland`) | **PARTIAL** (Fails if PortAudio absent on import) |
| **Full HUD / Mini HUD** | `ui.py` (`MainWindow`) | QPainter software rasterization / translucent frameless | X11 compositor (picom/mutter) or Wayland compositor | **WORKS** (Requires compositing for translucency) |
| **Theme / Visualizer** | `ui.py` (`_render_emblem_frame`) | Pure Python NumPy + QPainter math | `numpy` (CPU software render) | **WORKS** |
| **Microphone / Input** | `main.py:_listen_audio` | `sounddevice` / PortAudio C-lib | `libportaudio.so.2` | **PARTIAL** (Hard crash via `sys.exit(1)` if missing) |
| **Wake Word** | `core/wake_word.py` | `openwakeword` + ONNXRuntime | `onnxruntime`, CPU SIMD | **WORKS** (Models downloaded to `models/`) |
| **STT (Speech-to-Text)**| `main.py` -> Gemini Live WebSocket | PCM 16kHz stream | Network connectivity to Google API | **WORKS** |
| **TTS (Text-to-Speech)**| `core/tts/` | EdgeTTS / ElevenLabs / Kokoro | Python `requests`, network, or local `piper`/`espeak` | **WORKS** |
| **Audio Ducking** | `core/audio_ducker.py` | `pulsectl` (PulseAudio / PipeWire) | `pulsectl`, active PulseAudio / PipeWire pulse daemon | **PARTIAL** (Works on Pulse/Pipewire; no ALSA-only fallback) |
| **System Volume Controls** | `core/platform/linux.py` | `pactl` subprocess | `pulseaudio-utils` (`pactl`) | **PARTIAL** (Fails if `pactl` not installed) |
| **Media Pause / Resume** | `core/platform/linux.py` | `playerctl` subprocess | `playerctl` CLI | **PARTIAL** (Fails if `playerctl` not installed; `LinuxSuppressor` empty) |
| **Browser Detection** | `actions/browser_control.py` | `shutil.which` + process search | Common desktop binaries (`google-chrome`, `firefox`, etc.) | **PARTIAL** (Hardcoded binary names, no XDG desktop entry lookup) |
| **Open URL** | `actions/browser_control.py` | `xdg-open` / `webbrowser` | `xdg-utils` | **WORKS** |
| **Tab Closing / Control**| `core/browser/platform/linux.py` | `xdotool` + `wmctrl` (X11) | `xdotool`, `wmctrl` | **PARTIAL** (Fails completely on Wayland sessions) |
| **Playwright Automation**| `actions/browser_control.py` | Playwright async Chromium/Firefox | Playwright system browser deps (`libnss3`, etc.) | **PARTIAL** (Requires downloaded playwright browsers; external attach unverified) |
| **Visual HUD Video** | `actions/hud_video.py` | Qt Multimedia / QMediaPlayer | GStreamer plugins (`gstreamer1.0-plugins-good`, etc.) | **PARTIAL** (Depends on host GStreamer codecs) |
| **Image Viewer** | `core/image_viewer.py` | PyQt6 QDialog / QLabel | Qt image format plugins | **WORKS** |
| **Screen Capture** | `actions/screen_processor.py` | `mss` (X11) / `grim` / `maim` | X11 Xlib or compositor CLI (`grim`) | **PARTIAL** (`mss` fails on Wayland; needs portal / grim fallback) |
| **Window Grounding Context**| `actions/screen_processor.py` | `xdotool` + `xprop` (X11) | `xdotool`, `xprop` | **PARTIAL** (Fails on Wayland; returns `Unknown`) |
| **Spotify Integration** | `actions/spotify_control.py` | Spotify Web API (`requests`) | Network + valid user OAuth tokens | **PARTIAL** (Ungated calls before token verification) |
| **Gmail / Workspace API**| `core/apis/registry.py` | Google OAuth REST API | Network + OAuth credentials | **WORKS** |
| **System Monitoring** | `actions/system_monitor.py` | `psutil` + `libnvidia-ml.so.1` | Linux `/proc`, `/sys/class/thermal`, NVIDIA driver | **WORKS** |
| **Process Controls** | `actions/process_manager.py` | `psutil` Process API | Standard POSIX signals (`SIGTERM`, `SIGKILL`) | **WORKS** |
| **Sentry Mode Focus** | `core/sentry/focus/` | `LinuxPlatformReader` | X11 `xdotool`/`xprop` or Wayland `hyprctl` | **PARTIAL** (Fails on GNOME/KDE Wayland) |
| **Scheduler** | `core/scheduler/` | Python thread timers | Standard library | **WORKS** |
| **Persistence / Config** | `memory/config_manager.py` | JSON / encrypted SQLite | Standard library / `cryptography` | **WORKS** |
| **Crash Reporting** | `core/crash_handler.py` | Native Qt dialog (`QMessageBox`) | PyQt6 | **WORKS** |

---

## 3. Linux Runtime Environment Analysis

### 3.1 Python & Packaging
- **Supported Python Range:** Python 3.11 – 3.13 ([`setup.py:26-27`](file:///d:/Projects/Alfred-Mark-VIII/setup.py#L26-L27)).
- **Installation Mechanism:** `pip install -r requirements.txt`.
- **System Library Traps:**
  - `sounddevice` links to system `libportaudio.so.2`. If absent, Python throws `OSError`.
  - `pulsectl` links to `libpulse.so.0`. PipeWire systems run `pipewire-pulse` emulation by default on modern distros.
  - PyQt6 dynamically loads host graphics libraries: `libGL.so.1`, `libegl.so.1`, and XCB or Wayland Qt platform plugins (`libqxcb.so`, `libqwayland.so`).

### 3.2 Display Server Divergence: Wayland vs X11
- **X11:**
  - `xdotool` and `wmctrl` can focus windows, list windows (`wmctrl -l`), query titles, and inject synthetic key events (`ctrl+w`).
  - `mss` can capture the root X11 window.
  - Window transparency (`WA_TranslucentBackground`) requires a compositor running (e.g. Mutter in GNOME, KWin in KDE, or Picom on standalone window managers).
- **Wayland:**
  - Direct window enumeration and global active-window querying are blocked by compositor isolation. `xdotool` and `wmctrl` fail.
  - `core/sentry/focus/platform/linux.py:103` attempts `hyprctl activewindow -j`, which only works on Hyprland. On GNOME Wayland or KDE Wayland, it fails.
  - `mss` cannot read pixels directly on Wayland; attempts produce black frames or `ScreenShotError`. External CLI `grim` works on wlroots compositors, but GNOME Wayland requires `gnome-screenshot` or the `org.freedesktop.portal.Screenshot` DBus portal.

---

## 4. Browser & Application Routing Analysis

### 4.1 Voice Intent Routing for "play", YouTube, Spotify, and Browsers
- **Dispatch Point:** [`main.py:2410`](file:///d:/Projects/Alfred-Mark-VIII/main.py#L2410) `_execute_tool(fc)` delegates tool calls emitted by Gemini Live.
- **Routing Rules in `core/prompt.txt`:**
  - "Play a song / play music / play [artist]" routes to `spotify_control`.
  - "Play on YouTube in a browser" or "Close tab" routes to `browser_control`.
  - "Play in the app / in the hud" routes to `hud_video`.
- **Collision Guards in `actions/spotify_control.py:837-846`:**
  - Checks if query contains "netflix" -> redirects to `core.pilots.netflix.actions`.
  - Checks if query contains "trailer" / "teaser" / "clip" -> redirects to `hud_video`.
  - Otherwise, directly dispatches `client.play(query=query)` without checking if Spotify is configured or authenticated!

### 4.2 Spotify Readiness Audit: Current vs Required
- **Current State:**
  - [`actions/spotify_control.py:368`](file:///d:/Projects/Alfred-Mark-VIII/actions/spotify_control.py#L368) has `has_user_authorization()` which simply checks `bool(self._refresh_token)`.
  - In `spotify_control(parameters)` ([line 800](file:///d:/Projects/Alfred-Mark-VIII/actions/spotify_control.py#L800)), there is **no readiness guard**. If called with `action='play'`, it immediately executes `client.play()`, which calls `client.search()`, triggering network calls and returning 401 Unauthorized or failure exceptions.
- **Required Readiness States (for P4):**
  - `NOT_CONFIGURED`: Missing `client_id` or `client_secret` in SecretStore/config.
  - `AUTH_REQUIRED`: Client ID/Secret present, but no OAuth user `refresh_token` stored.
  - `READY`: Valid client credentials and user refresh token available; capable of issuing authenticated calls.
  - `UNAVAILABLE`: Network failure or Spotify service unavailable.
  - **Hard Gate:** If not `READY`, zero calls to `api.spotify.com/v1/search` or playback endpoints must be made.

### 4.3 Settings & Preference Persistence Patterns
- **API Keys & Flags:** [`memory/config_manager.py`](file:///d:/Projects/Alfred-Mark-VIII/memory/config_manager.py) persists JSON key-value pairs to `config/api_keys.json` (e.g. `wake_word_enabled`, `brief_enabled`, `clipboard_monitor_enabled`).
- **Encrypted Credentials:** [`core/secrets/store.py`](file:///d:/Projects/Alfred-Mark-VIII/core/secrets/store.py) (`SecretStore`) persists sensitive tokens (`spotify.refresh_token`, `google.client_secret`) in encrypted SQLite `data/secrets.db`.
- **Remembered Application Choice Pattern (for P3):**
  - Store remembered choices in `config/api_keys.json` or `memory/config_manager.py` under a structured key (e.g. `preferred_applications: {"browser_youtube": "firefox.desktop"}`).

---

## 5. Screenshot & Verification Facilities
- **Primary Live Capture:** [`actions/screen_processor.py:372`](file:///d:/Projects/Alfred-Mark-VIII/actions/screen_processor.py#L372) `capture_screen(monitor=1)` captures monitor pixels and returns `ScreenCapturePayload(img_bytes, mime_type, window_context, payload)`.
- **Platform File Capture:** [`core/platform/linux.py:77`](file:///d:/Projects/Alfred-Mark-VIII/core/platform/linux.py#L77) `capture_screen(save_path)` tries `maim`, `grim`, and `gnome-screenshot`.
- **HUD Verification Path:** Screenshots for verification artifacts are stored under `docs/linux_compat/screenshots/`.

---

## 6. Confirmed Linux Support & Test Target Matrix

| Component | Primary Target (Confirmed) | Secondary / Compatible Targets |
| :--- | :--- | :--- |
| **Distribution** | **Kubuntu (Ubuntu 24.04 / 22.04 LTS base)** | Ubuntu LTS (GNOME), Debian 12, Fedora 40 |
| **Desktop Environment** | **KDE Plasma 6 / 5** and **GNOME 46 / 42** | Xfce / standard freedesktop-compliant DEs |
| **Display Server** | **Wayland (with XWayland fallback)** and **X11** | Pure X11 |
| **Audio Server** | **PipeWire (via pipewire-pulse)** and **PulseAudio** | Standalone ALSA (unsupported without daemon) |
| **Tested Browsers** | **Google Chrome, Mozilla Firefox, Brave, Chromium / Edge** | Opera, Vivaldi |
| **Media Players** | **Spotify (Web API / Connect)**, **VLC** | Local MPRIS2-compliant players |

---

## 7. Files Slated for Changes in Subsequent Phases

1. `core/audio_portaudio.py`: Replace `sys.exit(1)` with graceful degradation / typed chat fallback.
2. `core/platform/linux.py`: Implement robust XDG app discovery, Wayland-safe volume/audio queries, and screenshot fallbacks.
3. `core/browser/platform/linux.py`: Add Wayland-aware tab closing and app execution abstraction.
4. `core/media/suppress/linux.py`: Implement real MPRIS-based media suppression replacing `NullSuppressor`.
5. `actions/browser_control.py`: Integrate XDG application capability detection and remembered app preference.
6. `actions/spotify_control.py`: Implement explicit `readiness` check gating all search/play API calls.
7. `memory/config_manager.py`: Add getter/setter for remembered application selections.
8. `setup.py`: Remove unauthorized `sudo apt-get` execution and document distro-specific manual commands.
9. `docs/linux_compat/SETUP.md`: Comprehensive verified installation guide.
