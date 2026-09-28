# PHASE 0 RECONNAISSANCE NOTES — SENTRY MODE V2: MONITOR + FOCUS
**Repository:** ALFRED-MK-V  
**Date:** 2026-09-29  
**Status:** Complete  

---

## 1. Where Sentry Mode Lives Today

### UI Component (`ui.py`)
- **Node ID:** `ui_mainwindow_toggle_sentry_mode` (`._toggle_sentry_mode()`)
- **Button Definition:** Lines 7914–7943 in `MainWindow._build_controls()`.
  ```python
  self._sentry_btn = QPushButton("[ ▣ ]  SENTRY MODE")
  self._sentry_btn.clicked.connect(self._toggle_sentry_mode)
  ```
- **Toggle Handler:** `MainWindow._toggle_sentry_mode(self, checked: bool)` at lines 9947–9962 invokes callback `self.on_screen_monitor_toggle(bool(checked))`.
- **State Application:** `MainWindow._apply_screen_monitor_state(self, active: bool, label: str = "")` at lines 9963–9971 sets button text (`[ ◈ ]  SCREEN MONITORING` when active vs `[ ▣ ]  SENTRY MODE` when inactive), tooltip, and checked state. Thread-safe emission via `_screen_monitor_sig` (line 7302).

### Controller & Dispatcher (`main.py`)
- **Node ID:** `main_rationale_1056` ("Fast callback used by the Sentry button on the Qt thread")
- **Callback Hook:** Line 764: `self.ui.on_screen_monitor_toggle = self._ui_screen_monitor_toggle`
- **Controller Methods:**
  - `_ui_screen_monitor_toggle(self, enabled: bool) -> dict` (lines 1055–1061) calls `_start_screen_monitor` or `_stop_screen_monitor`.
  - `_start_screen_monitor(self, goal: str, interval_seconds: float = 3.0)` (lines 1063–1074) starts the controller and informs `ui.set_screen_monitor_state`.
  - `_stop_screen_monitor(self, message: str = "Screen monitoring stopped.")` (lines 1076–1087) stops the controller.
- **Tool Dispatch:**
  - Registered in `TOOL_DEFINITIONS` under `"screen_monitor"` (lines 464–475).
  - Executed in `_execute_tool(self, fc)` at lines 1733–1755 for actions `start`, `stop`, `status`.

### Terminal Watching & Screen Monitoring Loop (`actions/screen_monitor.py`)
- **Node IDs:** `actions_screen_monitor_screenmonitorevent`, `actions_screen_processor_capture_screen`
- **Engine:** `ScreenMonitorController` manages a dedicated polling thread `_run_monitor()`:
  - Takes screen observation via `capture_screen()` (`actions/screen_processor.py`).
  - Queries active window context (`_get_windows_window_info`, `_get_macos_window_info`, `_get_linux_window_info`).
  - Computes visual perceptual hashes (`_visual_fingerprint`, 16x16 luma reduction) to detect frame differences exceeding `_VISUAL_CHANGE_THRESHOLD = 0.08`.
  - Runs local regex pattern matching (`_COMPLETION_WORDS = r"\b(done|complete|completed|finished|success|succeeded|failed|failure|error)\b"`).
  - Invokes `on_meaningful_state` or `on_completion` callbacks.

### Spoken Output & TTS Entry Point
- **Node ID:** `main_jarvislive_speak` (`speak(self, text: str)` lines 1494–1503)
  - Sends a turn to the Gemini Live WebSocket session (`self.session.send_client_content`). Gemini streams multimodal speech directly over audio output.
- **Node ID:** `main_jarvislive_speak_local` (lines 2979–2992)
  - Dispatches clean text to local SAPI voice (`win32com.client.Dispatch("SAPI.SpVoice")`) or local TTS engine (`core/local_ttt.py`).
- **Screen Analysis Speech Path:** In `_analyze_screen_monitor_event(self, event, completion_hint)` (lines 1129–1175), a prompt `[SCREEN MONITOR CHECK]...` with base64 JPEG attachment is passed to `self.session.send_client_content` so the model inspects the screen and responds verbally.

---

## 2. HUD Component Tree & Styling

### Full HUD vs Minimized HUD
- **Node ID:** `ui_mainwindow` (`MainWindow(QMainWindow)`, line 7094): The primary desktop interface.
- **Node ID:** `ui_hudcanvas` (`HudCanvas(QWidget)`, line 1132): Center viewport rendering the Stark Arc Reactor globe, reactive audio waveforms, cyber grid, and particle matrix with software `QPainter`.
- **Node ID:** `ui_minimizedhudoverlay` (`MinimizedHudOverlay(QWidget)`, line 3597):
  - Frameless, translucent (`WA_TranslucentBackground`), always-on-top (`WindowStaysOnTopHint`), fixed-size 420x230 window.
  - Activated via `MainWindow.changeEvent()` (lines 10073–10081):
    - `self.isMinimized()` → calls `self._hud_overlay.begin_minimize_session()`.
    - Restoring main window → calls `self._hud_overlay.hide_overlay()`.
  - Contains title bar (`overlayShell`), restore button `↗`, close button `×`, and read-only transcript `QTextEdit`.

### How Buttons Are Drawn
1. **Vector Buttons (`CyberGraphicLineButton`):** Lines 3004–3128. Custom `paintEvent` draws angled cyber chamfers, neon borders, and glowing backgrounds without bitmaps.
2. **Standard Buttons (e.g. `self._sentry_btn`, `ReactiveMicButton`):** Standard `QPushButton` instances styled via CSS stylesheets using monospaced fonts (`mono_font(8, QFont.Weight.Bold)`), transparent/dark panel backgrounds, and state-based borders (`BORDER` vs `BORDER_B`).

### Theme Palette Constants (`class C`, lines 724–751)
```python
BG          = "#090a12"       # Deep CRT obsidian backing
PANEL       = "#0d0f1e"       # CRT phosphor glass panel
PANEL2      = "#121528"       # Elevated tactical module layer
BORDER      = "#222748"       # Precision CRT frame line
BORDER_B    = "#505bb5"       # Bright glowing phosphorescent border
BORDER_A    = "#343a6b"       # Subtle division grid rule
PRI         = "#8e9bff"       # Electric CRT Phosphor Lavender / Indigo
PRI_DIM     = "#5463cc"       # Medium phosphor bloom
ACC         = "#ff7390"       # Tactical dossier alert red
ACC2        = "#ffd166"       # Telemetry warning amber
GREEN       = "#4ef2bb"       # Phosphor matrix emerald
RED         = "#ff2a55"       # Threat assessment crimson
MUTED       = "#707ab0"       # Muted terminal readout
TEXT        = "#e8ecff"       # Crisp luminescent CRT white-blue
TEXT_MED    = "#a6b2f0"       # Medium high-tech CRT readout
WHITE       = "#f4f6ff"       # Clean CRT white
```

### State Colours (`HudCanvas._core_colours()`, lines 1746–1755)
- `self.muted` → `C.MUTED_C` (silence neon red)
- `self.speaking` → `C.PRI` + `C.ACC` (lavender + alert rose)
- `"THINKING"` / `"PROCESSING"` → `C.PRI` + `C.ACC2` (lavender + amber)
- `"LISTENING"` → `C.PRI` + `C.GREEN` (lavender + emerald)
- Default / Idle → `C.PRI` + `C.PRI_DIM` (electric lavender + dim bloom)

---

## 3. Voice Pipeline & Answer Window

### Wake-Word Gate
- **Node ID:** `core_wake_word_wakeworddetector`, `main_jarvislive_listen_audio_callback`
- In `_listen_audio(self)` (lines 1937–2016):
  ```python
  if self._wake_enabled and not self._awake:
      det = self._wake_detector
      if det is not None:
          det.feed(indata)
      return
  ```
- Mic frames are fed strictly to `WakeWordDetector`. Only when `self.wake()` is triggered does `self._awake` become `True`, un-gating streaming to Gemini.
- Silence watchdog `_run_sleep_watch()` automatically re-arms sleep after 2 minutes of inactivity.

### One-Shot Answer Window ("Listen Once")
- **Current State:** No dedicated `listen_once()` helper exists in `JarvisLive`.
- **Implementation Strategy:**
  Create an Answer Window controller in `core/sentry/answer_window.py`:
  - When invoked with `timeout_s = ANSWER_WINDOW_S`:
    - Temporarily un-gates mic or captures the next completed utterance without requiring the wake word.
    - Shuts down the window immediately upon utterance completion (STT silence / turn complete) or expiration of `timeout_s`.
    - Restores prior sleep/wake state cleanly.

### STT Return Path into Dispatcher
- **Live Gemini Mode:** User audio streams to Gemini WebSocket; Gemini returns model turns or `tool_call` structures in `_receive_loop()`.
- **Local Mode:** `core/local_pipeline.py` / `core/local_stt.py` transcribes audio locally via Faster-Whisper, emitting transcribed text into `MainWindow.on_text_command`, routed to `_handle_chat_message` or action invocation.

---

## 4. Intent & Command Router Precedence

### Command Mapping
- Voice intent routing is handled dynamically by Gemini function calling using `TOOL_DEFINITIONS` and `core/prompt.txt`.
- Direct verbal regex shortcut map exists in `actions/computer_settings.py` (`_TRIGGER_MAP`, lines 700–720).

### Screen Lock Conflict & Precedence
- **Current Collision:** Line 710 in `actions/computer_settings.py`:
  `"lock_screen": ("lock", "lock the pc", "lock computer"),` calls `lock_screen()` (`pyautogui.hotkey("win", "l")` on Windows).
- **Required Routing Precedence:**
  The FOCUS voice routes ("lock on this tab", "keep me in this tab", "this is the tab", "stay on this tab") must be evaluated **BEFORE** checking `lock_screen`. If the utterance contains `"tab"` or `"focus"` alongside `"lock"`, it must strictly trigger Focus tab-lock rather than locking the physical operating system session!

---

## 5. System Prompt & Privacy Directive

- **Location:** [`core/prompt.txt`](file:///D:/Projects/Alfred-Mark-V/core/prompt.txt), loaded at `main.py` line 1524.
- **Current Privacy Directives:**
  - Section `[WHAT YOU CANNOT DO]` (lines 31–48) currently enforces the Heavenly Restriction (no access to `D:\Projects\Personal-Assistant`) and drive confinement (C: drive limited to Desktop and Documents).
- **Required Phase 8 Addition:**
  Add a dedicated privacy rule for Sentry v2:
  *ALFRED names the distraction out loud in the moment and never writes it down; session state and ledger hold only counters and booleans.*

---

## 6. Target Operating Systems Audit

Full breakdown documented in [`docs/sentry_v2/PLATFORM_MATRIX.md`](file:///D:/Projects/Alfred-Mark-V/docs/sentry_v2/PLATFORM_MATRIX.md).

- **Development OS:** Windows 11 (build 22631+, x86_64).
- **Target OS Support Required:** Windows 10/11, macOS 12+ (x86_64, arm64), Linux (X11 and Wayland on GNOME, KDE, wlroots).
- **Current Codebase Foundation:**
  - `actions/screen_processor.py` contains basic stubs for `_get_windows_window_info`, `_get_macos_window_info`, and `_get_linux_window_info`.
  - Missing browser URL host readers across all platforms (only window titles are read currently).
  - Linux Wayland support requires genuine compositing IPC/DBus readers, not `xdotool`.

---

## 7. Persistence Architecture

- **Existing Pattern:**
  - Files: `memory/long_term.json`, `memory/clipboard_history.json`, `config/api_keys.json`, `config/hud_overlay_pos.json`.
  - Architecture: Thread-safe read/write guarded by `threading.Lock()`, reading JSON with empty-structure defaults on missing/corrupt files, writing atomic or indented JSON (`indent=2` / `indent=4`) with UTF-8 encoding.
- **Focus Ledger Design:**
  - Path: `data/focus_ledger.json` (auto-creates `data/` directory).
  - Schema:
    ```json
    {
      "version": 1,
      "streak": 3,
      "sessions": [
        {
          "planned_s": 1500,
          "on_target_s": 1380,
          "drifts": 2,
          "clean": true,
          "ended_at": "2026-09-29T01:30:00Z"
        }
      ]
    }
    ```
  - Whitelist only: No application names, URLs, window titles, or distraction labels are ever stored.

---

## 8. Proposed File Layout (`core/sentry/`)

```
core/sentry/
├── __init__.py
├── mode_manager.py           # SentryModeManager singleton, SentrySnapshot, Qt signal state_changed
├── answer_window.py          # Temporary un-gated mic window for one-shot answers
├── monitor/
│   ├── __init__.py
│   ├── scheduler.py          # Shared 1 Hz target polling thread
│   └── targets/
│       ├── __init__.py
│       ├── base.py           # MonitorTarget ABC (describe, poll, should_alert)
│       ├── terminal.py       # TerminalTarget (exit code, build errors, completion)
│       ├── window_title.py   # WindowTitleTarget (app/title regex, done/error keywords)
│       ├── file_log.py       # FileLogTarget (tail file for regex, silence timeout)
│       ├── process.py        # ProcessTarget (PID/name exit, CPU/mem thresholds)
│       ├── command.py        # CommandTarget (shell command exit code/stdout diff)
│       ├── clipboard.py      # ClipboardTarget (pattern matching on clipboard entries)
│       └── screen_region.py  # ScreenRegionTarget (reuses screen_processor capture path)
└── focus/
    ├── __init__.py
    ├── state.py              # FocusState dataclass (whitelist booleans, counters, enums only)
    ├── engine.py             # FocusEngine (1 Hz independent tick, session lifecycle)
    ├── reader.py             # SurfaceReader facade, SurfaceIdentity (host hash, transient label)
    ├── labels.py             # HOST_LABEL_MAP, distraction categorisation, NAME_DISTRACTIONS toggle
    ├── lines.py              # TIER1, TIER2, TIER3, NAMELESS, DRILL_SERGEANT, FIRST_CALLOUT pools
    ├── ledger.py             # FocusLedger (data/focus_ledger.json, aggregates only, streak)
    └── platform/
        ├── __init__.py       # Platform backend factory & runtime detection
        ├── base.py           # BasePlatformReader interface
        ├── win.py            # Windows backend (GetForegroundWindow, UI Automation browser tab read)
        ├── mac.py            # macOS backend (lsappinfo foreground, AppleScript browser URL)
        └── linux.py          # Linux backend (X11 xdotool/xprop + Wayland DBus/portal/swaymsg)
```

---

## 9. Graphify Node & Edge Reference Table

| Node ID | Type / Symbol | File Reference | Role in Sentry Mode v2 |
|---|---|---|---|
| `ui_mainwindow_toggle_sentry_mode` | Method | `ui.py:9947` | Sentry UI button entry point to be refactored into dropdown |
| `main_rationale_1056` | Rationale / Handler | `main.py:1056` | Sentry toggle callback on Qt thread |
| `ui_hudcanvas` | Class | `ui.py:1132` | Main viewport canvas, indicators, and paint loop |
| `ui_minimizedhudoverlay` | Class | `ui.py:3597` | Mini translucent HUD overlay needing Sentry status controls |
| `ui_c` | Class | `ui.py:724` | Theme palette tokens (`PRI`, `ACC`, `RED`, `BORDER_B`) |
| `actions_screen_monitor_screenmonitorevent` | Dataclass | `actions/screen_monitor.py:38` | Current terminal watcher observation event structure |
| `actions_screen_processor_capture_screen` | Function | `actions/screen_processor.py:270` | Screen capture facility reused by `ScreenRegionTarget` |
| `actions_computer_settings_lock_screen` | Function | `actions/computer_settings.py:459` | Collision point with Focus tab lock |
| `main_jarvislive_speak` | Method | `main.py:1494` | Primary verbal announcement interface |
| `main_jarvislive_listen_audio` | Async Method | `main.py:1937` | Mic streaming & wake-word gate loop |
| `core_wake_word_wakeworddetector` | Class | `core/wake_word.py` | Local wake word detector |
| `memory_memory_manager_load_memory` | Function | `memory/memory_manager.py:57` | Reference pattern for thread-safe JSON persistence |
