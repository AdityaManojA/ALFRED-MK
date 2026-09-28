# Graph Report - Mark-LIV  (2026-09-25)

## Corpus Check
- 70 files · ~136,586 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 8 file(s) not represented in the graph (top: (none) 3, .ico 2, .obj 2)

## Summary
- 1752 nodes · 3461 edges · 100 communities (79 shown, 21 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 158 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `07e28d20`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- game_updater.py
- background_monitor.py
- file_processor.py
- file_controller.py
- tts.py
- avatar_mesh.py
- MainWindow
- gemini.py
- _RootShim
- _SessionRegistry
- llm_client.py
- code_helper.py
- HoloAvatar
- memory_manager.py
- _BrowserSession
- computer_control.py
- dev_agent.py
- screen_processor.py
- QWidget
- EchoGuard
- JarvisUI
- intel_notes.py
- .__init__
- JarvisLive
- PushToTalk
- crypto-js.min.js
- config_manager.py
- VisemeStream
- send_message.py
- undo.py
- server.py
- ui.py
- HudCanvas
- computer_settings
- system_monitor.py
- typing
- qcol
- browser_control.py
- daily_brief.py
- action_loader.py
- CustomizeOverlay
- ._build_quick_drawer
- tech_font
- _is_reconnect_signal
- confirm.py
- ._build_app
- main.py
- _SysMetrics
- load_api_keys
- NotesTerminalWidget
- FileDropZone
- DashboardServer
- plugin_loader.py
- _add_cranium
- ._build_jarvis_icon
- setter
- ._tuning_config
- HueWheel
- sys
- PluginSettingsOverlay
- ._aes_key
- MemoryOverlay
- Graphify + Antigravity Project Workflow & Setup Guide
- _get_macos_wifi_interface
- stt.py
- _ensure_network_access
- rules/graphify.md
- json
- workflows/graphify.md
- _detect_action
- desktop.py
- ._apply_name_update
- ._decrypt
- LogWidget
- PluginManagerOverlay
- ._launch
- get_input_device
- AudioDeviceOverlay
- _template.py
- _get_base_dir
- _make_uploads_dir
- _tlog
- weather_report.py
- ClipboardPanel
- pathlib
- CapabilitiesOverlay
- config
- core
- calendar_sync.py
- Daily Brief Protocol
- Email Handling Rules
- Executive Assistant Persona & Behavioral Standards
- get_plugin_config
- /email-triage Workflow
- get_plugin_enabled

## God Nodes (most connected - your core abstractions)
1. `MainWindow` - 87 edges
2. `JarvisLive` - 51 edges
3. `JarvisUI` - 42 edges
4. `tech_font()` - 38 edges
5. `_BrowserSession` - 32 edges
6. `mono_font()` - 30 edges
7. `_resolve_path()` - 23 edges
8. `file_controller()` - 22 edges
9. `qcol()` - 22 edges
10. `HudCanvas` - 22 edges

## Surprising Connections (you probably didn't know these)
- `3. Dedicated Intel & Notes Terminal (`intel_notes`)` --references--> `intel_notes()`  [INFERRED]
  .agents/rules/file_exploration.md → actions/intel_notes.py
- `1. File Opening (`open`)` --references--> `file_controller()`  [INFERRED]
  .agents/rules/file_exploration.md → actions/file_controller.py
- `2. Folder Exploration (`explore`)` --references--> `file_controller()`  [INFERRED]
  .agents/rules/file_exploration.md → actions/file_controller.py
- `Step 1: Target Identification` --references--> `file_controller()`  [INFERRED]
  .agents/workflows/file_explorer.md → actions/file_controller.py
- `🛡️ 1. The Heavenly Restriction (Source Code Lockdown)` --references--> `file_controller()`  [INFERRED]
  readme.md → actions/file_controller.py

## Import Cycles
- None detected.

## Communities (100 total, 21 thin omitted)

### Community 0 - "game_updater.py"
Cohesion: 0.06
Nodes (79): _build_google_flights_url(), flight_finder(), _format_spoken(), _format_text_report(), _get_base_dir(), _parse_date(), _parse_flights_with_gemini(), Path (+71 more)

### Community 1 - "background_monitor.py"
Cohesion: 0.23
Nodes (14): add_monitor(), check_all(), _is_blocked(), list_monitors(), _load(), BackgroundMonitor — user-configured topic watching. Checks DDG news once per…, Run all pending topic checks (once per day per topic). Returns a list of…, remove_monitor() (+6 more)

### Community 3 - "file_processor.py"
Cohesion: 0.24
Nodes (18): _detect_type(), file_processor(), _file_size_str(), _gemini_client(), _output_path(), _process_archive(), _process_audio(), _process_code() (+10 more)

### Community 4 - "file_controller.py"
Cohesion: 0.09
Nodes (52): copy_file(), create_file(), create_folder(), delete_file(), explore_folder(), file_controller(), find_files(), _format_size() (+44 more)

### Community 5 - "tts.py"
Cohesion: 0.07
Nodes (26): asyncio, _compress_silence(), create_tts_player(), EdgeTTSEngine, ElevenLabsTTSEngine, _import_kokoro_pipeline(), KokoroTTSEngine, _synth() (+18 more)

### Community 6 - "avatar_mesh.py"
Cohesion: 0.19
Nodes (17): _add_neck(), build_head(), _check_landmarks(), get_head_mesh(), _load_obj(), Path, Human head mesh for the HUD avatar. The face is **real measured human…, A tapering tube dropped from inside the jaw; it fades out, so no shoulders. (+9 more)

### Community 7 - "MainWindow"
Cohesion: 0.06
Nodes (9): QMainWindow, MainWindow, _fl(), Slot — display camera preview overlay (main thread)., Collapsible panel below the HUD — shows search results, news, briefings. Hidden…, Slot — runs on Qt main thread. Updates and shows the content panel., Slot — Qt main thread. Lays a document review into the content panel., Slot — Qt main thread. Puts a fresh quiz on the board. (+1 more)

### Community 8 - "gemini.py"
Cohesion: 0.06
Nodes (58): _compare(), _ddg_news(), _ddg_search(), _format_ddg(), _format_news(), _gemini_available(), _gemini_headlines(), _gemini_search() (+50 more)

### Community 10 - "_SessionRegistry"
Cohesion: 0.15
Nodes (5): _detect_default_browser(), Manages all active browser sessions., Is there an active automation session for this browser (or any)?, Returns the last natively-opened URL once (consumed to avoid repeats)., _SessionRegistry

### Community 11 - "llm_client.py"
Cohesion: 0.14
Nodes (22): call_llm(), call_llm_stream(), call_llm_text(), check_model_available(), ensure_ollama_running(), get_base_dir(), get_llm_provider(), get_llm_settings() (+14 more)

### Community 12 - "code_helper.py"
Cohesion: 0.18
Nodes (25): _build(), _clean_code(), code_helper(), _detect_intent(), _edit_action(), _explain_action(), _fix_code(), _get_gemini() (+17 more)

### Community 13 - "HoloAvatar"
Cohesion: 0.11
Nodes (19): _blend(), _c(), HoloAvatar, QColor, QPainter, _rate(), `col` at alpha `a` pre-mixed onto `bg`, returned fully **opaque**. Qt's raster…, Animated holographic head. One instance per HUD canvas. Lifecycle: av =… (+11 more)

### Community 14 - "memory_manager.py"
Cohesion: 0.12
Nodes (27): _do_shutdown(), Summarise the current session in 1-2 sentences and save to long_term.json., _all_entries(), all_entries_for_ui(), _empty_memory(), _entry_value(), forget(), format_memory_for_prompt() (+19 more)

### Community 16 - "computer_control.py"
Cohesion: 0.10
Nodes (34): _base_dir(), _clear_field(), _click(), _clipboard_get(), _clipboard_paste(), computer_control(), _drag(), _focus_window() (+26 more)

### Community 17 - "dev_agent.py"
Cohesion: 0.16
Nodes (20): _build_project(), _classify_error(), dev_agent(), _fix_files(), _get_model(), _has_error(), _install_dependencies(), _is_rate_limit() (+12 more)

### Community 18 - "screen_processor.py"
Cohesion: 0.16
Nodes (18): _base_dir(), _capture_screen(), _compress(), _cv2_backend(), _detect_camera_index(), _get_camera_index(), _get_os(), _load_config() (+10 more)

### Community 19 - "QWidget"
Cohesion: 0.07
Nodes (14): QWidget, BiometricFingerprintWidget, _CameraPreview, ConfirmBanner, CRTReconWidget, MetricBar, Halftone / CRT Dithered Optical Recon Scanner Widget (Screenshot 1: Top-Left…, Biometric Fingerprint Scanner Widget (Screenshot 1: Middle-Left Biometric Box).… (+6 more)

### Community 20 - "EchoGuard"
Cohesion: 0.08
Nodes (14): band_energies(), EchoGuard, ndarray, Classifies microphone blocks while the assistant is speaking. Usage:…, True once the estimate rests on enough real echo to be trusted., Residual left by this room's own echo. Higher = harder to separate., False when the acoustics are too poor to judge on content alone. Speakers…, The residual a block must clear right now to count as a voice. (+6 more)

### Community 21 - "JarvisUI"
Cohesion: 0.05
Nodes (16): JarvisUI, Thread-safe: raise the irreversible-action gate. Called from action handlers…, Thread-safe: take the gate down., Thread-safe: feed a 0.0–1.0 live audio level to the HUD waveform. Called from…, Ask the avatar to look somewhere for a moment (see HoloAvatar.glance)., Thread-safe: post a schedule of (level, openness, width) mouth frames for…, Thread-safe: post special note, research link, or structured data to the…, Thread-safe: clear the dedicated Notes Terminal. (+8 more)

### Community 22 - "intel_notes.py"
Cohesion: 0.08
Nodes (26): _auto_detect_type(), _config_dir(), intel_notes(), _load_notes(), Path, actions/intel_notes.py — Dedicated Intel & Notes Terminal Action. Provides a…, Action handler called by Gemini / action_loader., _save_notes() (+18 more)

### Community 23 - ".__init__"
Cohesion: 0.12
Nodes (9): ProactiveEngine, Decides when JARVIS should speak unprompted and builds a context-rich prompt.…, Build a context snapshot for Gemini. Rotates through three focus areas so…, _Popen, Exception, Raised inside the session TaskGroup to force a clean, voluntary reconnect (e.g.…, Turn hold-to-talk on or off. Returns the scope actually achieved., _ReconnectSignal (+1 more)

### Community 24 - "JarvisLive"
Cohesion: 0.07
Nodes (17): JarvisLive, Background task: voice alerts when metrics exceed thresholds., Check user-configured topics once per day; speak alerts when new headlines…, Forward phone mic PCM chunks from dashboard queue into the Gemini Live session., Load the detector once (model loads on first start). Idempotent., Called from the detector thread when 'Hey Jarvis' is heard., Auto-sleep after the configured silence window (wake-word mode only)., Enable/disable wake word from the settings UI. Returns a status token:… (+9 more)

### Community 25 - "PushToTalk"
Cohesion: 0.06
Nodes (31): configure(), _display_name(), _is_pseudo(), list_devices(), prefetch(), _work(), _query(), _collect() (+23 more)

### Community 27 - "config_manager.py"
Cohesion: 0.13
Nodes (23): ensure_config_dir(), get_base_dir(), _patch_config(), Path, Read-modify-write one key without disturbing the rest of the config., Read-modify-write one or more keys in api_keys.json. Every setter in this file…, Merge `values` into a namespace's stored config (read-modify-write, like every…, Persist assistant name and user name to config. (+15 more)

### Community 28 - "VisemeStream"
Cohesion: 0.13
Nodes (12): collections, coverage(), Text → mouth shape, fused with the audio the avatar is actually speaking. Why…, Reduce any character to a bare Latin letter, or "" if it has none. This is what…, Fraction of the letters in `text` we can reduce to a Latin sound., Split a line of speech into (viseme, duration-weight) pairs. Returns [] for…, Fuses the transcript's shape sequence onto the audio's timing. Thread note:…, Blend audio frames [(level, openness, width)] with the text queue. (+4 more)

### Community 29 - "send_message.py"
Cohesion: 0.25
Nodes (19): _base_dir(), _clear_and_paste(), _desktop_send(), _get_os(), _open_app(), _open_browser_url(), _paste_text(), Path (+11 more)

### Community 30 - "undo.py"
Cohesion: 0.15
Nodes (11): clear(), _Entry, history(), peek(), core/undo.py — one shared undo stack for every action that changes state. WHY…, Forget the stack. Called when the app shuts down so closures holding old file…, Label of the operation that `undo_last()` would reverse, or ''., Most recent first — used by the UI panel and the `undo` tool's list mode. (+3 more)

### Community 31 - "server.py"
Cohesion: 0.12
Nodes (14): base64, _ensure_certs(), _local_ip(), dashboard/server.py — JARVIS Local HTTP Dashboard Plain HTTP on port 8000 (no…, Return the best LAN-facing IPv4 address, no internet required., Make sure config/certs holds a TLS key pair, generating a self-signed one the…, _read(), fastapi (+6 more)

### Community 32 - "ui.py"
Cohesion: 0.21
Nodes (11): Holographic AI head for the HUD centre — the thing that used to be a ring stack…, math, get_push_to_talk_enabled(), get_wake_word_enabled(), Whether local wake-word gating is on (assistant sleeps until 'Hey Jarvis')., Hold-a-key-to-speak. When on, the mic is closed unless the chord is held., pyqt6_qtcore, pyqt6_qtgui (+3 more)

### Community 33 - "HudCanvas"
Cohesion: 0.09
Nodes (15): HudCanvas, QPainter, Draw subtle background CRT coordinate grid with + crosshairs (Screenshot 2)., 3D Rotating Vector Wireframe Globe (Matching Screenshot 2: WAKU CRT Globe).…, Futuristic Oscilloscope Waveforms spanning across the globe (Screenshot 1 & 2…, Live cycling Hexadecimal & Telemetry stream (directly from Screenshot 1)., High-Impact Inverted Phosphor Status Banner (Screenshot 2: 'PROTECTING YOUR…, Authentic CRT Scanlines, Corner Brackets, and Viewport Telemetry. (+7 more)

### Community 34 - "computer_settings"
Cohesion: 0.12
Nodes (16): brightness_get(), brightness_set(), computer_settings(), dark_mode(), paste(), press_key(), Current brightness 0-100, or None where it cannot be read., Set brightness to an absolute percentage. Only used to restore a value captured… (+8 more)

### Community 35 - "system_monitor.py"
Cohesion: 0.18
Nodes (11): _get_cpu_temp(), _get_gpu_usage(), get_system_status(), _nvml_gpu(), System Monitor — background metric checks with voice alert support. Zero…, Snapshot of current system metrics for the system_status tool., Stateful monitor — cooldown state persists across session reconnections. Call…, GPU utilisation via NVML — zero subprocess on all platforms. (+3 more)

### Community 36 - "typing"
Cohesion: 0.28
Nodes (8): _available(), install_for_config(), _pip(), MARK XL — Dependency auto-installer. Called automatically on first launch and…, Return True if the module can be imported (no actual import)., Install all missing packages required by *config*. Blocking — always call from…, importlib_util, typing

### Community 37 - "qcol"
Cohesion: 0.18
Nodes (7): QPixmap, _DropCanvas, _file_category(), _fmt_size(), QColor, qcol(), Pre-render the static grid-dot background into a transparent pixmap so…

### Community 38 - "browser_control.py"
Cohesion: 0.24
Nodes (11): browser_control(), _find_exe_windows(), _find_opera_windows(), _log(), _normalize_url(), _open_native(), Bare words like "instagram" → "https://instagram.com" Domains like…, Opens the user's REAL browser normally — with their own profile, logged-in… (+3 more)

### Community 39 - "daily_brief.py"
Cohesion: 0.06
Nodes (51): daily_brief(), _get_gmail_brief(), _get_greeting(), _get_live_weather(), _get_reminders_brief(), _get_system_vitals(), Daily Brief Action for JARVIS Mark-LIV. Provides the ultimate morning and daily…, Inspect core CPU, RAM, and Battery vitals. (+43 more)

### Community 40 - "action_loader.py"
Cohesion: 0.13
Nodes (14): ActionRecord, ActionRegistry, _call_handler(), discover_actions(), _is_heavenly_restricted_params(), _opt_upper(), Path, Action discovery, validation, and dispatch — the built-in twin of… (+6 more)

### Community 41 - "CustomizeOverlay"
Cohesion: 0.22
Nodes (5): CustomizeOverlay, _lbl(), Floating glassmorphic overlay for configuring Assistant Persona, Commander…, Highlight the selected voice pill; dim the rest., Updates the selected colour; hex box + wheel stay in sync, theme is live-…

### Community 42 - "._build_quick_drawer"
Cohesion: 0.14
Nodes (6): _press(), Floating overlay panel shown when the ⚙ header button is toggled., Repaint the push-to-talk row from the saved setting., Swap the centrepiece. Both objects stay in memory, so the change is instant and…, Bind the chord inside the window when no global hook is available. On macOS and…, Report a windowed press/release to whoever owns the microphone.

### Community 43 - "tech_font"
Cohesion: 0.12
Nodes (12): QFont, QVBoxLayout, _row(), mono_font(), Floating overlay — QR code for instant phone pairing + manual key fallback., Call from any thread when a phone successfully connects., RemoteKeyOverlay, _lbl() (+4 more)

### Community 44 - "_is_reconnect_signal"
Cohesion: 0.50
Nodes (5): BaseException, _is_reconnect_signal(), _keep_context_of(), True if `exc` is a _ReconnectSignal, or a(n) (Base)ExceptionGroup that wraps…, Read `keep_context` off a reconnect signal, unwrapping the group the TaskGroup…

### Community 45 - "confirm.py"
Cohesion: 0.21
Nodes (12): bind(), _log(), _Pending, pending_title(), core/confirm.py — a confirmation the model cannot forge. THE PROBLEM WITH THE…, Called by the UI when the user presses CONFIRM or CANCEL. Runs the stored…, when nothing is waiting. Lets an action avoid stacking two banners., Wire this module to the HUD. Called once from main.py at startup. (+4 more)

### Community 46 - "._build_app"
Cohesion: 0.24
Nodes (6): _auth(), list_files(), revoke_devices(), _safe_filename(), upload_file(), wake_ep()

### Community 47 - "main.py"
Cohesion: 0.09
Nodes (23): ProactiveEngine 2.0 — context-aware, time-aware, non-repetitive background…, _capture_camera(), Telling the user's voice apart from our own coming back through the speakers.…, google, google_genai, LiveConnectConfig, _describe_limits(), _describe_tools() (+15 more)

### Community 48 - "_SysMetrics"
Cohesion: 0.21
Nodes (4): Thread-safe speech channel for plugins: lets a plugin ask JARVIS to say…, _nvml_gpu_windows(), Return NVIDIA GPU utilisation % using nvml.dll directly — zero subprocess., _SysMetrics

### Community 49 - "load_api_keys"
Cohesion: 0.13
Nodes (12): get_assistant_name(), get_brief_enabled(), get_gemini_key(), get_hud_style(), get_proactive_audio_enabled(), get_voice(), is_configured(), load_api_keys() (+4 more)

### Community 51 - "FileDropZone"
Cohesion: 0.18
Nodes (3): QDragEnterEvent, QDropEvent, FileDropZone

### Community 52 - "DashboardServer"
Cohesion: 0.25
Nodes (3): DashboardServer, URL for manual browser entry. When HTTPS active, points to alias port (also…, Second HTTPS server on PORT+1 sharing the same app and in-memory state. Chrome…

### Community 53 - "plugin_loader.py"
Cohesion: 0.21
Nodes (12): discover_plugins(), _load_error(), _opt_upper(), PluginRecord, Exception, Path, Plugin discovery, validation, collision detection, and dispatch. Discovery runs…, Returns a PluginRecord; .valid=False + .error set on any problem. Never raises. (+4 more)

### Community 54 - "_add_cranium"
Cohesion: 0.28
Nodes (8): _add_cowl_ears(), _add_cranium(), _boundary_loop(), ndarray, Sweep the mask's open border back over a skull and close it at the occiput., Add signature Batman Cowl tactical ears to the cranial mesh., Ordered ring of vertices along the open border of a triangle mesh., _slerp()

### Community 55 - "._build_jarvis_icon"
Cohesion: 0.20
Nodes (6): _base_dir(), Path, Render a JARVIS arc-reactor icon at 4× resolution and downsample for crisp…, Create a Windows .lnk shortcut WITHOUT launching PowerShell or cmd. Tries…, Resolve the user's REAL desktop directory instead of assuming ~/Desktop, which…, Create a desktop shortcut on Windows / macOS / Linux. Never opens a terminal,…

### Community 56 - "setter"
Cohesion: 0.10
Nodes (3): setter, _work(), Combined state for the two wake-word buttons. Readiness is a cheap,…

### Community 57 - "._tuning_config"
Cohesion: 0.22
Nodes (7): The optional knobs, kept apart so one bad field can be dropped wholesale. Every…, get_media_resolution(), get_thinking_enabled(), get_turn_tuning(), Whether the Live model may spend tokens thinking before it answers. Off by…, How eagerly the server decides you have stopped speaking. OFF by default, and…, How finely the model tokenises the screenshots and camera frames it is sent.…

### Community 58 - "HueWheel"
Cohesion: 0.24
Nodes (4): QPointF, QRectF, HueWheel, Circular colour picker. The user drags the handle (small white circle) around…

### Community 59 - "sys"
Cohesion: 0.31
Nodes (8): _check_assets(), _check_python(), main(), MARK LIV — one-time setup. Installs the Python dependencies for THIS operating…, Fail immediately and clearly rather than deep inside a pip resolver. A wrong…, The avatar's face is a shipped file; a truncated clone should say so., _run(), sys

### Community 61 - "._aes_key"
Cohesion: 0.32
Nodes (6): auto_login(), device_login_ep(), login(), phone_audio_ws(), _derive_key(), SHA-256(sessionKey‖salt) → 32-byte AES-256 key (microseconds, no PBKDF2 needed).

### Community 62 - "MemoryOverlay"
Cohesion: 0.21
Nodes (6): _HudOverlay, MemoryOverlay, Base for the floating panels placed by hand over the HUD. They are children of…, Everything JARVIS has stored about you, and when it learned it. Memory used to…, Take every item out of the layout and detach it from the widget tree in this…, Size the panel to its content, re-centre it, and repaint what the old size…

### Community 65 - "stt.py"
Cohesion: 0.15
Nodes (8): ndarray, Speech-to-Text engines for MARK XL. Whisper – offline transcription via faster-…, Offline transcription using faster-whisper., Transcribe a float32 mono 16 kHz numpy array. Returns transcript string., Streaming transcription using Vosk., Feed raw int16 LE PCM bytes. Returns (text, is_final)., VoskSTT, WhisperSTT

### Community 68 - "json"
Cohesion: 0.38
Nodes (6): json, Focus Protocol Plugin for JARVIS Mark-LIV. Manages deep work intervals,…, Execute focus protocol actions., _read_state(), run(), _write_state()

### Community 70 - "_detect_action"
Cohesion: 0.40
Nodes (5): _detect_action(), _normalise(), Resolve a free-text description to an action name, locally. Returns {"action":…, What to tell the model when nothing matched. Names real actions so its retry…, _suggest()

### Community 71 - "desktop.py"
Cohesion: 0.08
Nodes (30): _ask_gemini_for_desktop_action(), _build_sandbox(), clean_desktop(), desktop_control(), _execute_generated_code(), _get_api_key(), _get_base_dir(), get_current_wallpaper() (+22 more)

### Community 72 - "._apply_name_update"
Cohesion: 0.15
Nodes (10): apply_ui_accent(), current_palette(), Applies either DOSSIER CRT [A-34] (#8e9bff) or VECTOR CRT [WAKU] (#a8ff3e), or…, A snapshot of the accent-linked colours currently on class C., LIVE full theme change. Replaces the old palette colours with the new ones in…, Read api_keys.json config dict. Returns {} on any error., Live preview — paints the whole interface the new colour (does NOT write to…, Update all name/theme-dependent UI elements and persist to config. (+2 more)

### Community 73 - "._decrypt"
Cohesion: 0.40
Nodes (4): command(), ws_ep(), _decrypt_cbc(), Decrypt base64(IV[16] ‖ ciphertext) with AES-256-CBC + PKCS7.

### Community 75 - "PluginManagerOverlay"
Cohesion: 0.31
Nodes (4): QHBoxLayout, QPushButton, PluginManagerOverlay, Floating overlay — lists discovered plugins with per-plugin ON/OFF toggles.

### Community 76 - "._launch"
Cohesion: 0.29
Nodes (5): _firefox_profile_dir(), launch_persistent_context already opens a starting tab. Instead of opening a…, Launches the browser with the real user profile. Does nothing if the context is…, _real_profile_dir(), Page

### Community 77 - "get_input_device"
Cohesion: 0.33
Nodes (5): get_input_device(), get_output_device(), Microphone device name, or '' for the system default., Speaker device name, or '' for the system default., save_output_device()

### Community 78 - "AudioDeviceOverlay"
Cohesion: 0.22
Nodes (3): AudioDeviceOverlay, Choose which microphone JARVIS listens to and which speakers it uses. Both…, Place a floating overlay in the middle of the HUD and show it.

### Community 79 - "_template.py"
Cohesion: 0.50
Nodes (3): Drop-in JARVIS plugin template. Copy this file, rename it (no leading…, parameters: dict of the args Gemini extracted, matching PLUGIN['parameters'].…, run()

### Community 80 - "_get_base_dir"
Cohesion: 0.67
Nodes (3): _get_api_key(), _get_base_dir(), Path

### Community 81 - "_make_uploads_dir"
Cohesion: 0.67
Nodes (3): _make_uploads_dir(), Path, Return (and create) the cross-platform uploads folder.

### Community 82 - "_tlog"
Cohesion: 0.09
Nodes (16): _clean_transcript(), _is_repeat_chunk(), callback(), _open_mic(), _deliver_news(), main(), runner(), Format terminal log report without emojis using red bracketed tags, and… (+8 more)

### Community 83 - "weather_report.py"
Cohesion: 0.50
Nodes (4): _log(), weather_action(), urllib_parse, webbrowser

### Community 93 - "calendar_sync.py"
Cohesion: 0.47
Nodes (5): _load_events(), Calendar Sync Plugin for JARVIS Mark-LIV. Tracks agenda, meetings,…, Execute calendar action., run(), _save_events()

### Community 94 - "Daily Brief Protocol"
Cohesion: 0.50
Nodes (3): Daily Brief Protocol, Purpose, Rules

### Community 95 - "Email Handling Rules"
Cohesion: 0.50
Nodes (3): Email Handling Rules, Purpose, Rules

### Community 96 - "Executive Assistant Persona & Behavioral Standards"
Cohesion: 0.50
Nodes (3): Core Operational Rules, Executive Assistant Persona & Behavioral Standards, Persona & Demeanor

### Community 97 - "get_plugin_config"
Cohesion: 0.50
Nodes (4): get_plugin_config(), get_plugin_setting(), All stored values for a namespace (empty dict if none set yet)., A single value from a namespace, or `default` if unset.

### Community 98 - "/email-triage Workflow"
Cohesion: 0.50
Nodes (3): /email-triage Workflow, Objective, Steps

### Community 99 - "get_plugin_enabled"
Cohesion: 0.19
Nodes (7): _call_run(), PluginRegistry, One entry per settings SECTION, for enabled plugins that declare a…, Invoke run() passing only the kwargs it actually declares (or all of them if it…, How this plugin's result should re-enter the conversation, if it said., get_plugin_enabled(), Plugins are enabled by default the moment they're discovered (opt-out model).

## Knowledge Gaps
- **29 isolated node(s):** `C`, `Purpose`, `Rules`, `Purpose`, `Rules` (+24 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 686 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **21 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MainWindow` connect `MainWindow` to `ui.py`, `qcol`, `._apply_name_update`, `._build_quick_drawer`, `PluginManagerOverlay`, `tech_font`, `AudioDeviceOverlay`, `load_api_keys`, `QWidget`, `CapabilitiesOverlay`, `._build_jarvis_icon`, `setter`, `.resizeEvent`?**
  _High betweenness centrality (0.094) - this node is a cross-community bridge._
- **Why does `JarvisUI` connect `JarvisUI` to `ui.py`, `._apply_name_update`, `._build_quick_drawer`, `main.py`, `_tlog`, `QWidget`, `.__init__`, `JarvisLive`, `setter`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._
- **Why does `DashboardServer` connect `DashboardServer` to `._decrypt`, `._build_app`, `main.py`, `JarvisLive`, `._aes_key`, `server.py`?**
  _High betweenness centrality (0.047) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `JarvisLive` (e.g. with `ProactiveEngine` and `SystemMonitor`) actually correct?**
  _`JarvisLive` has 8 INFERRED edges - model-reasoned connections that need verification._
- **What connects `C`, `Purpose`, `Rules` to the rest of the system?**
  _29 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `game_updater.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06155950752393981 - nodes in this community are weakly interconnected._
- **Should `computer_settings.py` be split into smaller, more focused modules?**
  _Cohesion score 0.041666666666666664 - nodes in this community are weakly interconnected._