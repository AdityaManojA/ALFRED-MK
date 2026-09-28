# Graph Report - Alfred-Mark-III  (2026-09-26)

## Corpus Check
- 94 files · ~184,215 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 16 file(s) not represented in the graph (top: .ico 7, (none) 3, .bak 2)

## Summary
- 2361 nodes · 4631 edges · 125 communities (95 shown, 30 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 186 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `711bfc4a`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- game_updater.py
- code_helper.py
- MainWindow
- file_processor.py
- file_controller.py
- TronScoreBackgroundPlayer
- CustomizeOverlay
- computer_settings.py
- protocol_engine.py
- HudCanvas
- tts.py
- CentralizedCache
- web_search.py
- .__init__
- gmail_manager.py
- test_screen_processor.py
- JarvisLive
- _BrowserSession
- computer_control.py
- dev_agent.py
- ui.py
- memory_manager.py
- .run_local
- EchoGuard
- ALFRED — MARK III (Wayne Protocol Edition)
- JarvisUI
- config_manager.py
- tech_font
- mono_font
- get_plugin_enabled
- audio_devices.py
- crypto-js.min.js
- screen_processor.py
- desktop.py
- _tlog
- is_heavenly_restricted
- discover_actions
- load_api_keys
- PushToTalk
- GraphManager
- ._build_app
- TestBackgroundWorkerPool
- _index_file
- TelemetryHUD
- browser_control.py
- MemoryOverlay
- main.py
- computer_settings
- json
- FileDropZone
- .__init__
- system_monitor.py
- get_input_device
- TacticalAudioPlayerWidget
- _is_reconnect_signal
- install_and_download
- ._build_right_panel
- _SessionRegistry
- clipboard_manager.py
- echo.py
- NotesTerminalWidget
- RemoteKeyOverlay
- save_app_icon
- confirm.py
- datetime
- DashboardServer
- VisemeStream
- _SysMetrics
- ._apply_name_update
- .broadcast
- SetupOverlay
- WakeWordDetector
- setter
- intel_notes.py
- pathlib
- ._build_jarvis_icon
- .__init__
- re
- ._listen_audio
- LogWidget
- ._apply_ptt_shortcut
- .test_error_isolation_in_concurrent_tasks
- time
- _ensure_network_access
- TestAudioDucker
- .__init__
- ._launch
- get_push_to_talk_enabled
- _detect_action
- CapabilitiesOverlay
- ClipboardPanel
- ._toggle_sentry_mode
- _RootShim
- .clear_chat
- setup.py
- Daily Brief Protocol
- Email Handling Rules
- Executive Assistant Persona & Behavioral Standards
- /email-triage Workflow
- _template.py
- _get_base_dir
- Graphify + Antigravity Project Workflow & Setup Guide
- /deep-work Workflow
- _get_macos_wifi_interface
- duck_media_apps
- rules/graphify.md
- workflows/graphify.md
- _VolumeSliderPopup
- audio_ws
- calendar_sync.py
- SubjectDossierCard
- weather_report.py
- chromadb
- chromadb_config
- fastembed
- sentence_transformers
- screen_find.py
- watchdog_events
- watchdog_observers

## God Nodes (most connected - your core abstractions)
1. `MainWindow` - 92 edges
2. `JarvisLive` - 64 edges
3. `JarvisUI` - 45 edges
4. `tech_font()` - 35 edges
5. `mono_font()` - 35 edges
6. `_BrowserSession` - 32 edges
7. `is_heavenly_restricted()` - 26 edges
8. `TronScoreBackgroundPlayer` - 26 edges
9. `qcol()` - 25 edges
10. `computer_control()` - 24 edges

## Surprising Connections (you probably didn't know these)
- `3. Dedicated Intel & Notes Terminal (`intel_notes`)` --references--> `intel_notes()`  [INFERRED]
  .agents/rules/file_exploration.md → actions/intel_notes.py
- `Steps` --references--> `computer_control()`  [INFERRED]
  .agents/workflows/deep_work.md → actions/computer_control.py
- `2. Security, Privacy & Defensive Architecture` --references--> `computer_control()`  [INFERRED]
  readme.md → actions/computer_control.py
- `1. File Opening (`open`)` --references--> `file_controller()`  [INFERRED]
  .agents/rules/file_exploration.md → actions/file_controller.py
- `2. Folder Exploration (`explore`)` --references--> `file_controller()`  [INFERRED]
  .agents/rules/file_exploration.md → actions/file_controller.py

## Import Cycles
- None detected.

## Communities (125 total, 30 thin omitted)

### Community 0 - "game_updater.py"
Cohesion: 0.06
Nodes (78): _build_google_flights_url(), flight_finder(), _format_spoken(), _format_text_report(), _get_base_dir(), _parse_date(), _parse_flights_with_gemini(), Path (+70 more)

### Community 1 - "code_helper.py"
Cohesion: 0.07
Nodes (49): _build(), _clean_code(), code_helper(), _detect_intent(), _edit_action(), _explain_action(), _fix_code(), _get_gemini() (+41 more)

### Community 2 - "MainWindow"
Cohesion: 0.06
Nodes (7): QMainWindow, MainWindow, Slot — display camera preview overlay (main thread)., Slot — runs on Qt main thread. Updates and shows the content panel., Slot — Qt main thread. Lays a document review into the content panel., Slot — Qt main thread. Puts a fresh quiz on the board., Place a floating overlay in the middle of the HUD and show it.

### Community 3 - "file_processor.py"
Cohesion: 0.08
Nodes (45): _detect_type(), file_processor(), _file_size_str(), _gemini_client(), _output_path(), _process_archive(), _process_audio(), _process_code() (+37 more)

### Community 4 - "file_controller.py"
Cohesion: 0.07
Nodes (62): copy_file(), create_file(), create_folder(), delete_file(), explore_folder(), file_controller(), find_files(), _format_size() (+54 more)

### Community 5 - "TronScoreBackgroundPlayer"
Cohesion: 0.11
Nodes (7): QObject, _base_dir(), Path, Background music audio engine. Plays background score continuously on loop…, Set base normal volume (0.0 to 1.0). Speech ducking scales to 50% of base., Duck to 50% of base volume when speaking, restore to base volume when…, TronScoreBackgroundPlayer

### Community 6 - "CustomizeOverlay"
Cohesion: 0.10
Nodes (9): QPointF, QRectF, CustomizeOverlay, _lbl(), HueWheel, Circular colour picker. The user drags the handle (small white circle) around…, Floating glassmorphic overlay for configuring Assistant Persona, Commander…, Highlight the selected voice pill; dim the rest. (+1 more)

### Community 8 - "protocol_engine.py"
Cohesion: 0.07
Nodes (39): create_protocol(), _do_save(), execute_protocol(), _execute_tool(), get_action_registry(), get_protocols_file(), interpolate_variables(), _is_failure() (+31 more)

### Community 9 - "HudCanvas"
Cohesion: 0.09
Nodes (15): QPainter, HudCanvas, Thread-safe entry point for the audio threads. Stores the louder of the…, True only when this canvas can actually be seen by the user., Draw the Avengers: Endgame Stark Arc Reactor at (cx, cy) with outer radius r., Draw subtle background CRT coordinate grid with + crosshairs (Screenshot 2)., 3D Rotating Vector Wireframe Globe (Matching Screenshot 2: WAKU CRT Globe).…, Futuristic Oscilloscope Waveforms spanning across the globe (Screenshot 1 & 2… (+7 more)

### Community 10 - "tts.py"
Cohesion: 0.07
Nodes (25): _compress_silence(), create_tts_player(), EdgeTTSEngine, ElevenLabsTTSEngine, _import_kokoro_pipeline(), KokoroTTSEngine, _synth(), _play_audio_bytes() (+17 more)

### Community 11 - "CentralizedCache"
Cohesion: 0.06
Nodes (22): CentralizedCache, _canonicalize(), decorator(), wrapper(), Any, Stores value in cache with TTL. Fails open gracefully if storage fails., Deletes a key from cache. Fails open gracefully., Invalidates all keys starting with prefix. Useful for mutation hooks. (+14 more)

### Community 12 - "web_search.py"
Cohesion: 0.07
Nodes (43): _get_live_weather(), Fetch live weather conditions without opening an external browser., _compare(), _fetch_item(), _ddg_news(), _ddg_search(), _format_ddg(), _format_news() (+35 more)

### Community 13 - ".__init__"
Cohesion: 0.10
Nodes (12): BiometricFingerprintWidget, _CameraPreview, CRTReconWidget, _EqualizerBarsWidget, MetricBar, QWidget, Halftone / CRT Dithered Optical Recon Scanner Widget (Screenshot 1: Top-Left…, Biometric Fingerprint Scanner Widget (Screenshot 1: Middle-Left Biometric Box).… (+4 more)

### Community 14 - "gmail_manager.py"
Cohesion: 0.07
Nodes (34): daily_brief(), _get_gmail_brief(), _get_greeting(), _get_reminders_brief(), _get_system_vitals(), Fetch unread emails summary via gmail_manager., Check scheduled reminders in ~/.alfred/reminders or ~/.jarvis/reminders., Inspect core CPU, RAM, and Battery vitals. (+26 more)

### Community 15 - "test_screen_processor.py"
Cohesion: 0.09
Nodes (18): capture_screen(), _compress(), format_visual_payload(), format_window_context(), Format the standard metadata block: [WINDOW_CONTEXT] App: <Name> | Title:…, Prepares the visual frame payload dictionary for the Gemini Live API…, Hybrid return payload for screen captures. - Behaves as a 3-tuple `(img_bytes,…, Captures primary or specified monitor, queries active OS window context,… (+10 more)

### Community 16 - "JarvisLive"
Cohesion: 0.05
Nodes (23): Restore ducked media applications to their exact original volume levels. :param…, unduck_media_apps(), LiveConnectConfig, JarvisLive, Chord pressed or released — may arrive on the hotkey thread., Stop JARVIS mid-speech: drain queued audio and open mic immediately., Worker loop consuming background jobs from background_task_queue., The optional knobs, kept apart so one bad field can be dropped wholesale. Every… (+15 more)

### Community 18 - "computer_control.py"
Cohesion: 0.15
Nodes (29): _base_dir(), _clear_field(), _click(), _clipboard_get(), _clipboard_paste(), computer_control(), _drag(), _focus_window() (+21 more)

### Community 19 - "dev_agent.py"
Cohesion: 0.12
Nodes (27): _build_project(), _classify_error(), _extract_culprit_script(), _fix_files(), _get_model(), _has_error(), _install_dependencies(), _is_rate_limit() (+19 more)

### Community 20 - "ui.py"
Cohesion: 0.12
Nodes (15): core_avatar, get_hud_style(), get_wake_word_enabled(), Whether local wake-word gating is on (assistant sleeps until 'Hey Jarvis')., Which centrepiece the HUD draws: the animated head, or the reactor core. Taste,…, pyqt6_qtcore, pyqt6_qtgui, pyqt6_qtmultimedia (+7 more)

### Community 21 - "memory_manager.py"
Cohesion: 0.08
Nodes (35): Update Daily Briefing Preferences Action for ALFRED Mark-LIV. Permanently…, Permanently saves daily briefing preferences into long-term memory., update_daily_briefing(), _do_shutdown(), Summarise the current session in 1-2 sentences and save to long_term.json., _all_entries(), all_entries_for_ui(), _empty_memory() (+27 more)

### Community 22 - ".run_local"
Cohesion: 0.12
Nodes (21): call_llm(), call_llm_stream(), _do_stream(), call_llm_text(), check_model_available(), ensure_ollama_running(), get_llm_provider(), get_llm_settings() (+13 more)

### Community 23 - "EchoGuard"
Cohesion: 0.08
Nodes (14): band_energies(), EchoGuard, ndarray, Classifies microphone blocks while the assistant is speaking. Usage:…, True once the estimate rests on enough real echo to be trusted., Residual left by this room's own echo. Higher = harder to separate., False when the acoustics are too poor to judge on content alone. Speakers…, The residual a block must clear right now to count as a voice. (+6 more)

### Community 24 - "ALFRED — MARK III (Wayne Protocol Edition)"
Cohesion: 0.06
Nodes (33): 10. Local Hybrid Visual Grounding (RapidOCR + ONNX + Gemini Fallback), 11. Process-Level Audio Ducking & Background Concurrency, 13. Bug Fixes & Stability Updates, 14. System Architecture & File Structure, 15. Quick Start & Installation, 16. Configuration Reference (`config/api_keys.json`), 17. Knowledge Graph (`graphify`), 18. Author & Credits (+25 more)

### Community 25 - "JarvisUI"
Cohesion: 0.06
Nodes (16): main(), JarvisUI, Thread-safe: raise the irreversible-action gate. Called from action handlers…, Thread-safe: take the gate down., Thread-safe: feed a 0.0–1.0 live audio level to the HUD waveform. Called from…, Ask the avatar to look somewhere for a moment (see HoloAvatar.glance)., Thread-safe: post a schedule of (level, openness, width) mouth frames for…, Thread-safe: wipe the on-screen conversation chat feed. (+8 more)

### Community 26 - "config_manager.py"
Cohesion: 0.13
Nodes (22): ensure_config_dir(), get_base_dir(), get_brief_enabled(), Path, Persist the chosen Live voice. Unknown names collapse to the default so a bad…, Read-modify-write one key without disturbing the rest of the config., Merge `values` into a namespace's stored config (read-modify-write, like every…, Persist assistant name and user name to config. (+14 more)

### Community 27 - "tech_font"
Cohesion: 0.18
Nodes (7): QPushButton, QVBoxLayout, PluginManagerOverlay, PluginSettingsOverlay, Floating overlay — lists discovered plugins with per-plugin ON/OFF toggles., Floating overlay — renders per-plugin settings forms. Fully generic: it…, tech_font()

### Community 28 - "mono_font"
Cohesion: 0.12
Nodes (10): QColor, QFont, QPixmap, _DropCanvas, _file_category(), _fmt_size(), mono_font(), qcol() (+2 more)

### Community 29 - "get_plugin_enabled"
Cohesion: 0.14
Nodes (11): _call_run(), PluginRegistry, One entry per settings SECTION, for enabled plugins that declare a…, Invoke run() passing only the kwargs it actually declares (or all of them if it…, How this plugin's result should re-enter the conversation, if it said., get_plugin_config(), get_plugin_enabled(), get_plugin_setting() (+3 more)

### Community 30 - "audio_devices.py"
Cohesion: 0.11
Nodes (21): configure(), _display_name(), _is_pseudo(), list_devices(), prefetch(), _work(), _query(), _collect() (+13 more)

### Community 32 - "screen_processor.py"
Cohesion: 0.08
Nodes (30): _base_dir(), _cv2_backend(), _detect_camera_index(), get_active_window_context(), get_active_window_info(), _get_camera_index(), _get_linux_window_info(), _get_macos_window_info() (+22 more)

### Community 33 - "desktop.py"
Cohesion: 0.12
Nodes (36): _ask_gemini_for_desktop_action(), _build_sandbox(), clean_desktop(), desktop_control(), _execute_generated_code(), _get_api_key(), _get_base_dir(), get_current_wallpaper() (+28 more)

### Community 34 - "_tlog"
Cohesion: 0.08
Nodes (19): FunctionResponse, _clean_transcript(), _is_repeat_chunk(), broadcast_progress(), _run_tool_bounded(), _deliver_news(), runner(), Queue a background task and return task metadata immediately. (+11 more)

### Community 35 - "is_heavenly_restricted"
Cohesion: 0.09
Nodes (27): apply_heal_patch(), dev_agent(), _diagnose_trace(), heal_execution_error(), _heuristic_repair(), Parses stderr and stack traces to isolate error category, line number, and…, Attempts fast, deterministic rule-based fixes for standard syntax and import…, r""" Automated diagnostic and self-repair engine for tool and script execution… (+19 more)

### Community 36 - "discover_actions"
Cohesion: 0.13
Nodes (11): ActionRecord, ActionRegistry, _call_handler(), discover_actions(), _opt_upper(), Path, Invoke the handler passing only the context kwargs it actually declares (or all…, Returns an ActionRecord; .valid=False + .error set on any problem. Never raises. (+3 more)

### Community 37 - "load_api_keys"
Cohesion: 0.11
Nodes (18): get_app_icon(), get_assistant_name(), get_gemini_key(), get_llm_provider(), get_media_resolution(), get_proactive_audio_enabled(), get_thinking_enabled(), get_turn_tuning() (+10 more)

### Community 38 - "PushToTalk"
Cohesion: 0.20
Nodes (5): PushToTalk, Begin watching. Returns the scope actually achieved., Feed a press/release from a Qt shortcut (non-Windows, or no hook)., Calls `on_change(held: bool)` whenever the chord is pressed or released. Start…, global' once a system-wide hook is running, else 'window'.

### Community 39 - "GraphManager"
Cohesion: 0.11
Nodes (14): GraphManager, Any, Path, Save the graph data to the JSON file atomically., Add an entity node to the graph. Returns True if successful., Add a relationship (edge) between two nodes. Returns True if successful., Apply exponential decay to all temporary nodes. Returns the number of nodes…, Query the knowledge graph for a concept and return connected subgraph up to… (+6 more)

### Community 40 - "._build_app"
Cohesion: 0.17
Nodes (10): _auth(), command(), list_files(), revoke_devices(), _safe_filename(), upload_file(), wake_ep(), ws_ep() (+2 more)

### Community 41 - "TestBackgroundWorkerPool"
Cohesion: 0.12
Nodes (7): Verify that calling interrupt() sets halt event, immediately stops active…, Verify that _safe_background_announce waits until ALFRED finishes speaking…, Verify DashboardServer tracks background tasks and exposes them via endpoint., Verify queue_background_task is registered in TOOL_DECLARATIONS., Verify that queue_background_task returns immediately (sub-millisecond), and…, Dispatch a mock task and verify voice PTT interaction continues with sub-second…, TestBackgroundWorkerPool

### Community 42 - "_index_file"
Cohesion: 0.09
Nodes (28): _ChangeHandler, _chunk_text(), _delete_file_chunks(), _detokenize_tokens(), _extract_text_from_file(), _get_chroma_collection(), _get_embedding_model(), _index_file() (+20 more)

### Community 43 - "TelemetryHUD"
Cohesion: 0.13
Nodes (11): main(), QWidget, Set up the update timer., Set up system tray icon for control., Handle mouse press for dragging., Handle mouse move for dragging., Update all telemetry displays., Main entry point for the HUD widget. (+3 more)

### Community 44 - "browser_control.py"
Cohesion: 0.24
Nodes (11): browser_control(), _find_exe_windows(), _find_opera_windows(), _log(), _normalize_url(), _open_native(), Bare words like "instagram" → "https://instagram.com" Domains like…, Opens the user's REAL browser normally — with their own profile, logged-in… (+3 more)

### Community 45 - "MemoryOverlay"
Cohesion: 0.33
Nodes (4): MemoryOverlay, Everything ALFRED has stored about you, and when it learned it. Memory used to…, Take every item out of the layout and detach it from the widget tree in this…, Size the panel to its content, re-centre it, and repaint what the old size…

### Community 46 - "main.py"
Cohesion: 0.10
Nodes (27): add_monitor(), check_all(), _is_blocked(), list_monitors(), _load(), BackgroundMonitor — user-configured topic watching. Checks DDG news once per…, Run all pending topic checks (once per day per topic). Returns a list of…, remove_monitor() (+19 more)

### Community 47 - "computer_settings"
Cohesion: 0.12
Nodes (16): brightness_get(), brightness_set(), computer_settings(), dark_mode(), paste(), press_key(), Current brightness 0-100, or None where it cannot be read., Set brightness to an absolute percentage. Only used to restore a value captured… (+8 more)

### Community 48 - "json"
Cohesion: 0.10
Nodes (26): Daily Brief Action for ALFRED Mark-LIV. Provides the ultimate morning and daily…, crawl_and_index(), actions/doc_rag.py — Local Document RAG with ChromaDB and nomic-embed-text-v1.5…, Crawl the allowed Desktop and Documents directories and index all files., Start watching the Desktop and Documents directories for changes., Stop the watchdog observer., start_watchdog(), stop_watchdog() (+18 more)

### Community 49 - "FileDropZone"
Cohesion: 0.10
Nodes (5): QDragEnterEvent, QDropEvent, CyberGraphicLineButton, FileDropZone, Tactical button rendered strictly with vector graphic lines, sharp 2px border…

### Community 50 - ".__init__"
Cohesion: 0.12
Nodes (5): _fl(), Floating overlay panel shown when the ⚙ header button is toggled., Collapsible panel below the HUD — shows search results, news, briefings. Hidden…, Returns True if auto-start is currently registered on this OS., Update application and window icon in realtime.

### Community 51 - "system_monitor.py"
Cohesion: 0.07
Nodes (38): _get_cpu_temp(), _get_gpu_usage(), get_system_status(), _is_private_or_loopback(), is_protected_process(), _nvml_gpu(), Any, actions/system_monitor.py — System Metric Checks, Process Tree Watchdog &… (+30 more)

### Community 52 - "get_input_device"
Cohesion: 0.21
Nodes (10): get_input_device(), get_output_device(), _patch_config(), Read-modify-write one or more keys in api_keys.json. Every setter in this file…, Microphone device name, or '' for the system default., Speaker device name, or '' for the system default., save_input_device(), save_output_device() (+2 more)

### Community 54 - "_is_reconnect_signal"
Cohesion: 0.50
Nodes (5): BaseException, _is_reconnect_signal(), _keep_context_of(), True if `exc` is a _ReconnectSignal, or a(n) (Base)ExceptionGroup that wraps…, Read `keep_context` off a reconnect signal, unwrapping the group the TaskGroup…

### Community 55 - "install_and_download"
Cohesion: 0.16
Nodes (8): install_and_download(), is_installed(), is_ready(), True if the openwakeword package is importable (no model check)., True if openwakeword is installed AND its model files are present on disk. This…, One-click setup for the UI button: pip-install openwakeword if missing, then…, _work(), Combined state for the two wake-word buttons. Readiness is a cheap,…

### Community 56 - "._build_right_panel"
Cohesion: 0.18
Nodes (3): QHBoxLayout, Read api_keys.json config dict. Returns {} on any error., _read_full_config()

### Community 57 - "_SessionRegistry"
Cohesion: 0.15
Nodes (5): _detect_default_browser(), Manages all active browser sessions., Is there an active automation session for this browser (or any)?, Returns the last natively-opened URL once (consumed to avoid repeats)., _SessionRegistry

### Community 58 - "clipboard_manager.py"
Cohesion: 0.05
Nodes (40): add_clipboard_item(), classify_content_type(), clipboard_manager_action(), ClipboardManager, cosine_similarity(), _get_active_window_info(), get_recent_clipboards(), is_sensitive_content() (+32 more)

### Community 59 - "echo.py"
Cohesion: 0.10
Nodes (12): is_ducked(), Return whether media ducking is currently active., Telling the user's voice apart from our own coming back through the speakers.…, ndarray, Speech-to-Text engines for MARK XL. Whisper – offline transcription via faster-…, Offline transcription using faster-whisper., Transcribe a float32 mono 16 kHz numpy array. Returns transcript string., Streaming transcription using Vosk. (+4 more)

### Community 61 - "RemoteKeyOverlay"
Cohesion: 0.27
Nodes (4): Floating overlay — QR code for instant phone pairing + manual key fallback., Call from any thread when a phone successfully connects., RemoteKeyOverlay, _lbl()

### Community 62 - "save_app_icon"
Cohesion: 0.20
Nodes (10): Update App Icon Action for ALFRED Mark-LIV. Switches the application window,…, Updates the main application icon and taskbar badge in realtime., update_app_icon(), Save the chosen app icon setting to config., save_app_icon(), format_icon_display_name(), get_available_app_icons(), Format an icon file name into an authentic, sleek tactical insignia title. (+2 more)

### Community 63 - "confirm.py"
Cohesion: 0.19
Nodes (13): bind(), _log(), _Pending, pending_title(), core/confirm.py — a confirmation the model cannot forge. THE PROBLEM WITH THE…, Called by the UI when the user presses CONFIRM or CANCEL. Runs the stored…, when nothing is waiting. Lets an action avoid stacking two banners., Wire this module to the HUD. Called once from main.py at startup. (+5 more)

### Community 64 - "datetime"
Cohesion: 0.23
Nodes (16): _base_dir(), _get_os(), Path, reminder(), _sanitise(), _schedule_linux(), _schedule_mac(), _schedule_windows() (+8 more)

### Community 66 - "VisemeStream"
Cohesion: 0.13
Nodes (12): collections, coverage(), Text → mouth shape, fused with the audio the avatar is actually speaking. Why…, Reduce any character to a bare Latin letter, or "" if it has none. This is what…, Fraction of the letters in `text` we can reduce to a Latin sound., Split a line of speech into (viseme, duration-weight) pairs. Returns [] for…, Fuses the transcript's shape sequence onto the audio's timing. Thread note:…, Blend audio frames [(level, openness, width)] with the text queue. (+4 more)

### Community 67 - "_SysMetrics"
Cohesion: 0.21
Nodes (4): Thread-safe speech channel for plugins: lets a plugin ask JARVIS to say…, _nvml_gpu_windows(), Return NVIDIA GPU utilisation % using nvml.dll directly — zero subprocess., _SysMetrics

### Community 68 - "._apply_name_update"
Cohesion: 0.16
Nodes (10): get_voice(), Return the configured Live voice, falling back to the default if unset or if…, apply_ui_accent(), current_palette(), Applies DOSSIER CRT [A-34] (#8e9bff), VECTOR CRT [WAKU] (#a8ff3e), or BATMAN…, A snapshot of the accent-linked colours currently on class C., LIVE full theme change. Replaces the old palette colours with the new ones in…, Live preview — paints the whole interface the new colour (does NOT write to… (+2 more)

### Community 69 - ".broadcast"
Cohesion: 0.24
Nodes (7): auto_login(), clear_chat_ep(), device_login_ep(), login(), phone_audio_ws(), _derive_key(), SHA-256(sessionKey‖salt) → 32-byte AES-256 key (microseconds, no PBKDF2 needed).

### Community 71 - "WakeWordDetector"
Cohesion: 0.20
Nodes (4): Runs the wake model in a dedicated thread. The mic thread calls feed() with raw…, Load the model and spawn the inference thread. Returns True on success. Safe to…, Called from the mic callback (real-time thread). Must stay cheap and never…, WakeWordDetector

### Community 73 - "intel_notes.py"
Cohesion: 0.31
Nodes (8): _auto_detect_type(), _config_dir(), intel_notes(), _load_notes(), Path, actions/intel_notes.py — Dedicated Intel & Notes Terminal Action. Provides a…, Action handler called by Gemini / action_loader., _save_notes()

### Community 74 - "pathlib"
Cohesion: 0.09
Nodes (28): Action discovery, validation, and dispatch — the built-in twin of…, _available(), install_for_config(), _pip(), MARK XL — Dependency auto-installer. Called automatically on first launch and…, Return True if the module can be imported (no actual import)., Install all missing packages required by *config*. Blocking — always call from…, get_base_dir() (+20 more)

### Community 75 - "._build_jarvis_icon"
Cohesion: 0.22
Nodes (4): Render an ALFRED tactical icon at 4× resolution and downsample for crisp…, Create a Windows .lnk shortcut WITHOUT launching PowerShell or cmd. Tries…, Resolve the user's REAL desktop directory instead of assuming ~/Desktop, which…, Create a desktop shortcut on Windows / macOS / Linux. Never opens a terminal,…

### Community 76 - ".__init__"
Cohesion: 0.40
Nodes (4): index(), _local_ip(), Return the best LAN-facing IPv4 address, no internet required., _read()

### Community 77 - "re"
Cohesion: 0.40
Nodes (3): main(), remove_emojis_from_headings(), re

### Community 78 - "._listen_audio"
Cohesion: 0.25
Nodes (7): callback(), _open_mic(), _pcm_level(), _pcm_visemes(), Map a block of int16 PCM samples to a 0.0–1.0 loudness level for the HUD…, Slice a PCM block into (level, openness, width) frames, one per 20 ms. Returns…, True while the speakers may still be finishing our last sentence.

### Community 79 - "LogWidget"
Cohesion: 0.25
Nodes (3): QTextEdit, LogWidget, Cancel any in-flight typing animation, drain the queue, and clear the display.

### Community 80 - "._apply_ptt_shortcut"
Cohesion: 0.29
Nodes (5): qt_sequence(), The same chord as a QKeySequence string., _press(), Bind the chord inside the window when no global hook is available. On macOS and…, Report a windowed press/release to whoever owns the microphone.

### Community 81 - ".test_error_isolation_in_concurrent_tasks"
Cohesion: 0.29
Nodes (5): Verify that an exception in one concurrent task does not break or cancel…, Verify that a batch of tasks run with a concurrency limit of 5 scales sub-…, TestConcurrencyLimiter, execute_task(), safe_run()

### Community 82 - "time"
Cohesion: 0.12
Nodes (16): asyncio, _make_uploads_dir(), Path, dashboard/server.py — ALFRED Local HTTP Dashboard Plain HTTP on port 8000 (no…, Return (and create) the cross-platform uploads folder., fastapi, fastapi_responses, hashlib (+8 more)

### Community 83 - "_ensure_network_access"
Cohesion: 0.20
Nodes (5): _ensure_certs(), _ensure_network_access(), Cross-platform, best-effort: open port in the OS firewall for LAN access. Runs…, Make sure config/certs holds a TLS key pair, generating a self-signed one the…, Second HTTPS server on PORT+1 sharing the same app and in-memory state. Chrome…

### Community 84 - "TestAudioDucker"
Cohesion: 0.29
Nodes (4): patch, Verify that duck_media_apps lowers target media processes by 70% (0.3 factor),…, Verify Linux pulsectl ducking fallback logic., TestAudioDucker

### Community 85 - ".__init__"
Cohesion: 0.11
Nodes (10): ProactiveEngine, ProactiveEngine 2.0 — context-aware, time-aware, non-repetitive background…, Decides when ALFRED should speak unprompted and builds a context-rich prompt.…, Build a context snapshot for Gemini. Rotates through three focus areas so…, _Popen, Exception, Turn hold-to-talk on or off. Returns the scope actually achieved., Raised inside the session TaskGroup to force a clean, voluntary reconnect (e.g.… (+2 more)

### Community 86 - "._launch"
Cohesion: 0.29
Nodes (5): _firefox_profile_dir(), launch_persistent_context already opens a starting tab. Instead of opening a…, Launches the browser with the real user profile. Does nothing if the context is…, _real_profile_dir(), Page

### Community 87 - "get_push_to_talk_enabled"
Cohesion: 0.29
Nodes (5): chord_label(), Human-readable name of the chord, for the UI and the logs., get_push_to_talk_enabled(), Hold-a-key-to-speak. When on, the mic is closed unless the chord is held., Repaint the push-to-talk row from the saved setting.

### Community 88 - "_detect_action"
Cohesion: 0.40
Nodes (5): _detect_action(), _normalise(), Resolve a free-text description to an action name, locally. Returns {"action":…, What to tell the model when nothing matched. Names real actions so its retry…, _suggest()

### Community 91 - "._toggle_sentry_mode"
Cohesion: 0.33
Nodes (3): Toggle continuous visual context (camera stream) monitoring., Thread-safe: start live camera feed in the full HUD area., Thread-safe: stop the live camera feed.

### Community 94 - "setup.py"
Cohesion: 0.36
Nodes (7): _check_assets(), _check_python(), main(), MARK LIV — one-time setup. Installs the Python dependencies for THIS operating…, Fail immediately and clearly rather than deep inside a pip resolver. A wrong…, The avatar's face is a shipped file; a truncated clone should say so., _run()

### Community 95 - "Daily Brief Protocol"
Cohesion: 0.50
Nodes (3): Daily Brief Protocol, Purpose, Rules

### Community 96 - "Email Handling Rules"
Cohesion: 0.50
Nodes (3): Email Handling Rules, Purpose, Rules

### Community 97 - "Executive Assistant Persona & Behavioral Standards"
Cohesion: 0.50
Nodes (3): Core Operational Rules, Executive Assistant Persona & Behavioral Standards, Persona & Demeanor

### Community 98 - "/email-triage Workflow"
Cohesion: 0.50
Nodes (3): /email-triage Workflow, Objective, Steps

### Community 99 - "_template.py"
Cohesion: 0.50
Nodes (3): Drop-in ALFRED plugin template. Copy this file, rename it (no leading…, parameters: dict of the args Gemini extracted, matching PLUGIN['parameters'].…, run()

### Community 100 - "_get_base_dir"
Cohesion: 0.67
Nodes (3): _get_api_key(), _get_base_dir(), Path

### Community 102 - "/deep-work Workflow"
Cohesion: 0.50
Nodes (3): /deep-work Workflow, Objective, Steps

### Community 104 - "duck_media_apps"
Cohesion: 0.29
Nodes (7): _duck_linux(), duck_media_apps(), _worker(), _duck_windows(), Execute ducking on Linux via pulsectl., Lower external media application volume (by default to 30%, i.e. ducking by…, Execute ducking on Windows via pycaw.

### Community 107 - "_VolumeSliderPopup"
Cohesion: 0.33
Nodes (3): QFrame, Sleek tactical cyber popup for adjusting master background music volume.…, _VolumeSliderPopup

### Community 109 - "calendar_sync.py"
Cohesion: 0.47
Nodes (5): _load_events(), Calendar Sync Plugin for ALFRED Mark-LIV. Tracks agenda, meetings,…, Execute calendar action., run(), _save_events()

### Community 112 - "weather_report.py"
Cohesion: 0.50
Nodes (4): _log(), weather_action(), urllib_parse, webbrowser

### Community 119 - "screen_find.py"
Cohesion: 0.07
Nodes (39): _calculate_similarity(), _capture_screen_image(), find_element(), _gemini_grounding(), _get_api_key(), _get_frame_key(), get_onnx_session(), get_rapid_ocr() (+31 more)

## Knowledge Gaps
- **41 isolated node(s):** `C`, `Purpose`, `Rules`, `Purpose`, `Rules` (+36 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 969 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **30 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `JarvisLive` connect `JarvisLive` to `DashboardServer`, `VisemeStream`, `_tlog`, `_SysMetrics`, `PushToTalk`, `WakeWordDetector`, `TestBackgroundWorkerPool`, `main.py`, `._listen_audio`, `time`, `system_monitor.py`, `.__init__`, `.run_local`, `EchoGuard`, `memory_manager.py`, `JarvisUI`?**
  _High betweenness centrality (0.051) - this node is a cross-community bridge._
- **Why does `JarvisUI` connect `JarvisUI` to `._apply_name_update`, `setter`, `.__init__`, `main.py`, `JarvisLive`, `._apply_ptt_shortcut`, `.__init__`, `ui.py`, `.__init__`, `install_and_download`, `._toggle_sentry_mode`, `.clear_chat`?**
  _High betweenness centrality (0.049) - this node is a cross-community bridge._
- **Why does `DashboardServer` connect `DashboardServer` to `.broadcast`, `._build_app`, `TestBackgroundWorkerPool`, `.__init__`, `main.py`, `JarvisLive`, `time`, `_ensure_network_access`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Are the 9 inferred relationships involving `JarvisLive` (e.g. with `ProactiveEngine` and `SystemMonitor`) actually correct?**
  _`JarvisLive` has 9 INFERRED edges - model-reasoned connections that need verification._
- **What connects `C`, `Purpose`, `Rules` to the rest of the system?**
  _41 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `game_updater.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06190476190476191 - nodes in this community are weakly interconnected._
- **Should `code_helper.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07402597402597402 - nodes in this community are weakly interconnected._