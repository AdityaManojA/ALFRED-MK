# Graph Report - Alfred-Mark-V  (2026-09-29)

## Corpus Check
- 121 files · ~210,548 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 15 file(s) not represented in the graph (top: .ico 7, (none) 3, .obj 2)

## Summary
- 2926 nodes · 5691 edges · 174 communities (144 shown, 30 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 249 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `2b5999ae`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- game_updater.py
- file_controller.py
- ClipboardManager
- file_processor.py
- web_search.py
- code_helper.py
- TelemetryHUD
- doc_rag.py
- system_monitor.py
- JarvisUI
- MinimizedHudOverlay
- computer_settings.py
- MainWindow
- dev_agent.py
- .run
- FileDropZone
- screen_find.py
- EchoGuard
- desktop.py
- plugin_loader.py
- qcol
- JarvisLive
- TestPluginSettingsSchemaCache
- setter
- TestScreenMonitorController
- get_plugin_enabled
- _tlog
- computer_control.py
- get_llm_settings
- datetime
- SpotifyClient
- TronScoreBackgroundPlayer
- _BrowserSession
- KokoroTTSEngine
- .test_error_isolation_in_concurrent_tasks
- .__init__
- audio_devices.py
- GraphManager
- DashboardServer
- CentralizedCache
- crypto-js.min.js
- ._apply_name_update
- HueWheel
- .__init__
- TacticalAudioPlayerWidget
- VisemeStream
- screen_processor.py
- protocol_engine.py
- load_api_keys
- spotify_control.py
- wake_word.py
- CustomizeOverlay
- computer_settings
- _patch_config
- tech_font
- get_input_device
- ._build_app
- AnalysisResult
- PushToTalk
- ._build_right_panel
- RemoteKeyOverlay
- mono_font
- _FakeButton
- LocalSTTManager
- NotesTerminalWidget
- _DropCanvas
- local_pipeline.py
- ALFRED — MARK-IV (Wayne Protocol Edition)
- _SysMetrics
- memory_manager.py
- unduck_media_apps
- undo.py
- WakeWordDetector
- TestMinimizedHudOverlay
- intel_notes.py
- TestHudReactivity
- ._build_jarvis_icon
- LocalPipelineCoordinator
- screen_monitor.py
- LogWidget
- main.py
- ScreenMonitorController
- MemoryOverlay
- SetupOverlay
- confirm.py
- .load_track
- ImagePopupOverlay
- delete_file
- ._aes_key
- _update_config
- config_manager.py
- save_app_icon
- _detect_action
- typing
- open_app.py
- get_push_to_talk_enabled
- 🎙️ 5. Master Tactical Voice Command Codex & Operational Handbook
- test_screen_processor.py
- LocalLLMManager
- Daily Brief Protocol
- Email Handling Rules
- Executive Assistant Persona & Behavioral Standards
- Detailed Step-by-Step Guide: How to Switch to a Local API
- /email-triage Workflow
- _template.py
- 8. Spotify AI Agent: Dual-Tier Web API & Native Playback Architecture
- _get_base_dir
- 🎭 3. Example & Fun Tactical Commands ("Wayne Protocol" in Action)
- Graphify + Antigravity Project Workflow & Setup Guide
- _get_macos_wifi_interface
- _scaled_icon_pixmap
- Q: Implement the ALFRED MK-IV translucent minimised HUD overlay plan from the pasted text.
- rules/graphify.md
- workflows/graphify.md
- chromadb
- chromadb_config
- Q: Remove Classic HUD mode from ALFRED MK-IV
- fastembed
- sentence_transformers
- TestAudioDucker
- watchdog_events
- watchdog_observers
- 1. What's New: Recent Enhancements, Bug Fixes & Stability Updates
- _RootShim
- control_playback
- README.md
- TestConfigCache
- TestScreenProcessorWindowContext
- get_user_name
- _read_full_config
- ._dispatch_tool
- get_active_window_info
- Q: Why did completed screen monitoring issue duplicate stop calls?
- Q: Why does opening Alfred show the old UI with no switch to the speech-reactive HUD?
- ui.py
- server.py
- Q: Read uiperformance.md and continousmonitoring.md and perform the tasks in the most efficient manner
- _undo_create
- capture_screen
- _ensure_network_access
- Q: Implement the ALFRED MK-IV speech-reactive graphical UI plan efficiently
- ScreenMonitorEvent
- .play
- 18. Quick Start & Installation
- EdgeTTSEngine
- setup.py
- TTSPlayer
- Q: change wake key to hey Alfred no t jarvis
- App Performance Plan
- _VolumeSliderPopup
- TestSpotifyApiOnlyPlayback
- ._listen_audio
- test_traceback_benchmark.py
- TestAudioCoreState
- SubjectDossierCard
- .__init__
- weather_report.py
- File & Folder Exploration and Notes Directives
- File & Folder Exploration Workflow
- ._decrypt
- Q: the hud text is quite hard to see
- _FakeController
- audio_core
- format_window_context
- get_plugin_config
- Step 1: Install & Set Up Your Preferred Local LLM Server
- .__init__
- _FakeUI
- _OAuthCallbackHandler

## God Nodes (most connected - your core abstractions)
1. `MainWindow` - 106 edges
2. `JarvisLive` - 80 edges
3. `JarvisUI` - 53 edges
4. `TronScoreBackgroundPlayer` - 39 edges
5. `tech_font()` - 38 edges
6. `mono_font()` - 37 edges
7. `_BrowserSession` - 32 edges
8. `ScreenMonitorController` - 30 edges
9. `computer_control()` - 26 edges
10. `is_heavenly_restricted()` - 26 edges

## Surprising Connections (you probably didn't know these)
- `1. File Opening (`open`)` --references--> `file_controller()`  [INFERRED]
  .agents/rules/file_exploration.md → actions/file_controller.py
- `2. Folder Exploration (`explore`)` --references--> `file_controller()`  [INFERRED]
  .agents/rules/file_exploration.md → actions/file_controller.py
- `Step 1: Target Identification` --references--> `file_controller()`  [INFERRED]
  .agents/workflows/file_explorer.md → actions/file_controller.py
- `3. Dedicated Intel & Notes Terminal (`intel_notes`)` --references--> `intel_notes()`  [INFERRED]
  .agents/rules/file_exploration.md → actions/intel_notes.py
- `High-Performance Client & Anti-Feedback Architecture` --references--> `SpotifyClient`  [INFERRED]
  readme.md → actions/spotify_control.py

## Import Cycles
- None detected.

## Communities (174 total, 30 thin omitted)

### Community 0 - "game_updater.py"
Cohesion: 0.06
Nodes (78): _build_google_flights_url(), flight_finder(), _format_spoken(), _format_text_report(), _get_base_dir(), _parse_date(), _parse_flights_with_gemini(), Path (+70 more)

### Community 1 - "file_controller.py"
Cohesion: 0.21
Nodes (26): copy_file(), create_file(), create_folder(), explore_folder(), file_controller(), find_files(), _format_size(), get_disk_usage() (+18 more)

### Community 2 - "ClipboardManager"
Cohesion: 0.05
Nodes (34): add_clipboard_item(), clipboard_manager_action(), ClipboardManager, cosine_similarity(), _get_active_window_info(), get_recent_clipboards(), paste_clipboard_item(), Any (+26 more)

### Community 3 - "file_processor.py"
Cohesion: 0.08
Nodes (44): _detect_type(), file_processor(), _file_size_str(), _gemini_client(), _output_path(), _process_archive(), _process_audio(), _process_code() (+36 more)

### Community 4 - "web_search.py"
Cohesion: 0.09
Nodes (38): _compare(), _fetch_item(), _ddg_news(), _ddg_search(), _format_ddg(), _format_news(), _gemini_available(), _gemini_headlines() (+30 more)

### Community 5 - "code_helper.py"
Cohesion: 0.08
Nodes (48): _build(), _clean_code(), code_helper(), _detect_intent(), _edit_action(), _explain_action(), _fix_code(), _get_gemini() (+40 more)

### Community 6 - "TelemetryHUD"
Cohesion: 0.13
Nodes (11): main(), QWidget, Set up the update timer., Set up system tray icon for control., Handle mouse press for dragging., Handle mouse move for dragging., Update all telemetry displays., Main entry point for the HUD widget. (+3 more)

### Community 7 - "doc_rag.py"
Cohesion: 0.07
Nodes (46): _ChangeHandler, _chunk_text(), crawl_and_index(), _delete_file_chunks(), _detokenize_tokens(), _extract_text_from_file(), _get_chroma_collection(), _get_embedding_model() (+38 more)

### Community 8 - "system_monitor.py"
Cohesion: 0.07
Nodes (38): _get_cpu_temp(), _get_gpu_usage(), get_system_status(), _is_private_or_loopback(), is_protected_process(), _nvml_gpu(), Any, actions/system_monitor.py — System Metric Checks, Process Tree Watchdog &… (+30 more)

### Community 9 - "JarvisUI"
Cohesion: 0.04
Nodes (22): JarvisUI, Thread-safe monitor state update used by click and voice controls., Thread-safe: raise the irreversible-action gate. Called from action handlers…, Thread-safe: take the gate down., Thread-safe: feed a 0.0–1.0 live audio level to the HUD waveform. Called from…, No-op: gaze tracking removed (face renderer removed)., Thread-safe: post a schedule of (level, openness, width) mouth frames for…, Thread-safe: wipe the on-screen conversation chat feed. (+14 more)

### Community 10 - "MinimizedHudOverlay"
Cohesion: 0.19
Nodes (3): QFont, MinimizedHudOverlay, Small independent transcript window shown while the main HUD is minimized.

### Community 12 - "MainWindow"
Cohesion: 0.05
Nodes (13): QMainWindow, MainWindow, Slot — display camera preview overlay (main thread)., Slot — runs on Qt main thread. Updates and shows the content panel., Slot — Qt main thread. Lays a document review into the content panel., Slot — Qt main thread. Puts a fresh quiz on the board., Place a floating overlay in the middle of the HUD and show it., Update bottom-left tactical audio player to display and control Spotify… (+5 more)

### Community 13 - "dev_agent.py"
Cohesion: 0.10
Nodes (35): apply_heal_patch(), _build_project(), _classify_error(), dev_agent(), _diagnose_trace(), _extract_culprit_script(), _fix_files(), _get_model() (+27 more)

### Community 14 - ".run"
Cohesion: 0.09
Nodes (15): BaseException, _get_api_key(), _is_reconnect_signal(), _do_shutdown(), _keep_context_of(), Summarise the current session in 1-2 sentences and save to long_term.json., Background task: voice alerts when metrics exceed thresholds., Check user-configured topics once per day; speak alerts when new headlines… (+7 more)

### Community 15 - "FileDropZone"
Cohesion: 0.11
Nodes (5): QDragEnterEvent, QDropEvent, CyberGraphicLineButton, FileDropZone, Tactical button rendered strictly with vector graphic lines, sharp 2px border…

### Community 16 - "screen_find.py"
Cohesion: 0.08
Nodes (29): _calculate_similarity(), _capture_screen_image(), _gemini_grounding(), _get_api_key(), _get_frame_key(), get_onnx_session(), get_rapid_ocr(), _ocr_grounding() (+21 more)

### Community 17 - "EchoGuard"
Cohesion: 0.07
Nodes (17): is_ducked(), Return whether media ducking is currently active., band_energies(), EchoGuard, ndarray, Telling the user's voice apart from our own coming back through the speakers.…, Classifies microphone blocks while the assistant is speaking. Usage:…, True once the estimate rests on enough real echo to be trusted. (+9 more)

### Community 18 - "desktop.py"
Cohesion: 0.12
Nodes (36): _ask_gemini_for_desktop_action(), _build_sandbox(), clean_desktop(), desktop_control(), _execute_generated_code(), _get_api_key(), _get_base_dir(), get_current_wallpaper() (+28 more)

### Community 19 - "plugin_loader.py"
Cohesion: 0.09
Nodes (20): copy, ActionRecord, ActionRegistry, _call_handler(), discover_actions(), _is_heavenly_restricted_params(), _opt_upper(), Path (+12 more)

### Community 20 - "qcol"
Cohesion: 0.08
Nodes (17): QColor, QPainter, HudCanvas, qcol(), No-op: gaze tracking removed (face renderer removed)., Thread-safe: hand over a schedule of (level, openness, width) frames. The…, Thread-safe entry point for the audio threads. Stores the louder of the…, True only when this canvas can actually be seen by the user. (+9 more)

### Community 21 - "JarvisLive"
Cohesion: 0.05
Nodes (18): JarvisLive, Fast callback used by the Sentry button on the Qt thread., Called when user clicks the CLEAR button in desktop GUI., Called when phone/dashboard sends a clear-chat directive., Chord pressed or released — may arrive on the hotkey thread., Load the detector once (model loads on first start). Idempotent., Called from the detector thread when the Alfred wake phrase is heard., Auto-sleep after the configured silence window (wake-word mode only). (+10 more)

### Community 23 - "setter"
Cohesion: 0.09
Nodes (5): setter, _work(), _plugin_settings_signature(), Stable identity for deciding whether a settings form can be reused., Combined state for the two wake-word buttons. Readiness is a cheap,…

### Community 24 - "TestScreenMonitorController"
Cohesion: 0.20
Nodes (3): TestScreenMonitorController, capture(), _wait_until()

### Community 25 - "get_plugin_enabled"
Cohesion: 0.11
Nodes (17): _call_run(), discover_plugins(), _load_error(), _opt_upper(), PluginRecord, PluginRegistry, Exception, Path (+9 more)

### Community 26 - "_tlog"
Cohesion: 0.08
Nodes (19): FunctionResponse, _clean_transcript(), _is_repeat_chunk(), broadcast_progress(), _run_tool_bounded(), _deliver_news(), main(), runner() (+11 more)

### Community 27 - "computer_control.py"
Cohesion: 0.10
Nodes (36): _base_dir(), _clear_field(), _click(), _clipboard_get(), _clipboard_paste(), computer_control(), _drag(), _focus_window() (+28 more)

### Community 28 - "get_llm_settings"
Cohesion: 0.15
Nodes (23): call_llm(), call_llm_stream(), _do_stream(), call_llm_text(), _chat_endpoint(), check_model_available(), ensure_ollama_running(), _get_headers() (+15 more)

### Community 29 - "datetime"
Cohesion: 0.06
Nodes (47): _get_gmail_brief(), Fetch unread emails summary via gmail_manager., _clean_header_str(), _extract_body_snippet(), fetch_unread_emails(), gmail_manager(), _load_gmail_creds(), Any (+39 more)

### Community 30 - "SpotifyClient"
Cohesion: 0.14
Nodes (12): High-performance Spotify client with connection pooling, token caching, device…, Loads Spotify credentials from config/api_keys.json or environment variables., Returns a valid access token, refreshing if needed., Playback endpoints require a user OAuth token, not client credentials., Controls playback: pause, resume, skip_next, skip_previous. Uses Spotify's Web…, Adds a track to the playback queue., Sets Spotify volume percentage (0-100)., Returns available Spotify devices with 5-minute TTL caching. (+4 more)

### Community 31 - "TronScoreBackgroundPlayer"
Cohesion: 0.09
Nodes (6): QObject, Background music audio engine. Plays background score continuously on loop…, Duck to 50% of base volume when speaking, restore to base volume when…, Called when Spotify plays a track. Pauses Tron background music, sets Spotify…, Specifically pause the local TRON audio core player regardless of mode., TronScoreBackgroundPlayer

### Community 32 - "_BrowserSession"
Cohesion: 0.05
Nodes (23): browser_control(), _BrowserSession, _detect_default_browser(), _find_exe_windows(), _find_opera_windows(), _firefox_profile_dir(), _log(), _normalize_url() (+15 more)

### Community 33 - "KokoroTTSEngine"
Cohesion: 0.14
Nodes (12): _compress_silence(), _import_kokoro_pipeline(), KokoroTTSEngine, _synth(), _play_np(), ndarray, Import KPipeline, auto-upgrading kokoro if a version mismatch is found. Old…, Fully offline Kokoro neural TTS. Model (~330 MB) is downloaded from HuggingFace… (+4 more)

### Community 34 - ".test_error_isolation_in_concurrent_tasks"
Cohesion: 0.29
Nodes (5): Verify that an exception in one concurrent task does not break or cancel…, Verify that a batch of tasks run with a concurrency limit of 5 scales sub-…, TestConcurrencyLimiter, execute_task(), safe_run()

### Community 35 - ".__init__"
Cohesion: 0.10
Nodes (11): ProactiveEngine, ProactiveEngine 2.0 — context-aware, time-aware, non-repetitive background…, Decides when ALFRED should speak unprompted and builds a context-rich prompt.…, Build a context snapshot for Gemini. Rotates through three focus areas so…, _Popen, Exception, Turn hold-to-talk on or off. Returns the scope actually achieved., Raised inside the session TaskGroup to force a clean, voluntary reconnect (e.g.… (+3 more)

### Community 36 - "audio_devices.py"
Cohesion: 0.11
Nodes (21): configure(), _display_name(), _is_pseudo(), list_devices(), prefetch(), _work(), _query(), _collect() (+13 more)

### Community 37 - "GraphManager"
Cohesion: 0.11
Nodes (14): GraphManager, Any, Path, Save the graph data to the JSON file atomically., Add an entity node to the graph. Returns True if successful., Add a relationship (edge) between two nodes. Returns True if successful., Apply exponential decay to all temporary nodes. Returns the number of nodes…, Query the knowledge graph for a concept and return connected subgraph up to… (+6 more)

### Community 38 - "DashboardServer"
Cohesion: 0.16
Nodes (3): DashboardServer, URL for manual browser entry. When HTTPS active, points to alias port (also…, Verify DashboardServer tracks background tasks and exposes them via endpoint.

### Community 39 - "CentralizedCache"
Cohesion: 0.06
Nodes (22): CentralizedCache, _canonicalize(), decorator(), wrapper(), Any, Stores value in cache with TTL. Fails open gracefully if storage fails., Deletes a key from cache. Fails open gracefully., Invalidates all keys starting with prefix. Useful for mutation hooks. (+14 more)

### Community 41 - "._apply_name_update"
Cohesion: 0.20
Nodes (8): apply_ui_accent(), current_palette(), Applies DOSSIER CRT [A-34] (#8e9bff), VECTOR CRT [WAKU] (#a8ff3e), or BATMAN…, A snapshot of the accent-linked colours currently on class C., LIVE full theme change. Replaces the old palette colours with the new ones in…, Live preview — paints the whole interface the new colour (does NOT write to…, Update all name/theme-dependent UI elements and persist to config., retheme_all_widgets()

### Community 42 - "HueWheel"
Cohesion: 0.16
Nodes (4): QPointF, QRectF, HueWheel, Circular colour picker. The user drags the handle (small white circle) around…

### Community 43 - ".__init__"
Cohesion: 0.08
Nodes (14): BiometricFingerprintWidget, _CameraPreview, CRTReconWidget, _EqualizerBarsWidget, ImagePopupOverlay, MetricBar, QWidget, Halftone / CRT Dithered Optical Recon Scanner Widget (Screenshot 1: Top-Left… (+6 more)

### Community 45 - "VisemeStream"
Cohesion: 0.13
Nodes (13): collections, coverage(), Text → mouth shape, fused with the audio the avatar is actually speaking. Why…, Reduce any character to a bare Latin letter, or "" if it has none. This is what…, Fraction of the letters in `text` we can reduce to a Latin sound., Split a line of speech into (viseme, duration-weight) pairs. Returns [] for…, Fuses the transcript's shape sequence onto the audio's timing. Thread note:…, Blend audio frames [(level, openness, width)] with the text queue. (+5 more)

### Community 46 - "screen_processor.py"
Cohesion: 0.15
Nodes (19): _base_dir(), _capture_camera(), _cv2_backend(), _detect_camera_index(), _get_camera_index(), _get_os(), _load_config(), _probe_camera() (+11 more)

### Community 47 - "protocol_engine.py"
Cohesion: 0.06
Nodes (49): create_protocol(), _do_save(), _ensure_user_protocols_dir(), execute_protocol(), _execute_tool(), get_action_registry(), _get_default_protocols_path(), get_protocols_file() (+41 more)

### Community 48 - "load_api_keys"
Cohesion: 0.09
Nodes (24): LiveConnectConfig, The optional knobs, kept apart so one bad field can be dropped wholesale. Every…, get_app_icon(), get_assistant_name(), get_gemini_key(), get_llm_provider(), get_media_resolution(), get_openrouter_key() (+16 more)

### Community 49 - "spotify_control.py"
Cohesion: 0.12
Nodes (19): authorize_user(), _get_base_dir(), get_spotify_client(), manage_queue(), Path, Spotify AI Agent & Playback Control for ALFRED. Provides Spotify Web API…, Main handler for the spotify_control action., Sends a native Windows WM_APPCOMMAND message to explicitly Pause, Play, or Stop. (+11 more)

### Community 50 - "wake_word.py"
Cohesion: 0.17
Nodes (12): install_and_download(), is_installed(), is_ready(), _prediction_score(), Local wake-word detection for ALFRED ("Hey Alfred"). Design goals: • ZERO cost…, Return the Alfred score while tolerating backend-specific key suffixes., True if the openwakeword package is importable (no model check)., True if openwakeword is installed AND its model files are present on disk. This… (+4 more)

### Community 51 - "CustomizeOverlay"
Cohesion: 0.19
Nodes (6): CustomizeOverlay, _lbl(), Floating glassmorphic overlay for configuring Assistant Persona, Commander…, Refresh reusable controls from persisted settings before showing., Highlight the selected voice pill; dim the rest., Updates the selected colour; hex box + wheel stay in sync, theme is live-…

### Community 52 - "computer_settings"
Cohesion: 0.12
Nodes (16): brightness_get(), brightness_set(), computer_settings(), dark_mode(), paste(), press_key(), Current brightness 0-100, or None where it cannot be read., Set brightness to an absolute percentage. Only used to restore a value captured… (+8 more)

### Community 53 - "_patch_config"
Cohesion: 0.18
Nodes (9): get_brief_enabled(), _patch_config(), Persist assistant name and user name to config., Persist the chosen Live voice. Unknown names collapse to the default so a bad…, Read-modify-write one or more keys in api_keys.json. Every setter in this file…, save_assistant_config(), save_brief_enabled(), save_openrouter_config() (+1 more)

### Community 54 - "tech_font"
Cohesion: 0.13
Nodes (9): QPushButton, QVBoxLayout, CapabilitiesOverlay, PluginManagerOverlay, PluginSettingsOverlay, Floating glassmorphic overlay displaying a categorized directory of everything…, Floating overlay — lists discovered plugins with per-plugin ON/OFF toggles., Floating overlay — renders per-plugin settings forms. Fully generic: it… (+1 more)

### Community 55 - "get_input_device"
Cohesion: 0.24
Nodes (8): get_input_device(), get_output_device(), Microphone device name, or '' for the system default., Speaker device name, or '' for the system default., save_input_device(), save_output_device(), AudioDeviceOverlay, Choose which microphone ALFRED listens to and which speakers it uses. Both…

### Community 56 - "._build_app"
Cohesion: 0.17
Nodes (11): action_ep(), audio_ws(), _auth(), download_file(), list_files(), phone_audio_ws(), _resolve_ws_auth(), _safe_filename() (+3 more)

### Community 57 - "AnalysisResult"
Cohesion: 0.20
Nodes (8): AnalysisResult, _default_analyzer(), Detect context, visual-frame, and explicit completion changes., One captured frame and its metadata, retained only until the next frame., Result returned by a screen analyzer., ScreenObservation, _FakeSession, TestScreenMonitorIntegration

### Community 58 - "PushToTalk"
Cohesion: 0.20
Nodes (5): PushToTalk, Begin watching. Returns the scope actually achieved., Feed a press/release from a Qt shortcut (non-Windows, or no hook)., Calls `on_change(held: bool)` whenever the chord is pressed or released. Start…, global' once a system-wide hook is running, else 'window'.

### Community 59 - "._build_right_panel"
Cohesion: 0.25
Nodes (3): QHBoxLayout, Style the COGNITIVE TRACE toggle to reflect its on/off state., Show or hide the agent's internal reasoning trace in the chat log.

### Community 60 - "RemoteKeyOverlay"
Cohesion: 0.24
Nodes (4): Floating overlay — QR code for instant phone pairing + manual key fallback., Call from any thread when a phone successfully connects., RemoteKeyOverlay, _lbl()

### Community 61 - "mono_font"
Cohesion: 0.14
Nodes (5): ClipboardPanel, mono_font(), Floating panel shown when text is copied — offers quick Alfred actions., Collapsible panel below the HUD — shows search results, news, briefings. Hidden…, Weight

### Community 62 - "_FakeButton"
Cohesion: 0.15
Nodes (5): Key Changes, _FakeButton, _FakeLog, Request screen-only monitoring from the application controller., Apply monitor state on the Qt thread for click and voice controls.

### Community 63 - "LocalSTTManager"
Cohesion: 0.05
Nodes (25): LocalSTTManager, audio_callback_wrapper(), Process audio bytes for transcription based on engine type., Cancel any pending debounce timer, thread-safe., Reset the FINISH_MS countdown from zero., Timer callback: commit the accumulated sentence to the queue., Immediately commit whatever is in the buffer (+ optional extra word)., Process audio using Vosk streaming STT. Final results are held for FINISH_MS… (+17 more)

### Community 65 - "_DropCanvas"
Cohesion: 0.25
Nodes (3): _DropCanvas, _file_category(), _fmt_size()

### Community 66 - "local_pipeline.py"
Cohesion: 0.08
Nodes (23): asyncio, Local audio pipeline coordinator for MARK XL. Handles STT → LLM → TTS flow for…, create_local_stt_engine(), Local Speech-to-Text wrappers for MARK XL. Provides unified interface for…, Factory function to create a local STT manager., create_local_tts_engine(), LocalTTSManager, Local Text-to-Speech wrappers for MARK XL. Provides unified interface for… (+15 more)

### Community 67 - "ALFRED — MARK-IV (Wayne Protocol Edition)"
Cohesion: 0.12
Nodes (15): 11. High-Performance Memory & Conversational Briefing Customizer, 12. Real-Time Insignia & Chassis Hot-Swapper, 13. Protocol Engine & Multi-Step Macro Playbooks (`config/protocols.yaml`), 14. Local Hybrid Visual Grounding (RapidOCR + ONNX + Gemini Fallback), 15. Process-Level Audio Ducking & Background Concurrency, 17. System Architecture & File Structure, 19. Configuration Reference (`config/api_keys.json`), 20. Knowledge Graph (`graphify`) (+7 more)

### Community 68 - "_SysMetrics"
Cohesion: 0.13
Nodes (7): Thread-safe speech channel for plugins: lets a plugin ask JARVIS to say…, Thread-safe: ask the run loop to tear down and rebuild the Live session. Called…, Voice picker applied. The voice is baked into the session at connect time, so a…, Microphone or speaker changed. Both streams are opened inside the session…, _nvml_gpu_windows(), Return NVIDIA GPU utilisation % using nvml.dll directly — zero subprocess., _SysMetrics

### Community 69 - "memory_manager.py"
Cohesion: 0.06
Nodes (45): daily_brief(), _get_live_weather(), _get_reminders_brief(), _get_system_vitals(), Check scheduled reminders in ~/.alfred/reminders or ~/.jarvis/reminders., Inspect core CPU, RAM, and Battery vitals., Executes the daily briefing and delivers spoken synthesis., Fetch live weather conditions without opening an external browser. (+37 more)

### Community 70 - "unduck_media_apps"
Cohesion: 0.12
Nodes (15): _duck_linux(), duck_media_apps(), _worker(), _duck_windows(), Execute ducking on Linux via pulsectl., Lower external media application volume (by default to 30%, i.e. ducking by…, Restore ducked media applications to their exact original volume levels. :param…, Execute ducking on Windows via pycaw. (+7 more)

### Community 71 - "undo.py"
Cohesion: 0.15
Nodes (11): clear(), _Entry, history(), peek(), core/undo.py — one shared undo stack for every action that changes state. WHY…, Forget the stack. Called when the app shuts down so closures holding old file…, Label of the operation that `undo_last()` would reverse, or ''., Most recent first — used by the UI panel and the `undo` tool's list mode. (+3 more)

### Community 72 - "WakeWordDetector"
Cohesion: 0.20
Nodes (4): Runs the wake model in a dedicated thread. The mic thread calls feed() with raw…, Load the model and spawn the inference thread. Returns True on success. Safe to…, Called from the mic callback (real-time thread). Must stay cheap and never…, WakeWordDetector

### Community 73 - "TestMinimizedHudOverlay"
Cohesion: 0.17
Nodes (3): _LogSource, QObject, TestMinimizedHudOverlay

### Community 74 - "intel_notes.py"
Cohesion: 0.31
Nodes (8): _auto_detect_type(), _config_dir(), intel_notes(), _load_notes(), Path, actions/intel_notes.py — Dedicated Intel & Notes Terminal Action. Provides a…, Action handler called by Gemini / action_loader., _save_notes()

### Community 75 - "TestHudReactivity"
Cohesion: 0.14
Nodes (3): TestHudReactivity, Acoustic control with a cheap listening-level outline., ReactiveMicButton

### Community 76 - "._build_jarvis_icon"
Cohesion: 0.22
Nodes (4): Render an ALFRED tactical icon at 4× resolution and downsample for crisp…, Create a Windows .lnk shortcut WITHOUT launching PowerShell or cmd. Tries…, Resolve the user's REAL desktop directory instead of assuming ~/Desktop, which…, Create a desktop shortcut on Windows / macOS / Linux. Never opens a terminal,…

### Community 77 - "LocalPipelineCoordinator"
Cohesion: 0.09
Nodes (18): create_local_pipeline(), LocalPipelineCoordinator, Coordinates STT → LLM → TTS flow., Set callbacks for UI updates., Log message via callback or print., Set UI state via callback., Start the local pipeline., Stop the local pipeline. (+10 more)

### Community 78 - "screen_monitor.py"
Cohesion: 0.20
Nodes (10): _fingerprint_key(), Reusable, in-memory continuous screen monitoring. The controller owns only the…, Return normalized mean absolute difference in the range 0.0 to 1.0., Return a tiny grayscale frame representation without writing image data., _visual_difference(), _visual_fingerprint(), io, pil (+2 more)

### Community 79 - "LogWidget"
Cohesion: 0.25
Nodes (3): QTextEdit, LogWidget, Cancel any in-flight typing animation, drain the queue, and clear the display.

### Community 80 - "main.py"
Cohesion: 0.15
Nodes (11): gc, google, google_genai, _describe_limits(), _describe_tools(), _load_system_prompt(), One line per capability, straight from the live tool declarations. Derived…, The other half of self-knowledge: what is out of reach, and why. Derived from… (+3 more)

### Community 81 - "ScreenMonitorController"
Cohesion: 0.16
Nodes (8): Exception, Poll screen capture in a daemon thread and retain only the latest frame., Start monitoring immediately; return false if a run is already active., Request a clean stop; optionally wait for the polling thread to exit., Return an immutable snapshot without copying or persisting image bytes., Thread-safe snapshot of controller state., ScreenMonitorController, ScreenMonitorStatus

### Community 82 - "MemoryOverlay"
Cohesion: 0.17
Nodes (8): ConfirmBanner, _HudOverlay, MemoryOverlay, Base for the floating panels placed by hand over the HUD. They are children of…, The gate in front of an action that cannot be taken back. The old confirmation…, Everything ALFRED has stored about you, and when it learned it. Memory used to…, Take every item out of the layout and detach it from the widget tree in this…, Size the panel to its content, re-centre it, and repaint what the old size…

### Community 83 - "SetupOverlay"
Cohesion: 0.20
Nodes (7): Update probe widgets on the Qt thread via a queued signal., SetupOverlay, _lbl(), _check(), _worker(), _check(), _worker()

### Community 84 - "confirm.py"
Cohesion: 0.21
Nodes (12): bind(), _log(), _Pending, pending_title(), core/confirm.py — a confirmation the model cannot forge. THE PROBLEM WITH THE…, Called by the UI when the user presses CONFIRM or CANCEL. Runs the stored…, when nothing is waiting. Lets an action avoid stacking two banners., Wire this module to the HUD. Called once from main.py at startup. (+4 more)

### Community 85 - ".load_track"
Cohesion: 0.18
Nodes (5): _base_dir(), Path, Set base normal volume (0.0 to 1.0). Speech ducking scales to 50% of base., Restores Tron legacy score as the default active audio., Specifically resume/play the local TRON audio core player.

### Community 86 - "ImagePopupOverlay"
Cohesion: 0.15
Nodes (9): action(), ImagePopupOverlay, QWidget, Handle mouse move for window dragging., Handle mouse release for window dragging., Show the popup centered over the parent widget., Show an image popup overlay., Popup overlay to display an image with a dismiss button. (+1 more)

### Community 87 - "delete_file"
Cohesion: 0.31
Nodes (11): delete_file(), _get_desktop(), _get_documents(), _get_downloads(), _get_music(), _get_pictures(), _get_videos(), Path (+3 more)

### Community 88 - "._aes_key"
Cohesion: 0.24
Nodes (7): auto_login(), clear_chat_ep(), device_login_ep(), login(), revoke_devices(), _derive_key(), SHA-256(sessionKey‖salt) → 32-byte AES-256 key (microseconds, no PBKDF2 needed).

### Community 89 - "_update_config"
Cohesion: 0.24
Nodes (8): ensure_config_dir(), Merge `values` into a namespace's stored config (read-modify-write, like every…, save_api_keys(), update(), save_plugin_config(), save_plugin_enabled(), save_turn_tuning(), _update_config()

### Community 90 - "config_manager.py"
Cohesion: 0.14
Nodes (19): _config_signature_unlocked(), get_base_dir(), get_hud_style(), get_plugin_settings_revision(), invalidate_config_cache(), _plugin_settings_state(), Path, The speech-reactive globe is the only supported HUD. (+11 more)

### Community 91 - "save_app_icon"
Cohesion: 0.40
Nodes (5): Update App Icon Action for ALFRED Mark-LIV. Switches the application window,…, Updates the main application icon and taskbar badge in realtime., update_app_icon(), Save the chosen app icon setting to config., save_app_icon()

### Community 92 - "_detect_action"
Cohesion: 0.40
Nodes (5): _detect_action(), _normalise(), Resolve a free-text description to an action name, locally. Returns {"action":…, What to tell the model when nothing matched. Names real actions so its retry…, _suggest()

### Community 93 - "typing"
Cohesion: 0.10
Nodes (23): Tactical Audio Core Control Action for ALFRED. Controls the tactical HUD's…, Process-level Audio Ducking for ALFRED. Automatically ducks background media…, Execute unducking on Windows via pycaw, restoring exact prior volume levels., Execute unducking on Linux via pulsectl., _unduck_linux(), _worker(), _unduck_windows(), core/cache.py — Centralized Caching Layer for ALFRED Mark-II. Provides high-… (+15 more)

### Community 94 - "open_app.py"
Cohesion: 0.22
Nodes (5): _normalize(), open_app(), /deep-work Workflow, Objective, Steps

### Community 95 - "get_push_to_talk_enabled"
Cohesion: 0.12
Nodes (10): chord_label(), Human-readable name of the chord, for the UI and the logs., get_push_to_talk_enabled(), Hold-a-key-to-speak. When on, the mic is closed unless the chord is held., save_push_to_talk_enabled(), _press(), Floating overlay panel shown when the ⚙ header button is toggled., Repaint the push-to-talk row from the saved setting. (+2 more)

### Community 96 - "🎙️ 5. Master Tactical Voice Command Codex & Operational Handbook"
Cohesion: 0.20
Nodes (10): 👁️ 1. Desktop Automation, Screen & Multimodal Vision, ⚙️ 2. Operating System, Hardware Settings & Applications, ⚡ 3. Compound Protocols & Workflow Macros, 🧠 4. Memory, History & Universal Reversibility, 📰 5. Intelligence, Briefings, News & Weather, 🎙️ 5. Master Tactical Voice Command Codex & Operational Handbook, 📱 6. Quantum Mobile Remote & Web Telemetry Uplink, 🎧 7. Spotify AI Agent & Music Streaming (+2 more)

### Community 97 - "test_screen_processor.py"
Cohesion: 0.16
Nodes (7): _capture_screen(), format_visual_payload(), Prepares the visual frame payload dictionary for the Gemini Live API…, Hybrid return payload for screen captures. - Behaves as a 3-tuple `(img_bytes,…, ScreenCapturePayload, Unit and integration tests for screen_processor.py window context grounding.…, tuple

### Community 98 - "LocalLLMManager"
Cohesion: 0.16
Nodes (8): LocalLLMManager, stream_callback(), Handle tool calls by executing them and getting final response., Manages local LLM interactions., Set system prompt and available tools., Add message to conversation history., Clear conversation history., Generate response from local LLM.

### Community 99 - "Daily Brief Protocol"
Cohesion: 0.50
Nodes (3): Daily Brief Protocol, Purpose, Rules

### Community 100 - "Email Handling Rules"
Cohesion: 0.50
Nodes (3): Email Handling Rules, Purpose, Rules

### Community 101 - "Executive Assistant Persona & Behavioral Standards"
Cohesion: 0.50
Nodes (3): Core Operational Rules, Executive Assistant Persona & Behavioral Standards, Persona & Demeanor

### Community 102 - "Detailed Step-by-Step Guide: How to Switch to a Local API"
Cohesion: 0.22
Nodes (9): 2. 100% Local & Air-Gapped Offline Execution: Switching from Gemini to Local API, Configuration Template for LM Studio / vLLM (OpenAI-Compatible):, Configuration Template for Ollama:, Configuration Template for OpenRouter API (Frontier Multi-Model Gateway):, Detailed Step-by-Step Guide: How to Switch to a Local API, Gemini Live API vs. Local Offline API Comparison, Step 2: Configure ALFRED's Target Backend in `config/api_keys.json`, Step 3: Launch ALFRED & Verify Connection (+1 more)

### Community 103 - "/email-triage Workflow"
Cohesion: 0.50
Nodes (3): /email-triage Workflow, Objective, Steps

### Community 104 - "_template.py"
Cohesion: 0.50
Nodes (3): Drop-in ALFRED plugin template. Copy this file, rename it (no leading…, parameters: dict of the args Gemini extracted, matching PLUGIN['parameters'].…, run()

### Community 105 - "8. Spotify AI Agent: Dual-Tier Web API & Native Playback Architecture"
Cohesion: 0.22
Nodes (9): 8. Spotify AI Agent: Dual-Tier Web API & Native Playback Architecture, Dual-Tier Control Architecture, Elimination of the Toggle Inversion Bug, High-Performance Client & Anti-Feedback Architecture, Key Capabilities & Default Music Routing, Spotify API & OAuth 2.0 Setup Guide, Step 1: Create a Spotify Developer Application, Step 2: Add Credentials to `config/api_keys.json` (+1 more)

### Community 106 - "_get_base_dir"
Cohesion: 0.67
Nodes (3): _get_api_key(), _get_base_dir(), Path

### Community 107 - "🎭 3. Example & Fun Tactical Commands ("Wayne Protocol" in Action)"
Cohesion: 0.40
Nodes (5): 🎭 3. Example & Fun Tactical Commands ("Wayne Protocol" in Action), 🎵 Ambience, Scores & Entertainment, 🎩 Distinguished Butler & Persona Banter, 🛡️ Insignia & Batcave Customization, 👁️ Tactical Vision & Screen Grounding

### Community 110 - "_scaled_icon_pixmap"
Cohesion: 0.33
Nodes (4): QPixmap, Pre-render the static grid-dot background into a transparent pixmap so…, Load and scale an icon once per file version and target size., _scaled_icon_pixmap()

### Community 111 - "Q: Implement the ALFRED MK-IV translucent minimised HUD overlay plan from the pasted text."
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Implement the ALFRED MK-IV translucent minimised HUD overlay plan from the pasted text., Source Nodes

### Community 116 - "Q: Remove Classic HUD mode from ALFRED MK-IV"
Cohesion: 0.50
Nodes (3): Answer, Q: Remove Classic HUD mode from ALFRED MK-IV, Source Nodes

### Community 124 - "TestAudioDucker"
Cohesion: 0.29
Nodes (4): patch, Verify that duck_media_apps lowers target media processes by 70% (0.3 factor),…, Verify Linux pulsectl ducking fallback logic., TestAudioDucker

### Community 127 - "1. What's New: Recent Enhancements, Bug Fixes & Stability Updates"
Cohesion: 0.18
Nodes (4): Called from Qt main thread when user presses Remote Control., 1. What's New: Recent Enhancements, Bug Fixes & Stability Updates, Thread-safe UI slot: wipe chat display., Wipe chat log and trigger any registered callback (e.g. backend/mobile sync).

### Community 132 - "TestScreenProcessorWindowContext"
Cohesion: 0.18
Nodes (6): Verifies system falls back to 'App: Unknown' without raising exceptions., Verification Requirement: Verify [WINDOW_CONTEXT] header contains VS Code and…, Verifies that active window query resolves in < 15ms and adheres to schema., Verifies metadata block is prepended directly to the visual frame payload., Verifies capture_screen() returns valid compressed image and window context., TestScreenProcessorWindowContext

### Community 133 - "get_user_name"
Cohesion: 0.50
Nodes (4): _get_greeting(), Generate time-contextual executive salutation., get_user_name(), Return the configured user name for addressing.

### Community 134 - "_read_full_config"
Cohesion: 0.22
Nodes (3): Read api_keys.json config dict. Returns {} on any error., Build expensive reusable settings widgets after first paint., _read_full_config()

### Community 135 - "._dispatch_tool"
Cohesion: 0.26
Nodes (13): add_monitor(), check_all(), _is_blocked(), list_monitors(), _load(), BackgroundMonitor — user-configured topic watching. Checks DDG news once per…, Run all pending topic checks (once per day per topic). Returns a list of…, remove_monitor() (+5 more)

### Community 136 - "get_active_window_info"
Cohesion: 0.20
Nodes (10): get_active_window_context(), get_active_window_info(), _get_linux_window_info(), _get_macos_window_info(), _get_windows_window_info(), Query foreground window handle, title, and process name on Windows., Query active frontmost window on macOS via Quartz or AppleScript fallback., Query active window on Linux via xdotool or wmctrl. (+2 more)

### Community 137 - "Q: Why did completed screen monitoring issue duplicate stop calls?"
Cohesion: 0.50
Nodes (3): Answer, Q: Why did completed screen monitoring issue duplicate stop calls?, Source Nodes

### Community 138 - "Q: Why does opening Alfred show the old UI with no switch to the speech-reactive HUD?"
Cohesion: 0.50
Nodes (3): Answer, Q: Why does opening Alfred show the old UI with no switch to the speech-reactive HUD?, Source Nodes

### Community 139 - "ui.py"
Cohesion: 0.09
Nodes (37): classify_content_type(), is_sensitive_content(), actions/clipboard_manager.py — Persistent, Semantically Indexed Clipboard…, Determine category: url, email, json, code, or text., Detect if content originates from a password manager or contains high-entropy…, Daily Brief Action for ALFRED Mark-LIV. Provides the ultimate morning and daily…, Action to show an image popup overlay., get_base_dir() (+29 more)

### Community 140 - "server.py"
Cohesion: 0.11
Nodes (17): base64, index(), _ensure_certs(), _local_ip(), _make_uploads_dir(), Path, dashboard/server.py — ALFRED Local HTTP Dashboard Plain HTTP on port 8000 (no…, Return the best LAN-facing IPv4 address, no internet required. (+9 more)

### Community 141 - "Q: Read uiperformance.md and continousmonitoring.md and perform the tasks in the most efficient manner"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Read uiperformance.md and continousmonitoring.md and perform the tasks in the most efficient manner, Source Nodes

### Community 142 - "_undo_create"
Cohesion: 0.22
Nodes (7): Reverse of a move: put it back where it came from., Reverse of a create: remove what we made — and only if we still made it.…, Reverse of a write: restore the old contents, or remove a file that did not…, _undo_create(), _undo_move(), _fn(), _undo_write()

### Community 143 - "capture_screen"
Cohesion: 0.20
Nodes (10): capture_screen(), _compress(), Captures primary or specified monitor, queries active OS window context,…, Default entry point used by main.py., Assumptions, Continuous Screen Monitoring Plan, Monitoring Behavior, Stop Conditions (+2 more)

### Community 144 - "_ensure_network_access"
Cohesion: 0.25
Nodes (3): _ensure_network_access(), Cross-platform, best-effort: open port in the OS firewall for LAN access. Runs…, Second HTTPS server on PORT+1 sharing the same app and in-memory state. Chrome…

### Community 145 - "Q: Implement the ALFRED MK-IV speech-reactive graphical UI plan efficiently"
Cohesion: 0.50
Nodes (3): Answer, Q: Implement the ALFRED MK-IV speech-reactive graphical UI plan efficiently, Source Nodes

### Community 146 - "ScreenMonitorEvent"
Cohesion: 0.36
Nodes (3): Event delivered to meaningful-state and completion callbacks., ScreenMonitorEvent, Forward selected changed frames from the monitor thread to the AI loop.

### Community 147 - ".play"
Cohesion: 0.32
Nodes (6): get_devices(), Any, Search Spotify for tracks, albums, artists, or playlists., Start playback through Spotify Connect without opening a local app., spotify_search(), start_playback()

### Community 148 - "18. Quick Start & Installation"
Cohesion: 0.67
Nodes (3): 18. Quick Start & Installation, 1. Prerequisites, 2. Setup & Execution

### Community 149 - "EdgeTTSEngine"
Cohesion: 0.29
Nodes (4): EdgeTTSEngine, _play_audio_bytes(), Microsoft EdgeTTS – free, requires internet., Decode MP3/WAV/OGG bytes and play via sounddevice (uses miniaudio).

### Community 150 - "setup.py"
Cohesion: 0.36
Nodes (7): _check_assets(), _check_python(), main(), MARK LIV — one-time setup. Installs the Python dependencies for THIS operating…, Fail immediately and clearly rather than deep inside a pip resolver. A wrong…, The avatar's face is a shipped file; a truncated clone should say so., _run()

### Community 151 - "TTSPlayer"
Cohesion: 0.29
Nodes (3): Wraps any *Engine. Exposes a blocking speak() method meant to be called from a…, Synthesise and play text. BLOCKING – call from a dedicated thread., TTSPlayer

### Community 152 - "Q: change wake key to hey Alfred no t jarvis"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: change wake key to hey Alfred no t jarvis, Source Nodes

### Community 153 - "App Performance Plan"
Cohesion: 0.33
Nodes (5): App Performance Plan, Assumptions, Key Changes, Summary, Test Plan

### Community 154 - "_VolumeSliderPopup"
Cohesion: 0.33
Nodes (3): QFrame, Sleek tactical cyber popup for adjusting master background music volume.…, _VolumeSliderPopup

### Community 156 - "._listen_audio"
Cohesion: 0.40
Nodes (3): callback(), _open_mic(), True while the speakers may still be finishing our last sentence.

### Community 157 - "test_traceback_benchmark.py"
Cohesion: 0.40
Nodes (4): _parse_traceback(), Performance Benchmark: dev_agent._parse_traceback Tests O(1) hash map lookups…, Measures lookup time across 50,000 mock project files and 500 stack frames., TestTracebackBenchmark

### Community 160 - ".__init__"
Cohesion: 0.40
Nodes (4): AnalysisCallback, CaptureCallback, EventCallback, StoppedCallback

### Community 161 - "weather_report.py"
Cohesion: 0.50
Nodes (4): _log(), weather_action(), urllib_parse, webbrowser

### Community 162 - "File & Folder Exploration and Notes Directives"
Cohesion: 0.40
Nodes (4): 1. File Opening (`open`), 2. Folder Exploration (`explore`), 3. Dedicated Intel & Notes Terminal (`intel_notes`), File & Folder Exploration and Notes Directives

### Community 163 - "File & Folder Exploration Workflow"
Cohesion: 0.40
Nodes (4): File & Folder Exploration Workflow, Step 1: Target Identification, Step 2: Open File vs Explore Folder, Step 3: Record Intel or Links

### Community 164 - "._decrypt"
Cohesion: 0.40
Nodes (4): command(), ws_ep(), _decrypt_cbc(), Decrypt base64(IV[16] ‖ ciphertext) with AES-256-CBC + PKCS7.

### Community 165 - "Q: the hud text is quite hard to see"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: the hud text is quite hard to see, Source Nodes

### Community 167 - "audio_core"
Cohesion: 0.50
Nodes (4): audio_core(), Any, Main handler for the Audio Core control action., 7. Dual-Mode Tactical Audio Matrix & Background Sound Engine

### Community 168 - "format_window_context"
Cohesion: 0.50
Nodes (3): format_window_context(), Format the standard metadata block: [WINDOW_CONTEXT] App: <Name> | Title:…, Verifies exact string formatting requirements.

### Community 169 - "get_plugin_config"
Cohesion: 0.50
Nodes (4): get_plugin_config(), get_plugin_setting(), All stored values for a namespace (empty dict if none set yet)., A single value from a namespace, or `default` if unset.

### Community 170 - "Step 1: Install & Set Up Your Preferred Local LLM Server"
Cohesion: 0.50
Nodes (4): Option A: Ollama (Recommended — Simplest Setup), Option B: LM Studio (Recommended for GUI Users), Option C: vLLM or llama.cpp (High-Throughput / Linux Servers), Step 1: Install & Set Up Your Preferred Local LLM Server

### Community 171 - ".__init__"
Cohesion: 0.10
Nodes (9): format_icon_display_name(), get_available_app_icons(), _fl(), Open the API key and neural backend configuration overlay from settings., Update application and window icon in realtime., Format an icon file name into an authentic, sleek tactical insignia title., Returns True if auto-start is currently registered on this OS., Scan Icons/ and config/ for all available badges/icons. (+1 more)

## Knowledge Gaps
- **84 isolated node(s):** `Purpose`, `Rules`, `Purpose`, `Rules`, `Persona & Demeanor` (+79 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1231 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **30 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Work-memory lessons

**Preferred sources** — corroborated by past sessions; start here.
- `MinimizedHudOverlay` (2× useful, score=1.999551435) _(code changed — re-verify)_

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MainWindow` connect `MainWindow` to `_DropCanvas`, `_read_full_config`, `._apply_name_update`, `ui.py`, `.__init__`, `.__init__`, `_scaled_icon_pixmap`, `._build_jarvis_icon`, `_patch_config`, `tech_font`, `setter`, `AnalysisResult`, `._build_right_panel`, `1. What's New: Recent Enhancements, Bug Fixes & Stability Updates`, `mono_font`, `_FakeButton`, `get_push_to_talk_enabled`?**
  _High betweenness centrality (0.086) - this node is a cross-community bridge._
- **Why does `JarvisLive` connect `JarvisLive` to `._dispatch_tool`, `system_monitor.py`, `JarvisUI`, `ui.py`, `.run`, `EchoGuard`, `ScreenMonitorEvent`, `_tlog`, `._listen_audio`, `.__init__`, `DashboardServer`, `VisemeStream`, `load_api_keys`, `AnalysisResult`, `PushToTalk`, `_FakeButton`, `_SysMetrics`, `unduck_media_apps`, `WakeWordDetector`, `main.py`, `ScreenMonitorController`, `1. What's New: Recent Enhancements, Bug Fixes & Stability Updates`?**
  _High betweenness centrality (0.071) - this node is a cross-community bridge._
- **Why does `JarvisUI` connect `JarvisUI` to `control_playback`, `.__init__`, `._apply_name_update`, `ui.py`, `.__init__`, `.__init__`, `main.py`, `qcol`, `JarvisLive`, `setter`, `_tlog`, `get_push_to_talk_enabled`, `1. What's New: Recent Enhancements, Bug Fixes & Stability Updates`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `JarvisLive` (e.g. with `Key Changes` and `ProactiveEngine`) actually correct?**
  _`JarvisLive` has 14 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Purpose`, `Rules`, `Purpose` to the rest of the system?**
  _84 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `game_updater.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06190476190476191 - nodes in this community are weakly interconnected._
- **Should `ClipboardManager` be split into smaller, more focused modules?**
  _Cohesion score 0.05194805194805195 - nodes in this community are weakly interconnected._