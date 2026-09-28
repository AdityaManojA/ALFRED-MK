# Graph Report - Alfred-Mark-V  (2026-09-29)

## Corpus Check
- 127 files · ~215,125 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 15 file(s) not represented in the graph (top: .ico 7, (none) 3, .obj 2)

## Summary
- 3015 nodes · 5856 edges · 185 communities (147 shown, 38 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 266 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `9a8d0eab`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- game_updater.py
- file_controller.py
- clipboard_manager.py
- file_processor.py
- web_search.py
- code_helper.py
- TelemetryHUD
- doc_rag.py
- system_monitor.py
- JarvisUI
- profile_alfred_ui.py
- MainWindow
- dev_agent.py
- .run
- FileDropZone
- screen_find.py
- EchoGuard
- send_message.py
- action_loader.py
- HudCanvas
- JarvisLive
- TestPluginSettingsSchemaCache
- setter
- AnalysisResult
- plugin_loader.py
- _tlog
- computer_control.py
- local_pipeline.py
- gmail_manager.py
- SpotifyClient
- TronScoreBackgroundPlayer
- _BrowserSession
- tts.py
- .test_error_isolation_in_concurrent_tasks
- .__init__
- audio_devices.py
- GraphManager
- DashboardServer
- CentralizedCache
- crypto-js.min.js
- ._apply_name_update
- MinimizedHudOverlay
- mono_font
- TacticalAudioPlayerWidget
- VisemeStream
- screen_processor.py
- protocol_engine.py
- main.py
- spotify_control.py
- wake_word.py
- CustomizeOverlay
- computer_settings
- desktop.py
- tech_font
- load_api_keys
- ._build_app
- TestProtocolEngine
- PushToTalk
- find_element
- RemoteKeyOverlay
- json
- time
- LocalSTTManager
- NotesTerminalWidget
- qcol
- LocalTTSManager
- ALFRED MARK-VI (Wayne Protocol Edition)
- _SysMetrics
- memory_manager.py
- unduck_media_apps
- window_manager.py
- WakeWordDetector
- TestBackgroundWorkerPool
- intel_notes.py
- TestHudReactivity
- ._build_jarvis_icon
- ._log
- screen_monitor.py
- LogWidget
- ProactiveEngine
- ScreenMonitorController
- MemoryOverlay
- SetupOverlay
- confirm.py
- control_playback
- ImagePopupOverlay
- is_heavenly_restricted
- ._aes_key
- _update_config
- config_manager.py
- update_app_icon.py
- _detect_action
- daily_brief.py
- open_app
- get_push_to_talk_enabled
- audio_ducker.py
- ._dispatch_tool
- LocalLLMManager
- Daily Brief Protocol
- Email Handling Rules
- Executive Assistant Persona & Behavioral Standards
- Detailed Step-by-Step Guide: How to Switch to a Local API
- /email-triage Workflow
- _template.py
- 8. Spotify AI Agent: Dual-Tier Web API & Native Playback Architecture
- _get_base_dir
- test_cache.py
- Graphify + Antigravity Project Workflow & Setup Guide
- _get_macos_wifi_interface
- ._make_grid
- Q: Implement the ALFRED MK-IV translucent minimised HUD overlay plan from the pasted text.
- rules/graphify.md
- workflows/graphify.md
- chromadb
- chromadb_config
- Q: Remove Classic HUD mode from ALFRED MK-IV
- fastembed
- _get_user_protocols_path
- sentence_transformers
- TestAudioDucker
- watchdog_events
- watchdog_observers
- re
- _RootShim
- .set_spotify_playback_state
- README.md
- TestConfigCache
- echo.py
- daily_brief
- datetime
- background_monitor.py
- CyberGraphicLineButton
- Q: Why did completed screen monitoring issue duplicate stop calls?
- Q: Why does opening Alfred show the old UI with no switch to the speech-reactive HUD?
- ui.py
- server.py
- Q: Read uiperformance.md and continousmonitoring.md and perform the tasks in the most efficient manner
- LocalPipelineCoordinator
- ._receive_audio
- _ensure_network_access
- Q: Implement the ALFRED MK-IV speech-reactive graphical UI plan efficiently
- ScreenMonitorEvent
- .play
- 18. Quick Start & Installation
- Ã°Å¸Å½â„¢Ã¯Â¸Â 5. Master Tactical Voice Command Codex & Operational Handbook
- setup.py
- TTSPlayer
- Q: change wake key to hey Alfred no t jarvis
- _gemini_grounding
- _VolumeSliderPopup
- TestSpotifyApiOnlyPlayback
- ._listen_audio
- ._set_state
- TestAudioCoreState
- ._apply_ptt_shortcut
- .__init__
- weather_report.py
- news_brief.py
- process_manager.py
- ._decrypt
- Q: the hud text is quite hard to see
- TestScreenMonitorIntegration
- audio_core
- band_energies
- get_plugin_config
- Step 1: Install & Set Up Your Preferred Local LLM Server
- TestMemoryTrimBenchmark
- DailyBriefPerformanceTests
- _OAuthCallbackHandler
- Q: Fix Spotify playback, Audio Core now-playing display, inverted startup play button, and avoid opening the Spotify desktop app.
- Ã°Å¸Å½Â­ 3. Example & Fun Tactical Commands ("Wayne Protocol" in Action)
- _EqualizerBarsWidget
- ._paint_3d_vector_globe
- .interrupt
- .__init__
- 22. Mark VI Enhancements
- .muted
- config
- core
- memory

## God Nodes (most connected - your core abstractions)
1. `MainWindow` - 106 edges
2. `JarvisLive` - 82 edges
3. `JarvisUI` - 53 edges
4. `TronScoreBackgroundPlayer` - 39 edges
5. `tech_font()` - 38 edges
6. `mono_font()` - 37 edges
7. `_BrowserSession` - 32 edges
8. `ScreenMonitorController` - 28 edges
9. `computer_control()` - 26 edges
10. `is_heavenly_restricted()` - 26 edges

## Surprising Connections (you probably didn't know these)
- `3. Dedicated Intel & Notes Terminal (`intel_notes`)` --references--> `intel_notes()`  [INFERRED]
  .agents/rules/file_exploration.md → actions/intel_notes.py
- `High-Performance Client & Anti-Feedback Architecture` --references--> `SpotifyClient`  [INFERRED]
  readme.md → actions/spotify_control.py
- `7. Dual-Mode Tactical Audio Matrix & Background Sound Engine` --references--> `audio_core()`  [INFERRED]
  readme.md → actions/audio_core.py
- `Steps` --references--> `computer_control()`  [INFERRED]
  .agents/workflows/deep_work.md → actions/computer_control.py
- `4. Security, Privacy & Defensive Architecture` --references--> `computer_control()`  [INFERRED]
  readme.md → actions/computer_control.py

## Import Cycles
- None detected.

## Communities (185 total, 38 thin omitted)

### Community 0 - "game_updater.py"
Cohesion: 0.06
Nodes (77): _build_google_flights_url(), flight_finder(), _format_spoken(), _format_text_report(), _get_base_dir(), _parse_date(), _parse_flights_with_gemini(), Path (+69 more)

### Community 1 - "file_controller.py"
Cohesion: 0.07
Nodes (63): copy_file(), create_file(), create_folder(), delete_file(), explore_folder(), file_controller(), find_files(), _format_size() (+55 more)

### Community 2 - "clipboard_manager.py"
Cohesion: 0.05
Nodes (40): add_clipboard_item(), classify_content_type(), clipboard_manager_action(), ClipboardManager, cosine_similarity(), _get_active_window_info(), get_recent_clipboards(), is_sensitive_content() (+32 more)

### Community 3 - "file_processor.py"
Cohesion: 0.08
Nodes (44): _detect_type(), file_processor(), _file_size_str(), _gemini_client(), _output_path(), _process_archive(), _process_audio(), _process_code() (+36 more)

### Community 4 - "web_search.py"
Cohesion: 0.14
Nodes (25): _compare(), _fetch_item(), _ddg_search(), _format_ddg(), _gemini_available(), _gemini_search(), _get_base_dir(), _get_ddgs() (+17 more)

### Community 5 - "code_helper.py"
Cohesion: 0.07
Nodes (50): _build(), _clean_code(), code_helper(), _detect_intent(), _edit_action(), _explain_action(), _fix_code(), _get_gemini() (+42 more)

### Community 6 - "TelemetryHUD"
Cohesion: 0.13
Nodes (11): main(), QWidget, Set up the update timer., Set up system tray icon for control., Handle mouse press for dragging., Handle mouse move for dragging., Update all telemetry displays., Main entry point for the HUD widget. (+3 more)

### Community 7 - "doc_rag.py"
Cohesion: 0.09
Nodes (35): _ChangeHandler, _chunk_text(), crawl_and_index(), _delete_file_chunks(), _detokenize_tokens(), _extract_text_from_file(), _get_chroma_collection(), _get_embedding_model() (+27 more)

### Community 8 - "system_monitor.py"
Cohesion: 0.07
Nodes (37): _get_cpu_temp(), _get_gpu_usage(), get_system_status(), _is_private_or_loopback(), is_protected_process(), _nvml_gpu(), Any, actions/system_monitor.py — System Metric Checks, Process Tree Watchdog &… (+29 more)

### Community 9 - "JarvisUI"
Cohesion: 0.04
Nodes (24): main(), JarvisUI, Update application and window icon in realtime., Thread-safe monitor state update used by click and voice controls., Thread-safe: raise the irreversible-action gate. Called from action handlers…, Thread-safe: take the gate down., Thread-safe: feed a 0.0–1.0 live audio level to the HUD waveform. Called from…, No-op: gaze tracking removed (face renderer removed). (+16 more)

### Community 10 - "profile_alfred_ui.py"
Cohesion: 0.13
Nodes (17): argparse, cprofile, faulthandler, Profile, pstats, _install_probes(), instrumented_init(), pulse() (+9 more)

### Community 12 - "MainWindow"
Cohesion: 0.04
Nodes (16): QHBoxLayout, QMainWindow, MainWindow, Slot — display camera preview overlay (main thread)., Slot — runs on Qt main thread. Updates and shows the content panel., Slot — Qt main thread. Lays a document review into the content panel., Slot — Qt main thread. Puts a fresh quiz on the board., Returns True if auto-start is currently registered on this OS. (+8 more)

### Community 13 - "dev_agent.py"
Cohesion: 0.09
Nodes (37): apply_heal_patch(), _build_project(), _classify_error(), dev_agent(), _diagnose_trace(), _extract_culprit_script(), _fix_files(), _get_model() (+29 more)

### Community 14 - ".run"
Cohesion: 0.10
Nodes (14): BaseException, _get_api_key(), _is_reconnect_signal(), _stream_worker(), _keep_context_of(), Wait until speech, user input, and tool execution have all settled., Serialize unsolicited model turns so they cannot split or overlap audio., Background task: voice alerts when metrics exceed thresholds. (+6 more)

### Community 15 - "FileDropZone"
Cohesion: 0.21
Nodes (3): QDragEnterEvent, QDropEvent, FileDropZone

### Community 16 - "screen_find.py"
Cohesion: 0.15
Nodes (18): _calculate_similarity(), _get_frame_key(), get_onnx_session(), get_rapid_ocr(), _ocr_grounding(), Any, ndarray, actions/screen_find.py — Local Hybrid Element Grounding for ALFRED. Performs… (+10 more)

### Community 17 - "EchoGuard"
Cohesion: 0.11
Nodes (9): EchoGuard, Classifies microphone blocks while the assistant is speaking. Usage:…, True once the estimate rests on enough real echo to be trusted., Residual left by this room's own echo. Higher = harder to separate., False when the acoustics are too poor to judge on content alone. Speakers…, The residual a block must clear right now to count as a voice., Consecutive positive blocks before an interruption is believed., 1.0 = fully explained by our own output, 0.0 = nothing to do with it. (+1 more)

### Community 18 - "send_message.py"
Cohesion: 0.17
Nodes (24): clipboard_history_action(), _push(), Maintains a session-scoped ring buffer of clipboard entries. Every time Alfred…, Add an entry, deduplicating consecutive identical values., _snapshot(), _base_dir(), _clear_and_paste(), _desktop_send() (+16 more)

### Community 19 - "action_loader.py"
Cohesion: 0.14
Nodes (13): ActionRecord, ActionRegistry, _call_handler(), discover_actions(), _opt_upper(), Path, Action discovery, validation, and dispatch — the built-in twin of…, Invoke the handler passing only the context kwargs it actually declares (or all… (+5 more)

### Community 20 - "HudCanvas"
Cohesion: 0.11
Nodes (13): QPainter, HudCanvas, No-op: gaze tracking removed (face renderer removed)., Thread-safe: hand over a schedule of (level, openness, width) frames. The…, Thread-safe entry point for the audio threads. Stores the louder of the…, Draw the Avengers: Endgame Stark Arc Reactor at (cx, cy) with outer radius r., Draw subtle background CRT coordinate grid with + crosshairs (Screenshot 2)., Futuristic Oscilloscope Waveforms spanning across the globe (Screenshot 1 & 2… (+5 more)

### Community 21 - "JarvisLive"
Cohesion: 0.11
Nodes (9): JarvisLive, Called when user clicks the CLEAR button in desktop GUI., Called when phone/dashboard sends a clear-chat directive., Chord pressed or released â€” may arrive on the hotkey thread., Called from the detector thread when the Alfred wake phrase is heard., Auto-sleep after the configured silence window (wake-word mode only)., Enable/disable wake word from the settings UI. Returns a status token:…, Manual sleep/wake button in the UI. (+1 more)

### Community 23 - "setter"
Cohesion: 0.09
Nodes (7): setter, _work(), _plugin_settings_signature(), Stable identity for deciding whether a settings form can be reused., Combined state for the two wake-word buttons. Readiness is a cheap,…, Thread-safe UI slot: wipe chat display., Wipe chat log and trigger any registered callback (e.g. backend/mobile sync).

### Community 24 - "AnalysisResult"
Cohesion: 0.17
Nodes (7): AnalysisResult, Result returned by a screen analyzer., _jpeg_frame(), Focused tests for the reusable continuous screen monitoring backend., TestScreenMonitorController, capture(), _wait_until()

### Community 25 - "plugin_loader.py"
Cohesion: 0.11
Nodes (21): copy, _call_run(), discover_plugins(), _load_error(), _opt_upper(), PluginRecord, PluginRegistry, Exception (+13 more)

### Community 26 - "_tlog"
Cohesion: 0.12
Nodes (12): broadcast_progress(), _deliver_news(), runner(), Announce background completion ensuring ALFRED does not talk over active speech., Execute a single background job, streaming [control] [background XX%] progress., Worker loop consuming background jobs from background_task_queue., Format terminal log report without emojis using red bracketed tags, and…, Fetch startup context concurrently and deliver one uninterrupted brief. (+4 more)

### Community 27 - "computer_control.py"
Cohesion: 0.15
Nodes (29): _base_dir(), _clear_field(), _click(), _clipboard_get(), _clipboard_paste(), computer_control(), _drag(), _focus_window() (+21 more)

### Community 28 - "local_pipeline.py"
Cohesion: 0.15
Nodes (26): call_llm(), call_llm_stream(), _do_stream(), call_llm_text(), _chat_endpoint(), check_model_available(), ensure_ollama_running(), get_base_dir() (+18 more)

### Community 29 - "gmail_manager.py"
Cohesion: 0.09
Nodes (26): _get_gmail_brief(), Fetch unread emails summary via gmail_manager., _clean_header_str(), _extract_body_snippet(), fetch_unread_emails(), gmail_manager(), _load_gmail_creds(), Any (+18 more)

### Community 30 - "SpotifyClient"
Cohesion: 0.14
Nodes (12): High-performance Spotify client with connection pooling, token caching, device…, Loads Spotify credentials from config/api_keys.json or environment variables., Returns a valid access token, refreshing if needed., Playback endpoints require a user OAuth token, not client credentials., Controls playback: pause, resume, skip_next, skip_previous. Uses Spotify's Web…, Adds a track to the playback queue., Sets Spotify volume percentage (0-100)., Returns available Spotify devices with 5-minute TTL caching. (+4 more)

### Community 31 - "TronScoreBackgroundPlayer"
Cohesion: 0.08
Nodes (7): QObject, Background music audio engine. Plays background score continuously on loop…, Set base normal volume (0.0 to 1.0). Speech ducking scales to 50% of base., Duck to 50% of base volume when speaking, restore to base volume when…, Called when Spotify plays a track. Pauses Tron background music, sets Spotify…, Specifically pause the local TRON audio core player regardless of mode., TronScoreBackgroundPlayer

### Community 32 - "_BrowserSession"
Cohesion: 0.05
Nodes (23): browser_control(), _BrowserSession, _detect_default_browser(), _find_exe_windows(), _find_opera_windows(), _firefox_profile_dir(), _log(), _normalize_url() (+15 more)

### Community 33 - "tts.py"
Cohesion: 0.09
Nodes (21): Local Text-to-Speech wrappers for MARK XL. Provides unified interface for…, _compress_silence(), create_tts_player(), EdgeTTSEngine, ElevenLabsTTSEngine, _import_kokoro_pipeline(), KokoroTTSEngine, _synth() (+13 more)

### Community 34 - ".test_error_isolation_in_concurrent_tasks"
Cohesion: 0.29
Nodes (5): Verify that an exception in one concurrent task does not break or cancel…, Verify that a batch of tasks run with a concurrency limit of 5 scales sub-…, TestConcurrencyLimiter, execute_task(), safe_run()

### Community 35 - ".__init__"
Cohesion: 0.17
Nodes (7): _Popen, Exception, Session-scoped task: when a voluntary reconnect is requested, raise a signal…, Turn hold-to-talk on or off. Returns the scope actually achieved., Raised inside the session TaskGroup to force a clean, voluntary reconnect (e.g.…, _ReconnectSignal, _OrigPopen

### Community 36 - "audio_devices.py"
Cohesion: 0.11
Nodes (21): configure(), _display_name(), _is_pseudo(), list_devices(), prefetch(), _work(), _query(), _collect() (+13 more)

### Community 37 - "GraphManager"
Cohesion: 0.11
Nodes (14): GraphManager, Any, Path, Save the graph data to the JSON file atomically., Add an entity node to the graph. Returns True if successful., Add a relationship (edge) between two nodes. Returns True if successful., Apply exponential decay to all temporary nodes. Returns the number of nodes…, Query the knowledge graph for a concept and return connected subgraph up to… (+6 more)

### Community 38 - "DashboardServer"
Cohesion: 0.19
Nodes (3): DashboardServer, Second HTTPS server on PORT+1 sharing the same app and in-memory state. Chrome…, URL for manual browser entry. When HTTPS active, points to alias port (also…

### Community 39 - "CentralizedCache"
Cohesion: 0.06
Nodes (22): CentralizedCache, _canonicalize(), decorator(), wrapper(), Any, Stores value in cache with TTL. Fails open gracefully if storage fails., Deletes a key from cache. Fails open gracefully., Invalidates all keys starting with prefix. Useful for mutation hooks. (+14 more)

### Community 41 - "._apply_name_update"
Cohesion: 0.20
Nodes (8): apply_ui_accent(), current_palette(), Applies DOSSIER CRT [A-34] (#8e9bff), VECTOR CRT [WAKU] (#a8ff3e), or BATMAN…, A snapshot of the accent-linked colours currently on class C., LIVE full theme change. Replaces the old palette colours with the new ones in…, Live preview — paints the whole interface the new colour (does NOT write to…, Update all name/theme-dependent UI elements and persist to config., retheme_all_widgets()

### Community 42 - "MinimizedHudOverlay"
Cohesion: 0.07
Nodes (10): QFont, QPointF, QRectF, _LogSource, QObject, TestMinimizedHudOverlay, HueWheel, MinimizedHudOverlay (+2 more)

### Community 43 - "mono_font"
Cohesion: 0.05
Nodes (21): BiometricFingerprintWidget, _CameraPreview, ClipboardPanel, CRTReconWidget, ImagePopupOverlay, _fl(), MetricBar, mono_font() (+13 more)

### Community 45 - "VisemeStream"
Cohesion: 0.13
Nodes (13): collections, coverage(), Text → mouth shape, fused with the audio the avatar is actually speaking. Why…, Reduce any character to a bare Latin letter, or "" if it has none. This is what…, Fraction of the letters in `text` we can reduce to a Latin sound., Split a line of speech into (viseme, duration-weight) pairs. Returns [] for…, Fuses the transcript's shape sequence onto the audio's timing. Thread note:…, Blend audio frames [(level, openness, width)] with the text queue. (+5 more)

### Community 46 - "screen_processor.py"
Cohesion: 0.05
Nodes (49): _base_dir(), _capture_camera(), capture_screen(), _capture_screen(), _compress(), _cv2_backend(), _detect_camera_index(), format_visual_payload() (+41 more)

### Community 47 - "protocol_engine.py"
Cohesion: 0.14
Nodes (28): create_protocol(), _do_save(), execute_protocol(), _execute_tool(), get_action_registry(), interpolate_variables(), _is_failure(), list_protocols() (+20 more)

### Community 48 - "main.py"
Cohesion: 0.09
Nodes (20): gc, google, google_genai, LiveConnectConfig, The optional knobs, kept apart so one bad field can be dropped wholesale. Every…, get_brief_enabled(), get_media_resolution(), get_proactive_audio_enabled() (+12 more)

### Community 49 - "spotify_control.py"
Cohesion: 0.12
Nodes (19): authorize_user(), _get_base_dir(), get_spotify_client(), manage_queue(), Path, Spotify AI Agent & Playback Control for ALFRED. Provides Spotify Web API…, Main handler for the spotify_control action., Sends a native Windows WM_APPCOMMAND message to explicitly Pause, Play, or Stop. (+11 more)

### Community 50 - "wake_word.py"
Cohesion: 0.18
Nodes (11): install_and_download(), is_installed(), is_ready(), _prediction_score(), Local wake-word detection for ALFRED ("Hey Alfred"). Design goals: • ZERO cost…, Return the Alfred score while tolerating backend-specific key suffixes., True if the openwakeword package is importable (no model check)., True if openwakeword is installed AND its model files are present on disk. This… (+3 more)

### Community 51 - "CustomizeOverlay"
Cohesion: 0.12
Nodes (13): CustomizeOverlay, _lbl(), format_icon_display_name(), get_available_app_icons(), Load and scale an icon once per file version and target size., Floating glassmorphic overlay for configuring Assistant Persona, Commander…, Refresh reusable controls from persisted settings before showing., Highlight the selected voice pill; dim the rest. (+5 more)

### Community 52 - "computer_settings"
Cohesion: 0.12
Nodes (16): brightness_get(), brightness_set(), computer_settings(), dark_mode(), paste(), press_key(), Current brightness 0-100, or None where it cannot be read., Set brightness to an absolute percentage. Only used to restore a value captured… (+8 more)

### Community 53 - "desktop.py"
Cohesion: 0.23
Nodes (17): _ask_gemini_for_desktop_action(), _build_sandbox(), clean_desktop(), desktop_control(), _execute_generated_code(), _get_api_key(), _get_base_dir(), get_current_wallpaper() (+9 more)

### Community 54 - "tech_font"
Cohesion: 0.12
Nodes (9): QPushButton, QVBoxLayout, CapabilitiesOverlay, PluginManagerOverlay, PluginSettingsOverlay, Floating glassmorphic overlay displaying a categorized directory of everything…, Floating overlay — lists discovered plugins with per-plugin ON/OFF toggles., Floating overlay — renders per-plugin settings forms. Fully generic: it… (+1 more)

### Community 55 - "load_api_keys"
Cohesion: 0.14
Nodes (16): get_app_icon(), get_assistant_name(), get_gemini_key(), get_input_device(), get_llm_provider(), get_openrouter_key(), get_openrouter_model(), get_output_device() (+8 more)

### Community 56 - "._build_app"
Cohesion: 0.15
Nodes (14): action_ep(), audio_ws(), _auth(), clear_chat_ep(), command(), download_file(), list_files(), phone_audio_ws() (+6 more)

### Community 57 - "TestProtocolEngine"
Cohesion: 0.11
Nodes (8): Verify that a tool failure halts subsequent steps immediately., Verify voice trigger word resolution (e.g. 'FCC CLAUDE')., Verify dynamic workflow creation with confirmation banner., Verify protocol_engine TOOL action handler dispatching., Verification Requirement: Define test_protocol in protocols.yaml that opens…, Verify variable interpolation into strings, lists, and dicts., Verify that if any step is blocked by path restrictions, the engine aborts…, TestProtocolEngine

### Community 58 - "PushToTalk"
Cohesion: 0.08
Nodes (10): chord_label(), PushToTalk, Begin watching. Returns the scope actually achieved., Feed a press/release from a Qt shortcut (non-Windows, or no hook)., Human-readable name of the chord, for the UI and the logs., Calls `on_change(held: bool)` whenever the chord is pressed or released. Start…, global' once a system-wide hook is running, else 'window'., _FakeButton (+2 more)

### Community 59 - "find_element"
Cohesion: 0.14
Nodes (12): find_element(), is_icon_query(), Determine if target query is specifically targeting an icon/non-text element., Main entry point for local hybrid UI element grounding. 1. Executes RapidOCR on…, Action handler called by ALFRED action dispatcher., screen_find(), 10. Full Desktop Control & Operating System Automation, Verification Requirement: Call find_element('Save') on a text editor window.… (+4 more)

### Community 60 - "RemoteKeyOverlay"
Cohesion: 0.16
Nodes (6): Called from Qt main thread when user presses Remote Control., 1. What's New: Recent Enhancements, Bug Fixes & Stability Updates, Floating overlay — QR code for instant phone pairing + manual key fallback., Call from any thread when a phone successfully connects., RemoteKeyOverlay, _lbl()

### Community 61 - "json"
Cohesion: 0.15
Nodes (14): json, math, memory/graph_manager.py — Dynamic Knowledge Graph Manager for Graphify Manages…, networkx, _load_events(), Calendar Sync Plugin for ALFRED Mark-LIV. Tracks agenda, meetings,…, Execute calendar action., run() (+6 more)

### Community 62 - "time"
Cohesion: 0.18
Nodes (9): Tactical Audio Core Control Action for ALFRED. Controls the tactical HUD's…, asyncio, core/cache.py — Centralized Caching Layer for ALFRED Mark-II. Provides high-…, Push-to-talk — hold a key, speak, release. Why this exists ---------------…, functools, StartupBriefTests, threading, time (+1 more)

### Community 63 - "LocalSTTManager"
Cohesion: 0.05
Nodes (25): LocalSTTManager, audio_callback_wrapper(), Process audio bytes for transcription based on engine type., Cancel any pending debounce timer, thread-safe., Reset the FINISH_MS countdown from zero., Timer callback: commit the accumulated sentence to the queue., Immediately commit whatever is in the buffer (+ optional extra word)., Process audio using Vosk streaming STT. Final results are held for FINISH_MS… (+17 more)

### Community 65 - "qcol"
Cohesion: 0.24
Nodes (5): QColor, _DropCanvas, _file_category(), _fmt_size(), qcol()

### Community 66 - "LocalTTSManager"
Cohesion: 0.15
Nodes (8): LocalTTSManager, Flush any remaining text in buffer., Main loop for processing text queue and speaking., Manages local text-to-speech synthesis with streaming capabilities., Start the TTS processing thread., Stop the TTS processing thread., Add text to be spoken (non-blocking)., Add a sentence to be spoken, with sentence boundary detection.

### Community 67 - "ALFRED MARK-VI (Wayne Protocol Edition)"
Cohesion: 0.13
Nodes (14): 11. High-Performance Memory & Conversational Briefing Customizer, 12. Real-Time Insignia & Chassis Hot-Swapper, 13. Protocol Engine & Multi-Step Macro Playbooks (`config/protocols.yaml`), 14. Local Hybrid Visual Grounding (RapidOCR + ONNX + Gemini Fallback), 15. Process-Level Audio Ducking & Background Concurrency, 17. System Architecture & File Structure, 19. Configuration Reference (`config/api_keys.json`), 20. Knowledge Graph (`graphify`) (+6 more)

### Community 68 - "_SysMetrics"
Cohesion: 0.13
Nodes (7): Thread-safe speech channel for plugins: lets a plugin ask JARVIS to say…, Thread-safe: ask the run loop to tear down and rebuild the Live session. Called…, Voice picker applied. The voice is baked into the session at connect time, so a…, Microphone or speaker changed. Both streams are opened inside the session…, _nvml_gpu_windows(), Return NVIDIA GPU utilisation % using nvml.dll directly — zero subprocess., _SysMetrics

### Community 69 - "memory_manager.py"
Cohesion: 0.11
Nodes (27): Update Daily Briefing Preferences Action for ALFRED Mark-LIV. Permanently…, _all_entries(), all_entries_for_ui(), _empty_memory(), _entry_value(), forget(), get_base_dir(), load_memory() (+19 more)

### Community 70 - "unduck_media_apps"
Cohesion: 0.24
Nodes (7): Restore ducked media applications to their exact original volume levels. :param…, unduck_media_apps(), _pcm_level(), _pcm_visemes(), Stop JARVIS mid-speech: drain queued audio and open mic immediately., Map a block of int16 PCM samples to a 0.0â€“1.0 loudness level for the HUD…, Slice a PCM block into (level, openness, width) frames, one per 20 ms. Returns…

### Community 71 - "window_manager.py"
Cohesion: 0.21
Nodes (14): _find_hwnd_by_title(), _cb(), _focused_hwnd(), _get_screen(), _get_title(), _list_windows(), _move_resize(), Voice-driven window management for Windows. Snap, resize, fullscreen, tile,… (+6 more)

### Community 72 - "WakeWordDetector"
Cohesion: 0.17
Nodes (5): Runs the wake model in a dedicated thread. The mic thread calls feed() with raw…, Load the model and spawn the inference thread. Returns True on success. Safe to…, Called from the mic callback (real-time thread). Must stay cheap and never…, WakeWordDetector, Load the detector once (model loads on first start). Idempotent.

### Community 73 - "TestBackgroundWorkerPool"
Cohesion: 0.12
Nodes (7): Verify that calling interrupt() sets halt event, immediately stops active…, Verify that _safe_background_announce waits until ALFRED finishes speaking…, Verify DashboardServer tracks background tasks and exposes them via endpoint., Verify queue_background_task is registered in TOOL_DECLARATIONS., Verify that queue_background_task returns immediately (sub-millisecond), and…, Dispatch a mock task and verify voice PTT interaction continues with sub-second…, TestBackgroundWorkerPool

### Community 74 - "intel_notes.py"
Cohesion: 0.31
Nodes (8): _auto_detect_type(), _config_dir(), intel_notes(), _load_notes(), Path, actions/intel_notes.py — Dedicated Intel & Notes Terminal Action. Provides a…, Action handler called by Gemini / action_loader., _save_notes()

### Community 75 - "TestHudReactivity"
Cohesion: 0.14
Nodes (3): TestHudReactivity, Acoustic control with a cheap listening-level outline., ReactiveMicButton

### Community 76 - "._build_jarvis_icon"
Cohesion: 0.22
Nodes (4): Render an ALFRED tactical icon at 4× resolution and downsample for crisp…, Create a Windows .lnk shortcut WITHOUT launching PowerShell or cmd. Tries…, Resolve the user's REAL desktop directory instead of assuming ~/Desktop, which…, Create a desktop shortcut on Windows / macOS / Linux. Never opens a terminal,…

### Community 77 - "._log"
Cohesion: 0.22
Nodes (6): stream_callback(), Log message via callback or print., Start the local pipeline., Stop the local pipeline., Main processing loop: STT → LLM → TTS., Process a complete utterance: transcribe → generate response → synthesize.

### Community 78 - "screen_monitor.py"
Cohesion: 0.21
Nodes (11): _default_analyzer(), _fingerprint_key(), Reusable, in-memory continuous screen monitoring. The controller owns only the…, Return normalized mean absolute difference in the range 0.0 to 1.0., Detect context, visual-frame, and explicit completion changes., One captured frame and its metadata, retained only until the next frame., Return a tiny grayscale frame representation without writing image data., ScreenObservation (+3 more)

### Community 79 - "LogWidget"
Cohesion: 0.25
Nodes (3): QTextEdit, LogWidget, Cancel any in-flight typing animation, drain the queue, and clear the display.

### Community 80 - "ProactiveEngine"
Cohesion: 0.11
Nodes (13): ProactiveEngine, ProactiveEngine 2.0 — context-aware, time-aware, non-repetitive background…, Decides when ALFRED should speak unprompted and builds a context-rich prompt.…, Build a context snapshot for Gemini. Rotates through three focus areas so…, _describe_limits(), _describe_tools(), _load_system_prompt(), One line per capability, straight from the live tool declarations. Derived… (+5 more)

### Community 81 - "ScreenMonitorController"
Cohesion: 0.16
Nodes (8): Exception, Poll screen capture in a daemon thread and retain only the latest frame., Start monitoring immediately; return false if a run is already active., Request a clean stop; optionally wait for the polling thread to exit., Return an immutable snapshot without copying or persisting image bytes., Thread-safe snapshot of controller state., ScreenMonitorController, ScreenMonitorStatus

### Community 82 - "MemoryOverlay"
Cohesion: 0.08
Nodes (12): AudioDeviceOverlay, ConfirmBanner, _HudOverlay, MemoryOverlay, Base for the floating panels placed by hand over the HUD. They are children of…, The gate in front of an action that cannot be taken back. The old confirmation…, Choose which microphone ALFRED listens to and which speakers it uses. Both…, Everything ALFRED has stored about you, and when it learned it. Memory used to… (+4 more)

### Community 83 - "SetupOverlay"
Cohesion: 0.11
Nodes (11): Open the API key and neural backend configuration overlay from settings., Update probe widgets on the Qt thread via a queued signal., Read api_keys.json config dict. Returns {} on any error., Build expensive reusable settings widgets after first paint., _read_full_config(), SetupOverlay, _lbl(), _check() (+3 more)

### Community 84 - "confirm.py"
Cohesion: 0.21
Nodes (12): bind(), _log(), _Pending, pending_title(), core/confirm.py — a confirmation the model cannot forge. THE PROBLEM WITH THE…, Called by the UI when the user presses CONFIRM or CANCEL. Runs the stored…, when nothing is waiting. Lets an action avoid stacking two banners., Wire this module to the HUD. Called once from main.py at startup. (+4 more)

### Community 85 - "control_playback"
Cohesion: 0.18
Nodes (5): control_playback(), _base_dir(), Path, Restores Tron legacy score as the default active audio., Specifically resume/play the local TRON audio core player.

### Community 86 - "ImagePopupOverlay"
Cohesion: 0.15
Nodes (9): action(), ImagePopupOverlay, QWidget, Handle mouse move for window dragging., Handle mouse release for window dragging., Show the popup centered over the parent widget., Show an image popup overlay., Popup overlay to display an image with a dismiss button. (+1 more)

### Community 87 - "is_heavenly_restricted"
Cohesion: 0.20
Nodes (14): _is_heavenly_restricted_params(), check_action_params(), check_path_access(), get_allowed_c_roots(), is_heavenly_restricted(), is_safe_path(), Any, Path (+6 more)

### Community 88 - "._aes_key"
Cohesion: 0.43
Nodes (3): auto_login(), device_login_ep(), login()

### Community 89 - "_update_config"
Cohesion: 0.18
Nodes (12): _config_signature_unlocked(), ensure_config_dir(), _plugin_settings_state(), Merge `values` into a namespace's stored config (read-modify-write, like every…, _read_config_unlocked(), save_api_keys(), update(), save_plugin_config() (+4 more)

### Community 90 - "config_manager.py"
Cohesion: 0.10
Nodes (26): get_base_dir(), get_hud_style(), invalidate_config_cache(), _patch_config(), Path, Persist assistant name and user name to config., Persist the chosen Live voice. Unknown names collapse to the default so a bad…, The speech-reactive globe is the only supported HUD. (+18 more)

### Community 91 - "update_app_icon.py"
Cohesion: 0.50
Nodes (3): Update App Icon Action for ALFRED Mark-LIV. Switches the application window,…, Updates the main application icon and taskbar badge in realtime., update_app_icon()

### Community 92 - "_detect_action"
Cohesion: 0.40
Nodes (5): _detect_action(), _normalise(), Resolve a free-text description to an action name, locally. Returns {"action":…, What to tell the model when nothing matched. Names real actions so its retry…, _suggest()

### Community 93 - "daily_brief.py"
Cohesion: 0.10
Nodes (22): Daily Brief Action for ALFRED Mark-LIV. Provides the ultimate morning and daily…, _active_connections(), _local_ip(), network_tools_action(), _ping(), _public_ip(), Network diagnostics available by voice: - speed_test : download / upload / ping…, Try speedtest-cli library first, then subprocess. (+14 more)

### Community 94 - "open_app"
Cohesion: 0.29
Nodes (6): _normalize(), open_app(), /deep-work Workflow, Objective, Steps, 4. Security, Privacy & Defensive Architecture

### Community 95 - "get_push_to_talk_enabled"
Cohesion: 0.33
Nodes (4): get_push_to_talk_enabled(), Hold-a-key-to-speak. When on, the mic is closed unless the chord is held., save_push_to_talk_enabled(), Repaint the push-to-talk row from the saved setting.

### Community 96 - "audio_ducker.py"
Cohesion: 0.18
Nodes (13): _duck_linux(), duck_media_apps(), _worker(), _duck_windows(), Process-level Audio Ducking for ALFRED. Automatically ducks background media…, Execute unducking on Windows via pycaw, restoring exact prior volume levels., Execute ducking on Linux via pulsectl., Execute unducking on Linux via pulsectl. (+5 more)

### Community 97 - "._dispatch_tool"
Cohesion: 0.15
Nodes (7): _is_heavenly_restricted(), _do_shutdown(), Fast callback used by the Sentry button on the Qt thread., Queue a background task and return task metadata immediately., Check if any argument references the restricted Personal-Assistant directory., Summarise the current session in 1-2 sentences and save to long_term.json., Direct action execution from mobile dashboard buttons.

### Community 98 - "LocalLLMManager"
Cohesion: 0.13
Nodes (11): LocalLLMManager, Handle tool calls by executing them and getting final response., Manages local LLM interactions., Set system prompt and available tools., Add message to conversation history., Clear conversation history., Generate response from local LLM., create_local_stt_engine() (+3 more)

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

### Community 107 - "test_cache.py"
Cohesion: 0.22
Nodes (10): _get_live_weather(), Fetch live weather conditions without opening an external browser., Permanently saves daily briefing preferences into long-term memory., update_daily_briefing(), get_cache(), Returns the centralized cache client singleton., patch, tests/test_cache.py — Comprehensive Test Suite for CentralizedCache. Tests: -… (+2 more)

### Community 111 - "Q: Implement the ALFRED MK-IV translucent minimised HUD overlay plan from the pasted text."
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Implement the ALFRED MK-IV translucent minimised HUD overlay plan from the pasted text., Source Nodes

### Community 116 - "Q: Remove Classic HUD mode from ALFRED MK-IV"
Cohesion: 0.50
Nodes (3): Answer, Q: Remove Classic HUD mode from ALFRED MK-IV, Source Nodes

### Community 119 - "_get_user_protocols_path"
Cohesion: 0.18
Nodes (13): _ensure_user_protocols_dir(), _get_default_protocols_path(), get_protocols_file(), _get_user_name(), _get_user_protocols_dir(), _get_user_protocols_path(), Path, Get the configured user name from api_keys.json. (+5 more)

### Community 124 - "TestAudioDucker"
Cohesion: 0.29
Nodes (4): patch, Verify that duck_media_apps lowers target media processes by 70% (0.3 factor),…, Verify Linux pulsectl ducking fallback logic., TestAudioDucker

### Community 127 - "re"
Cohesion: 0.21
Nodes (11): quick_translate_action(), Translate text to a target language using the Gemini model already powering…, Return the full language name from a code or common alias., Use the project's LLM client (Gemini) to perform the translation., Fallback: use deep-translator if installed., _resolve_language(), _translate_via_googletrans(), _translate_via_llm() (+3 more)

### Community 132 - "echo.py"
Cohesion: 0.17
Nodes (7): is_ducked(), Return whether media ducking is currently active., Telling the user's voice apart from our own coming back through the speakers.…, Local Speech-to-Text wrappers for MARK XL. Provides unified interface for…, Speech-to-Text engines for MARK XL. Whisper – offline transcription via faster-…, numpy, queue

### Community 133 - "daily_brief"
Cohesion: 0.13
Nodes (16): daily_brief(), _get_preferred_news(), _get_greeting(), _get_reminders_brief(), _get_system_vitals(), Check scheduled reminders in ~/.alfred/reminders or ~/.jarvis/reminders., Inspect core CPU, RAM, and Battery vitals., Executes the daily briefing and delivers spoken synthesis. (+8 more)

### Community 134 - "datetime"
Cohesion: 0.41
Nodes (11): _base_dir(), _get_os(), Path, reminder(), _sanitise(), _schedule_linux(), _schedule_mac(), _schedule_windows() (+3 more)

### Community 135 - "background_monitor.py"
Cohesion: 0.26
Nodes (14): add_monitor(), check_all(), _fetch(), _is_blocked(), list_monitors(), _load(), BackgroundMonitor — user-configured topic watching. Checks DDG news once per…, Run all pending topic checks (once per day per topic). Returns a list of… (+6 more)

### Community 137 - "Q: Why did completed screen monitoring issue duplicate stop calls?"
Cohesion: 0.50
Nodes (3): Answer, Q: Why did completed screen monitoring issue duplicate stop calls?, Source Nodes

### Community 138 - "Q: Why does opening Alfred show the old UI with no switch to the speech-reactive HUD?"
Cohesion: 0.50
Nodes (3): Answer, Q: Why does opening Alfred show the old UI with no switch to the speech-reactive HUD?, Source Nodes

### Community 139 - "ui.py"
Cohesion: 0.17
Nodes (18): Action to show an image popup overlay., os, pathlib, pyqt6_qtcore, pyqt6_qtgui, pyqt6_qtmultimedia, pyqt6_qtwidgets, sys (+10 more)

### Community 140 - "server.py"
Cohesion: 0.11
Nodes (16): base64, _derive_key(), _ensure_certs(), _local_ip(), _make_uploads_dir(), Path, dashboard/server.py — ALFRED Local HTTP Dashboard Plain HTTP on port 8000 (no…, Return the best LAN-facing IPv4 address, no internet required. (+8 more)

### Community 141 - "Q: Read uiperformance.md and continousmonitoring.md and perform the tasks in the most efficient manner"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Read uiperformance.md and continousmonitoring.md and perform the tasks in the most efficient manner, Source Nodes

### Community 142 - "LocalPipelineCoordinator"
Cohesion: 0.20
Nodes (7): create_local_pipeline(), LocalPipelineCoordinator, Coordinates STT → LLM → TTS flow., Set callbacks for UI updates., Callback for audio from STT manager., Handle end of speech detection., Create and configure a local pipeline coordinator.

### Community 143 - "._receive_audio"
Cohesion: 0.20
Nodes (6): FunctionResponse, _clean_transcript(), _is_repeat_chunk(), _run_tool_bounded(), Send a captured frame immediately after its tool response. The frame is already…, True if this transcript chunk has already been seen this turn. Guards against…

### Community 145 - "Q: Implement the ALFRED MK-IV speech-reactive graphical UI plan efficiently"
Cohesion: 0.50
Nodes (3): Answer, Q: Implement the ALFRED MK-IV speech-reactive graphical UI plan efficiently, Source Nodes

### Community 146 - "ScreenMonitorEvent"
Cohesion: 0.21
Nodes (4): Event delivered to meaningful-state and completion callbacks., ScreenMonitorEvent, Forward selected changed frames from the monitor thread to the AI loop., _FakeSession

### Community 147 - ".play"
Cohesion: 0.32
Nodes (6): get_devices(), Any, Search Spotify for tracks, albums, artists, or playlists., Start playback through Spotify Connect without opening a local app., spotify_search(), start_playback()

### Community 148 - "18. Quick Start & Installation"
Cohesion: 0.67
Nodes (3): 18. Quick Start & Installation, 1. Prerequisites, 2. Setup & Execution

### Community 149 - "Ã°Å¸Å½â„¢Ã¯Â¸Â 5. Master Tactical Voice Command Codex & Operational Handbook"
Cohesion: 0.20
Nodes (10): Ã¢Å¡Â¡ 3. Compound Protocols & Workflow Macros, Ã°Å¸â€ºÂ¡Ã¯Â¸Â 9. Chassis Insignia & Assistant Customization, Ã°Å¸Â§Â  4. Memory, History & Universal Reversibility, Ã°Å¸â€˜ÂÃ¯Â¸Â 1. Desktop Automation, Screen & Multimodal Vision, Ã¢Å¡â„¢Ã¯Â¸Â 2. Operating System, Hardware Settings & Applications, Ã°Å¸â€œÂ° 5. Intelligence, Briefings, News & Weather, Ã°Å¸â€œÂ± 6. Quantum Mobile Remote & Web Telemetry Uplink, Ã°Å¸Å½Â§ 7. Spotify AI Agent & Music Streaming (+2 more)

### Community 150 - "setup.py"
Cohesion: 0.36
Nodes (7): _check_assets(), _check_python(), main(), MARK LIV — one-time setup. Installs the Python dependencies for THIS operating…, Fail immediately and clearly rather than deep inside a pip resolver. A wrong…, The avatar's face is a shipped file; a truncated clone should say so., _run()

### Community 151 - "TTSPlayer"
Cohesion: 0.29
Nodes (3): Wraps any *Engine. Exposes a blocking speak() method meant to be called from a…, Synthesise and play text. BLOCKING – call from a dedicated thread., TTSPlayer

### Community 152 - "Q: change wake key to hey Alfred no t jarvis"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: change wake key to hey Alfred no t jarvis, Source Nodes

### Community 153 - "_gemini_grounding"
Cohesion: 0.22
Nodes (9): _capture_screen_image(), _gemini_grounding(), _get_api_key(), _onnx_element_grounding(), Capture current screen into a PIL Image., Run local ONNX element detector (OmniParser-v2 / Florence-2). Returns:…, Fallback visual grounding via Gemini Live / Flash API., Retrieve Gemini API key from api_keys.json or environment. (+1 more)

### Community 154 - "_VolumeSliderPopup"
Cohesion: 0.33
Nodes (3): QFrame, Sleek tactical cyber popup for adjusting master background music volume.…, _VolumeSliderPopup

### Community 156 - "._listen_audio"
Cohesion: 0.40
Nodes (3): callback(), _open_mic(), True while the speakers may still be finishing our last sentence.

### Community 157 - "._set_state"
Cohesion: 0.22
Nodes (4): Set UI state via callback., Handle wake word detection., Enable or disable wake word detection., Put the assistant to sleep.

### Community 159 - "._apply_ptt_shortcut"
Cohesion: 0.29
Nodes (5): qt_sequence(), The same chord as a QKeySequence string., _press(), Bind the chord inside the window when no global hook is available. On macOS and…, Report a windowed press/release to whoever owns the microphone.

### Community 160 - ".__init__"
Cohesion: 0.40
Nodes (4): AnalysisCallback, CaptureCallback, EventCallback, StoppedCallback

### Community 161 - "weather_report.py"
Cohesion: 0.50
Nodes (4): _log(), weather_action(), urllib_parse, webbrowser

### Community 162 - "news_brief.py"
Cohesion: 0.43
Nodes (6): _cache_get(), _cache_put(), _fetch_headlines(), news_brief_action(), On-demand news headlines fetched via the existing web_search infrastructure and…, Use the existing web_search action to pull headlines.

### Community 163 - "process_manager.py"
Cohesion: 0.52
Nodes (6): _find_procs_by_name(), _get_psutil(), process_manager_action(), Voice-driven process management using psutil. Kill a named process, list…, Return all processes whose name or cmdline contains `name` (case-insensitive)., _top_procs()

### Community 164 - "._decrypt"
Cohesion: 0.50
Nodes (3): ws_ep(), _decrypt_cbc(), Decrypt base64(IV[16] ‖ ciphertext) with AES-256-CBC + PKCS7.

### Community 165 - "Q: the hud text is quite hard to see"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: the hud text is quite hard to see, Source Nodes

### Community 166 - "TestScreenMonitorIntegration"
Cohesion: 0.17
Nodes (3): _FakeController, _FakeUI, TestScreenMonitorIntegration

### Community 167 - "audio_core"
Cohesion: 0.50
Nodes (4): audio_core(), Any, Main handler for the Audio Core control action., 7. Dual-Mode Tactical Audio Matrix & Background Sound Engine

### Community 168 - "band_energies"
Cohesion: 0.29
Nodes (5): band_energies(), ndarray, Record a slice of what is being played, for later comparison., True if this microphone block is a different voice, not our echo., Raw energy per speech band — the fingerprint we compare. Left unnormalised on…

### Community 169 - "get_plugin_config"
Cohesion: 0.50
Nodes (4): get_plugin_config(), get_plugin_setting(), All stored values for a namespace (empty dict if none set yet)., A single value from a namespace, or `default` if unset.

### Community 170 - "Step 1: Install & Set Up Your Preferred Local LLM Server"
Cohesion: 0.50
Nodes (4): Option A: Ollama (Recommended Ã¢â‚¬â€ Simplest Setup), Option B: LM Studio (Recommended for GUI Users), Option C: vLLM or llama.cpp (High-Throughput / Linux Servers), Step 1: Install & Set Up Your Preferred Local LLM Server

### Community 171 - "TestMemoryTrimBenchmark"
Cohesion: 0.29
Nodes (4): Measures execution time for 50,000 mock records. Under the old O(N^2)…, Preserves all items when memory is already below limit., Handles empty memory structure gracefully., TestMemoryTrimBenchmark

### Community 174 - "Q: Fix Spotify playback, Audio Core now-playing display, inverted startup play button, and avoid opening the Spotify desktop app."
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Fix Spotify playback, Audio Core now-playing display, inverted startup play button, and avoid opening the Spotify desktop app., Source Nodes

### Community 175 - "Ã°Å¸Å½Â­ 3. Example & Fun Tactical Commands ("Wayne Protocol" in Action)"
Cohesion: 0.40
Nodes (5): Ã°Å¸â€ºÂ¡Ã¯Â¸Â Insignia & Batcave Customization, Ã°Å¸â€˜ÂÃ¯Â¸Â Tactical Vision & Screen Grounding, Ã°Å¸Å½Â­ 3. Example & Fun Tactical Commands ("Wayne Protocol" in Action), Ã°Å¸Å½Â© Distinguished Butler & Persona Banter, Ã°Å¸Å½Âµ Ambience, Scores & Entertainment

### Community 180 - "22. Mark VI Enhancements"
Cohesion: 0.50
Nodes (4): 22. Mark VI Enhancements, Network Resilience Fix (`main.py`), New Actions (auto-discovered â€” no registration required), Prompt Engine Overhaul (`core/prompt.txt`)

## Knowledge Gaps
- **83 isolated node(s):** `Purpose`, `Rules`, `Purpose`, `Rules`, `Persona & Demeanor` (+78 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1263 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **38 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Work-memory lessons

**Preferred sources** — corroborated by past sessions; start here.
- `MinimizedHudOverlay` (2× useful, score=1.999551435) _(code changed — re-verify)_

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `JarvisUI` connect `JarvisUI` to `._apply_ptt_shortcut`, `.set_spotify_playback_state`, `.__init__`, `._apply_name_update`, `ui.py`, `mono_font`, `main.py`, `MemoryOverlay`, `JarvisLive`, `.muted`, `setter`, `RemoteKeyOverlay`, `get_push_to_talk_enabled`?**
  _High betweenness centrality (0.074) - this node is a cross-community bridge._
- **Why does `JarvisLive` connect `JarvisLive` to `system_monitor.py`, `JarvisUI`, `ui.py`, `.run`, `._receive_audio`, `EchoGuard`, `ScreenMonitorEvent`, `_tlog`, `._listen_audio`, `.__init__`, `DashboardServer`, `TestScreenMonitorIntegration`, `VisemeStream`, `main.py`, `PushToTalk`, `RemoteKeyOverlay`, `time`, `_SysMetrics`, `unduck_media_apps`, `WakeWordDetector`, `TestBackgroundWorkerPool`, `ProactiveEngine`, `ScreenMonitorController`, `._dispatch_tool`?**
  _High betweenness centrality (0.071) - this node is a cross-community bridge._
- **Why does `MainWindow` connect `MainWindow` to `qcol`, `TestScreenMonitorIntegration`, `._apply_name_update`, `mono_font`, `ui.py`, `._build_jarvis_icon`, `MemoryOverlay`, `SetupOverlay`, `CustomizeOverlay`, `tech_font`, `setter`, `PushToTalk`, `RemoteKeyOverlay`, `get_push_to_talk_enabled`, `._apply_ptt_shortcut`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._
- **Are the 13 inferred relationships involving `JarvisLive` (e.g. with `ProactiveEngine` and `ScreenMonitorController`) actually correct?**
  _`JarvisLive` has 13 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Purpose`, `Rules`, `Purpose` to the rest of the system?**
  _83 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `game_updater.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0633964429145152 - nodes in this community are weakly interconnected._
- **Should `file_controller.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06690140845070422 - nodes in this community are weakly interconnected._