# Graph Report - Alfred-Mark-IV  (2026-09-28)

## Corpus Check
- 119 files · ~209,652 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 15 file(s) not represented in the graph (top: .ico 7, (none) 3, .obj 2)

## Summary
- 2897 nodes · 5636 edges · 149 communities (124 shown, 25 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 245 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `3fad0292`
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
- _index_file
- system_monitor.py
- JarvisUI
- MinimizedHudOverlay
- MainWindow
- dev_agent.py
- .run
- FileDropZone
- screen_find
- EchoGuard
- desktop.py
- is_heavenly_restricted
- HudCanvas
- JarvisLive
- TestPluginSettingsSchemaCache
- ._wake_state
- ScreenMonitorController
- get_plugin_enabled
- _tlog
- computer_control.py
- llm_client.py
- gmail_manager.py
- ._process_utterance
- TronScoreBackgroundPlayer
- _BrowserSession
- tts.py
- .test_error_isolation_in_concurrent_tasks
- .__init__
- audio_devices.py
- GraphManager
- calendar_sync.py
- CentralizedCache
- crypto-js.min.js
- ._apply_name_update
- HueWheel
- mono_font
- TacticalAudioPlayerWidget
- VisemeStream
- screen_processor.py
- protocol_engine.py
- load_api_keys
- spotify_control.py
- subprocess
- CustomizeOverlay
- computer_settings
- _patch_config
- PluginSettingsOverlay
- _HudOverlay
- DashboardServer
- screen_monitor.py
- PushToTalk
- ._build_right_panel
- tech_font
- TestBackgroundWorkerPool
- _FakeButton
- LocalSTTManager
- NotesTerminalWidget
- qcol
- main.py
- ALFRED — MARK-IV (Wayne Protocol Edition)
- _SysMetrics
- memory_manager.py
- echo.py
- ._log
- WakeWordDetector
- TestMinimizedHudOverlay
- re
- TestHudReactivity
- ._build_jarvis_icon
- LocalPipelineCoordinator
- installer.py
- LogWidget
- ._build_system_instruction
- ScreenMonitorStatus
- MemoryOverlay
- SetupOverlay
- confirm.py
- install_and_download
- ImagePopupOverlay
- band_energies
- datetime
- plugin_loader.py
- config_manager.py
- save_app_icon
- _detect_action
- sys
- focus_protocol.py
- ._apply_ptt_shortcut
- 🎙️ 5. Master Tactical Voice Command Codex & Operational Handbook
- capture_screen
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
- .clear_chat
- _RootShim
- README.md
- TestConfigCache
- TestScreenProcessorWindowContext
- daily_brief
- ._dispatch_tool
- get_active_window_info
- Q: Why did completed screen monitoring issue duplicate stop calls?
- Q: Why does opening Alfred show the old UI with no switch to the speech-reactive HUD?
- ui.py
- pathlib
- Q: Read uiperformance.md and continousmonitoring.md and perform the tasks in the most efficient manner
- Continuous Screen Monitoring Plan
- Q: Implement the ALFRED MK-IV speech-reactive graphical UI plan efficiently
- 18. Quick Start & Installation
- format_visual_payload
- Q: change wake key to hey Alfred no t jarvis
- App Performance Plan
- ._play_audio
- _base_dir
- .__init__

## God Nodes (most connected - your core abstractions)
1. `MainWindow` - 105 edges
2. `JarvisLive` - 80 edges
3. `JarvisUI` - 51 edges
4. `tech_font()` - 38 edges
5. `mono_font()` - 37 edges
6. `_BrowserSession` - 32 edges
7. `TronScoreBackgroundPlayer` - 32 edges
8. `ScreenMonitorController` - 30 edges
9. `computer_control()` - 26 edges
10. `is_heavenly_restricted()` - 26 edges

## Surprising Connections (you probably didn't know these)
- `3. Dedicated Intel & Notes Terminal (`intel_notes`)` --references--> `intel_notes()`  [INFERRED]
  .agents/rules/file_exploration.md → actions/intel_notes.py
- `Monitoring Behavior` --references--> `capture_screen()`  [INFERRED]
  continousmonitoring.md → actions/screen_processor.py
- `High-Performance Client & Anti-Feedback Architecture` --references--> `SpotifyClient`  [INFERRED]
  readme.md → actions/spotify_control.py
- `7. Dual-Mode Tactical Audio Matrix & Background Sound Engine` --references--> `audio_core()`  [INFERRED]
  readme.md → actions/audio_core.py
- `4. Security, Privacy & Defensive Architecture` --references--> `computer_control()`  [INFERRED]
  readme.md → actions/computer_control.py

## Import Cycles
- None detected.

## Communities (149 total, 25 thin omitted)

### Community 0 - "game_updater.py"
Cohesion: 0.06
Nodes (78): _build_google_flights_url(), flight_finder(), _format_spoken(), _format_text_report(), _get_base_dir(), _parse_date(), _parse_flights_with_gemini(), Path (+70 more)

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
Cohesion: 0.09
Nodes (38): _compare(), _fetch_item(), _ddg_news(), _ddg_search(), _format_ddg(), _format_news(), _gemini_available(), _gemini_headlines() (+30 more)

### Community 5 - "code_helper.py"
Cohesion: 0.08
Nodes (48): _build(), _clean_code(), code_helper(), _detect_intent(), _edit_action(), _explain_action(), _fix_code(), _get_gemini() (+40 more)

### Community 6 - "TelemetryHUD"
Cohesion: 0.13
Nodes (11): main(), QWidget, Set up the update timer., Set up system tray icon for control., Handle mouse press for dragging., Handle mouse move for dragging., Update all telemetry displays., Main entry point for the HUD widget. (+3 more)

### Community 7 - "_index_file"
Cohesion: 0.08
Nodes (32): _ChangeHandler, _chunk_text(), crawl_and_index(), _delete_file_chunks(), _detokenize_tokens(), _extract_text_from_file(), _get_chroma_collection(), _get_embedding_model() (+24 more)

### Community 8 - "system_monitor.py"
Cohesion: 0.07
Nodes (37): _get_cpu_temp(), _get_gpu_usage(), get_system_status(), _is_private_or_loopback(), is_protected_process(), _nvml_gpu(), Any, actions/system_monitor.py — System Metric Checks, Process Tree Watchdog &… (+29 more)

### Community 9 - "JarvisUI"
Cohesion: 0.04
Nodes (23): setter, JarvisUI, Thread-safe monitor state update used by click and voice controls., Thread-safe: raise the irreversible-action gate. Called from action handlers…, Thread-safe: take the gate down., Thread-safe: feed a 0.0–1.0 live audio level to the HUD waveform. Called from…, No-op: gaze tracking removed (face renderer removed)., Thread-safe: post a schedule of (level, openness, width) mouth frames for… (+15 more)

### Community 10 - "MinimizedHudOverlay"
Cohesion: 0.21
Nodes (3): QFont, MinimizedHudOverlay, Small independent transcript window shown while the main HUD is minimized.

### Community 12 - "MainWindow"
Cohesion: 0.05
Nodes (13): QMainWindow, MainWindow, Slot — display camera preview overlay (main thread)., Slot — runs on Qt main thread. Updates and shows the content panel., Slot — Qt main thread. Lays a document review into the content panel., Slot — Qt main thread. Puts a fresh quiz on the board., Place a floating overlay in the middle of the HUD and show it., Update bottom-left tactical audio player to display and control Spotify… (+5 more)

### Community 13 - "dev_agent.py"
Cohesion: 0.09
Nodes (39): apply_heal_patch(), _build_project(), _classify_error(), dev_agent(), _diagnose_trace(), _extract_culprit_script(), _fix_files(), _get_model() (+31 more)

### Community 14 - ".run"
Cohesion: 0.12
Nodes (12): BaseException, _get_api_key(), _is_reconnect_signal(), _keep_context_of(), Background task: voice alerts when metrics exceed thresholds., Check user-configured topics once per day; speak alerts when new headlines…, Periodically sweeps garbage during idle silence so full Generation 2…, Forward phone mic PCM chunks from dashboard queue into the Gemini Live session. (+4 more)

### Community 15 - "FileDropZone"
Cohesion: 0.11
Nodes (5): QDragEnterEvent, QDropEvent, CyberGraphicLineButton, FileDropZone, Tactical button rendered strictly with vector graphic lines, sharp 2px border…

### Community 16 - "screen_find"
Cohesion: 0.67
Nodes (3): Action handler called by ALFRED action dispatcher., screen_find(), 10. Full Desktop Control & Operating System Automation

### Community 17 - "EchoGuard"
Cohesion: 0.11
Nodes (9): EchoGuard, Classifies microphone blocks while the assistant is speaking. Usage:…, True once the estimate rests on enough real echo to be trusted., Residual left by this room's own echo. Higher = harder to separate., False when the acoustics are too poor to judge on content alone. Speakers…, The residual a block must clear right now to count as a voice., Consecutive positive blocks before an interruption is believed., 1.0 = fully explained by our own output, 0.0 = nothing to do with it. (+1 more)

### Community 18 - "desktop.py"
Cohesion: 0.12
Nodes (36): _ask_gemini_for_desktop_action(), _build_sandbox(), clean_desktop(), desktop_control(), _execute_generated_code(), _get_api_key(), _get_base_dir(), get_current_wallpaper() (+28 more)

### Community 19 - "is_heavenly_restricted"
Cohesion: 0.08
Nodes (25): _normalize(), open_app(), ActionRecord, ActionRegistry, _call_handler(), discover_actions(), _is_heavenly_restricted_params(), _opt_upper() (+17 more)

### Community 20 - "HudCanvas"
Cohesion: 0.08
Nodes (15): QPainter, HudCanvas, No-op: gaze tracking removed (face renderer removed)., Thread-safe: hand over a schedule of (level, openness, width) frames. The…, Thread-safe entry point for the audio threads. Stores the louder of the…, True only when this canvas can actually be seen by the user., Draw the Avengers: Endgame Stark Arc Reactor at (cx, cy) with outer radius r., Draw subtle background CRT coordinate grid with + crosshairs (Screenshot 2). (+7 more)

### Community 21 - "JarvisLive"
Cohesion: 0.06
Nodes (18): Event delivered to meaningful-state and completion callbacks., ScreenMonitorEvent, JarvisLive, Fast callback used by the Sentry button on the Qt thread., Forward selected changed frames from the monitor thread to the AI loop., Called when user clicks the CLEAR button in desktop GUI., Called when phone/dashboard sends a clear-chat directive., Chord pressed or released — may arrive on the hotkey thread. (+10 more)

### Community 24 - "ScreenMonitorController"
Cohesion: 0.09
Nodes (15): Exception, Poll screen capture in a daemon thread and retain only the latest frame., Start monitoring immediately; return false if a run is already active., Request a clean stop; optionally wait for the polling thread to exit., ScreenMonitorController, AnalysisCallback, CaptureCallback, EventCallback (+7 more)

### Community 25 - "get_plugin_enabled"
Cohesion: 0.14
Nodes (11): _call_run(), PluginRegistry, One entry per settings SECTION, for enabled plugins that declare a…, Invoke run() passing only the kwargs it actually declares (or all of them if it…, How this plugin's result should re-enter the conversation, if it said., get_plugin_config(), get_plugin_enabled(), get_plugin_setting() (+3 more)

### Community 26 - "_tlog"
Cohesion: 0.08
Nodes (19): FunctionResponse, _clean_transcript(), _is_repeat_chunk(), broadcast_progress(), _run_tool_bounded(), _deliver_news(), main(), runner() (+11 more)

### Community 27 - "computer_control.py"
Cohesion: 0.05
Nodes (62): _base_dir(), _clear_field(), _click(), _clipboard_get(), _clipboard_paste(), computer_control(), _drag(), _focus_window() (+54 more)

### Community 28 - "llm_client.py"
Cohesion: 0.16
Nodes (25): call_llm(), call_llm_stream(), call_llm_text(), _chat_endpoint(), check_model_available(), ensure_ollama_running(), get_base_dir(), _get_headers() (+17 more)

### Community 29 - "gmail_manager.py"
Cohesion: 0.09
Nodes (26): _get_gmail_brief(), Fetch unread emails summary via gmail_manager., _clean_header_str(), _extract_body_snippet(), fetch_unread_emails(), gmail_manager(), _load_gmail_creds(), Any (+18 more)

### Community 30 - "._process_utterance"
Cohesion: 0.33
Nodes (3): Start the local pipeline., Main processing loop: STT → LLM → TTS., Process a complete utterance: transcribe → generate response → synthesize.

### Community 31 - "TronScoreBackgroundPlayer"
Cohesion: 0.08
Nodes (12): control_playback(), _base_dir(), Path, QObject, Background music audio engine. Plays background score continuously on loop…, Set base normal volume (0.0 to 1.0). Speech ducking scales to 50% of base., Duck to 50% of base volume when speaking, restore to base volume when…, Called when Spotify plays a track. Pauses Tron background music, sets Spotify… (+4 more)

### Community 32 - "_BrowserSession"
Cohesion: 0.05
Nodes (23): browser_control(), _BrowserSession, _detect_default_browser(), _find_exe_windows(), _find_opera_windows(), _firefox_profile_dir(), _log(), _normalize_url() (+15 more)

### Community 33 - "tts.py"
Cohesion: 0.07
Nodes (24): _compress_silence(), create_tts_player(), EdgeTTSEngine, ElevenLabsTTSEngine, _import_kokoro_pipeline(), KokoroTTSEngine, _synth(), _play_audio_bytes() (+16 more)

### Community 34 - ".test_error_isolation_in_concurrent_tasks"
Cohesion: 0.29
Nodes (5): Verify that an exception in one concurrent task does not break or cancel…, Verify that a batch of tasks run with a concurrency limit of 5 scales sub-…, TestConcurrencyLimiter, execute_task(), safe_run()

### Community 35 - ".__init__"
Cohesion: 0.11
Nodes (10): ProactiveEngine, Decides when ALFRED should speak unprompted and builds a context-rich prompt.…, Build a context snapshot for Gemini. Rotates through three focus areas so…, _Popen, Exception, Turn hold-to-talk on or off. Returns the scope actually achieved., Raised inside the session TaskGroup to force a clean, voluntary reconnect (e.g.…, Session-scoped task: when a voluntary reconnect is requested, raise a signal… (+2 more)

### Community 36 - "audio_devices.py"
Cohesion: 0.12
Nodes (20): configure(), _display_name(), _is_pseudo(), list_devices(), prefetch(), _work(), _query(), _collect() (+12 more)

### Community 37 - "GraphManager"
Cohesion: 0.11
Nodes (14): GraphManager, Any, Path, Save the graph data to the JSON file atomically., Add an entity node to the graph. Returns True if successful., Add a relationship (edge) between two nodes. Returns True if successful., Apply exponential decay to all temporary nodes. Returns the number of nodes…, Query the knowledge graph for a concept and return connected subgraph up to… (+6 more)

### Community 38 - "calendar_sync.py"
Cohesion: 0.47
Nodes (5): _load_events(), Calendar Sync Plugin for ALFRED Mark-LIV. Tracks agenda, meetings,…, Execute calendar action., run(), _save_events()

### Community 39 - "CentralizedCache"
Cohesion: 0.06
Nodes (22): CentralizedCache, _canonicalize(), decorator(), wrapper(), Any, Stores value in cache with TTL. Fails open gracefully if storage fails., Deletes a key from cache. Fails open gracefully., Invalidates all keys starting with prefix. Useful for mutation hooks. (+14 more)

### Community 41 - "._apply_name_update"
Cohesion: 0.20
Nodes (8): apply_ui_accent(), current_palette(), Applies DOSSIER CRT [A-34] (#8e9bff), VECTOR CRT [WAKU] (#a8ff3e), or BATMAN…, A snapshot of the accent-linked colours currently on class C., LIVE full theme change. Replaces the old palette colours with the new ones in…, Live preview — paints the whole interface the new colour (does NOT write to…, Update all name/theme-dependent UI elements and persist to config., retheme_all_widgets()

### Community 42 - "HueWheel"
Cohesion: 0.16
Nodes (4): QPointF, QRectF, HueWheel, Circular colour picker. The user drags the handle (small white circle) around…

### Community 43 - "mono_font"
Cohesion: 0.05
Nodes (21): BiometricFingerprintWidget, _CameraPreview, ClipboardPanel, CRTReconWidget, _EqualizerBarsWidget, ImagePopupOverlay, MetricBar, mono_font() (+13 more)

### Community 44 - "TacticalAudioPlayerWidget"
Cohesion: 0.15
Nodes (5): QFrame, Sleek tactical cyber popup for adjusting master background music volume.…, Bottom-Left Cyber Tactical Audio Player Widget. Styled matching the HUD /…, TacticalAudioPlayerWidget, _VolumeSliderPopup

### Community 45 - "VisemeStream"
Cohesion: 0.13
Nodes (13): collections, coverage(), Text → mouth shape, fused with the audio the avatar is actually speaking. Why…, Reduce any character to a bare Latin letter, or "" if it has none. This is what…, Fraction of the letters in `text` we can reduce to a Latin sound., Split a line of speech into (viseme, duration-weight) pairs. Returns [] for…, Fuses the transcript's shape sequence onto the audio's timing. Thread note:…, Blend audio frames [(level, openness, width)] with the text queue. (+5 more)

### Community 46 - "screen_processor.py"
Cohesion: 0.16
Nodes (18): _capture_camera(), _compress(), _cv2_backend(), _detect_camera_index(), _get_camera_index(), _get_os(), _load_config(), _probe_camera() (+10 more)

### Community 47 - "protocol_engine.py"
Cohesion: 0.06
Nodes (49): create_protocol(), _do_save(), _ensure_user_protocols_dir(), execute_protocol(), _execute_tool(), get_action_registry(), _get_default_protocols_path(), get_protocols_file() (+41 more)

### Community 48 - "load_api_keys"
Cohesion: 0.08
Nodes (28): LiveConnectConfig, The optional knobs, kept apart so one bad field can be dropped wholesale. Every…, get_app_icon(), get_assistant_name(), get_gemini_key(), get_llm_provider(), get_media_resolution(), get_openrouter_key() (+20 more)

### Community 49 - "spotify_control.py"
Cohesion: 0.05
Nodes (42): authorize_user(), _get_base_dir(), get_devices(), get_spotify_client(), manage_queue(), _OAuthCallbackHandler, Any, Path (+34 more)

### Community 50 - "subprocess"
Cohesion: 0.14
Nodes (14): _prediction_score(), Local wake-word detection for ALFRED ("Hey Alfred"). Design goals: • ZERO cost…, Return the Alfred score while tolerating backend-specific key suffixes., hashlib, _check_assets(), _check_python(), main(), MARK LIV — one-time setup. Installs the Python dependencies for THIS operating… (+6 more)

### Community 51 - "CustomizeOverlay"
Cohesion: 0.19
Nodes (6): CustomizeOverlay, _lbl(), Floating glassmorphic overlay for configuring Assistant Persona, Commander…, Refresh reusable controls from persisted settings before showing., Highlight the selected voice pill; dim the rest., Updates the selected colour; hex box + wheel stay in sync, theme is live-…

### Community 52 - "computer_settings"
Cohesion: 0.12
Nodes (16): brightness_get(), brightness_set(), computer_settings(), dark_mode(), paste(), press_key(), Current brightness 0-100, or None where it cannot be read., Set brightness to an absolute percentage. Only used to restore a value captured… (+8 more)

### Community 53 - "_patch_config"
Cohesion: 0.15
Nodes (13): get_input_device(), get_output_device(), _patch_config(), Persist assistant name and user name to config., Persist the chosen Live voice. Unknown names collapse to the default so a bad…, Read-modify-write one or more keys in api_keys.json. Every setter in this file…, Microphone device name, or '' for the system default., Speaker device name, or '' for the system default. (+5 more)

### Community 54 - "PluginSettingsOverlay"
Cohesion: 0.17
Nodes (6): QPushButton, QVBoxLayout, PluginManagerOverlay, PluginSettingsOverlay, Floating overlay — lists discovered plugins with per-plugin ON/OFF toggles., Floating overlay — renders per-plugin settings forms. Fully generic: it…

### Community 55 - "_HudOverlay"
Cohesion: 0.17
Nodes (6): AudioDeviceOverlay, ConfirmBanner, _HudOverlay, Base for the floating panels placed by hand over the HUD. They are children of…, The gate in front of an action that cannot be taken back. The old confirmation…, Choose which microphone ALFRED listens to and which speakers it uses. Both…

### Community 56 - "DashboardServer"
Cohesion: 0.05
Nodes (34): DashboardServer, action_ep(), audio_ws(), _auth(), auto_login(), clear_chat_ep(), command(), device_login_ep() (+26 more)

### Community 57 - "screen_monitor.py"
Cohesion: 0.09
Nodes (18): AnalysisResult, _default_analyzer(), _fingerprint_key(), Reusable, in-memory continuous screen monitoring. The controller owns only the…, Return normalized mean absolute difference in the range 0.0 to 1.0., Detect context, visual-frame, and explicit completion changes., One captured frame and its metadata, retained only until the next frame., Result returned by a screen analyzer. (+10 more)

### Community 58 - "PushToTalk"
Cohesion: 0.20
Nodes (5): PushToTalk, Begin watching. Returns the scope actually achieved., Feed a press/release from a Qt shortcut (non-Windows, or no hook)., Calls `on_change(held: bool)` whenever the chord is pressed or released. Start…, global' once a system-wide hook is running, else 'window'.

### Community 59 - "._build_right_panel"
Cohesion: 0.17
Nodes (3): QHBoxLayout, Style the COGNITIVE TRACE toggle to reflect its on/off state., Show or hide the agent's internal reasoning trace in the chat log.

### Community 60 - "tech_font"
Cohesion: 0.15
Nodes (8): _row(), CapabilitiesOverlay, Floating glassmorphic overlay displaying a categorized directory of everything…, Floating overlay — QR code for instant phone pairing + manual key fallback., Call from any thread when a phone successfully connects., RemoteKeyOverlay, _lbl(), tech_font()

### Community 61 - "TestBackgroundWorkerPool"
Cohesion: 0.14
Nodes (6): Verify that calling interrupt() sets halt event, immediately stops active…, Verify that _safe_background_announce waits until ALFRED finishes speaking…, Verify queue_background_task is registered in TOOL_DECLARATIONS., Verify that queue_background_task returns immediately (sub-millisecond), and…, Dispatch a mock task and verify voice PTT interaction continues with sub-second…, TestBackgroundWorkerPool

### Community 62 - "_FakeButton"
Cohesion: 0.12
Nodes (7): Key Changes, chord_label(), Human-readable name of the chord, for the UI and the logs., _FakeButton, _FakeLog, Request screen-only monitoring from the application controller., Apply monitor state on the Qt thread for click and voice controls.

### Community 63 - "LocalSTTManager"
Cohesion: 0.05
Nodes (25): LocalSTTManager, audio_callback_wrapper(), Process audio bytes for transcription based on engine type., Cancel any pending debounce timer, thread-safe., Reset the FINISH_MS countdown from zero., Timer callback: commit the accumulated sentence to the queue., Immediately commit whatever is in the buffer (+ optional extra word)., Process audio using Vosk streaming STT. Final results are held for FINISH_MS… (+17 more)

### Community 65 - "qcol"
Cohesion: 0.22
Nodes (5): QColor, _DropCanvas, _file_category(), _fmt_size(), qcol()

### Community 66 - "main.py"
Cohesion: 0.07
Nodes (29): Tactical Audio Core Control Action for ALFRED. Controls the tactical HUD's…, ProactiveEngine 2.0 — context-aware, time-aware, non-repetitive background…, Push-to-talk — hold a key, speak, release. Why this exists ---------------…, create_local_pipeline(), Local audio pipeline coordinator for MARK XL. Handles STT → LLM → TTS flow for…, Create and configure a local pipeline coordinator., create_local_stt_engine(), Local Speech-to-Text wrappers for MARK XL. Provides unified interface for… (+21 more)

### Community 67 - "ALFRED — MARK-IV (Wayne Protocol Edition)"
Cohesion: 0.12
Nodes (15): 11. High-Performance Memory & Conversational Briefing Customizer, 12. Real-Time Insignia & Chassis Hot-Swapper, 13. Protocol Engine & Multi-Step Macro Playbooks (`config/protocols.yaml`), 14. Local Hybrid Visual Grounding (RapidOCR + ONNX + Gemini Fallback), 15. Process-Level Audio Ducking & Background Concurrency, 17. System Architecture & File Structure, 19. Configuration Reference (`config/api_keys.json`), 20. Knowledge Graph (`graphify`) (+7 more)

### Community 68 - "_SysMetrics"
Cohesion: 0.16
Nodes (6): Called from Qt main thread when user presses Remote Control., Thread-safe speech channel for plugins: lets a plugin ask JARVIS to say…, 1. What's New: Recent Enhancements, Bug Fixes & Stability Updates, _nvml_gpu_windows(), Return NVIDIA GPU utilisation % using nvml.dll directly — zero subprocess., _SysMetrics

### Community 69 - "memory_manager.py"
Cohesion: 0.10
Nodes (25): Update Daily Briefing Preferences Action for ALFRED Mark-LIV. Permanently…, Permanently saves daily briefing preferences into long-term memory., update_daily_briefing(), _do_shutdown(), Summarise the current session in 1-2 sentences and save to long_term.json., _all_entries(), _empty_memory(), forget() (+17 more)

### Community 70 - "echo.py"
Cohesion: 0.09
Nodes (18): audio_core(), Any, Main handler for the Audio Core control action., _duck_linux(), duck_media_apps(), _worker(), _duck_windows(), is_ducked() (+10 more)

### Community 71 - "._log"
Cohesion: 0.24
Nodes (5): Log message via callback or print., Set UI state via callback., Handle wake word detection., Handle barge-in/interruption., Put the assistant to sleep.

### Community 72 - "WakeWordDetector"
Cohesion: 0.20
Nodes (4): Runs the wake model in a dedicated thread. The mic thread calls feed() with raw…, Load the model and spawn the inference thread. Returns True on success. Safe to…, Called from the mic callback (real-time thread). Must stay cheap and never…, WakeWordDetector

### Community 73 - "TestMinimizedHudOverlay"
Cohesion: 0.17
Nodes (3): _LogSource, QObject, TestMinimizedHudOverlay

### Community 74 - "re"
Cohesion: 0.17
Nodes (11): _auto_detect_type(), _config_dir(), intel_notes(), _load_notes(), Path, actions/intel_notes.py — Dedicated Intel & Notes Terminal Action. Provides a…, Action handler called by Gemini / action_loader., _save_notes() (+3 more)

### Community 75 - "TestHudReactivity"
Cohesion: 0.14
Nodes (3): TestHudReactivity, Acoustic control with a cheap listening-level outline., ReactiveMicButton

### Community 76 - "._build_jarvis_icon"
Cohesion: 0.22
Nodes (4): Render an ALFRED tactical icon at 4× resolution and downsample for crisp…, Create a Windows .lnk shortcut WITHOUT launching PowerShell or cmd. Tries…, Resolve the user's REAL desktop directory instead of assuming ~/Desktop, which…, Create a desktop shortcut on Windows / macOS / Linux. Never opens a terminal,…

### Community 77 - "LocalPipelineCoordinator"
Cohesion: 0.14
Nodes (8): LocalPipelineCoordinator, Coordinates STT → LLM → TTS flow., Set callbacks for UI updates., Stop the local pipeline., Callback for audio from STT manager., Handle end of speech detection., Check if UI is muted., Enable or disable wake word detection.

### Community 78 - "installer.py"
Cohesion: 0.32
Nodes (7): _available(), install_for_config(), _pip(), MARK XL — Dependency auto-installer. Called automatically on first launch and…, Return True if the module can be imported (no actual import)., Install all missing packages required by *config*. Blocking — always call from…, importlib_util

### Community 79 - "LogWidget"
Cohesion: 0.25
Nodes (3): QTextEdit, LogWidget, Cancel any in-flight typing animation, drain the queue, and clear the display.

### Community 80 - "._build_system_instruction"
Cohesion: 0.14
Nodes (15): _describe_limits(), _describe_tools(), One line per capability, straight from the live tool declarations. Derived…, The other half of self-knowledge: what is out of reach, and why. Derived from…, Fill {tokens} in the prompt template. A plain replace rather than str.format:…, _render_prompt(), _entry_value(), format_memory_for_prompt() (+7 more)

### Community 81 - "ScreenMonitorStatus"
Cohesion: 0.40
Nodes (3): Return an immutable snapshot without copying or persisting image bytes., Thread-safe snapshot of controller state., ScreenMonitorStatus

### Community 82 - "MemoryOverlay"
Cohesion: 0.25
Nodes (6): all_entries_for_ui(), Flat list for the memory panel: what ALFRED knows, and when it learned it.…, MemoryOverlay, Everything ALFRED has stored about you, and when it learned it. Memory used to…, Take every item out of the layout and detach it from the widget tree in this…, Size the panel to its content, re-centre it, and repaint what the old size…

### Community 83 - "SetupOverlay"
Cohesion: 0.14
Nodes (10): Update probe widgets on the Qt thread via a queued signal., Read api_keys.json config dict. Returns {} on any error., Build expensive reusable settings widgets after first paint., _read_full_config(), SetupOverlay, _lbl(), _check(), _worker() (+2 more)

### Community 84 - "confirm.py"
Cohesion: 0.21
Nodes (12): bind(), _log(), _Pending, pending_title(), core/confirm.py — a confirmation the model cannot forge. THE PROBLEM WITH THE…, Called by the UI when the user presses CONFIRM or CANCEL. Runs the stored…, when nothing is waiting. Lets an action avoid stacking two banners., Wire this module to the HUD. Called once from main.py at startup. (+4 more)

### Community 85 - "install_and_download"
Cohesion: 0.40
Nodes (6): install_and_download(), is_installed(), is_ready(), True if the openwakeword package is importable (no model check)., True if openwakeword is installed AND its model files are present on disk. This…, One-click setup for the UI button: pip-install openwakeword if missing, then…

### Community 86 - "ImagePopupOverlay"
Cohesion: 0.15
Nodes (9): action(), ImagePopupOverlay, QWidget, Handle mouse move for window dragging., Handle mouse release for window dragging., Show the popup centered over the parent widget., Show an image popup overlay., Popup overlay to display an image with a dismiss button. (+1 more)

### Community 87 - "band_energies"
Cohesion: 0.29
Nodes (5): band_energies(), ndarray, Record a slice of what is being played, for later comparison., True if this microphone block is a different voice, not our echo., Raw energy per speech band — the fingerprint we compare. Left unnormalised on…

### Community 88 - "datetime"
Cohesion: 0.41
Nodes (11): _base_dir(), _get_os(), Path, reminder(), _sanitise(), _schedule_linux(), _schedule_mac(), _schedule_windows() (+3 more)

### Community 89 - "plugin_loader.py"
Cohesion: 0.17
Nodes (14): copy, discover_plugins(), _load_error(), _opt_upper(), PluginRecord, Exception, Path, Plugin discovery, validation, collision detection, and dispatch. Discovery runs… (+6 more)

### Community 90 - "config_manager.py"
Cohesion: 0.10
Nodes (28): _config_signature_unlocked(), ensure_config_dir(), get_base_dir(), get_hud_style(), get_plugin_settings_revision(), invalidate_config_cache(), _plugin_settings_state(), Path (+20 more)

### Community 91 - "save_app_icon"
Cohesion: 0.20
Nodes (10): Update App Icon Action for ALFRED Mark-LIV. Switches the application window,…, Updates the main application icon and taskbar badge in realtime., update_app_icon(), Save the chosen app icon setting to config., save_app_icon(), format_icon_display_name(), get_available_app_icons(), Format an icon file name into an authentic, sleek tactical insignia title. (+2 more)

### Community 92 - "_detect_action"
Cohesion: 0.40
Nodes (5): _detect_action(), _normalise(), Resolve a free-text description to an action name, locally. Returns {"action":…, What to tell the model when nothing matched. Names real actions so its retry…, _suggest()

### Community 93 - "sys"
Cohesion: 0.09
Nodes (27): Daily Brief Action for ALFRED Mark-LIV. Provides the ultimate morning and daily…, actions/doc_rag.py — Local Document RAG with ChromaDB and nomic-embed-text-v1.5…, Stop the watchdog observer., stop_watchdog(), actions/screen_find.py — Local Hybrid Element Grounding for ALFRED. Performs…, Process-level Audio Ducking for ALFRED. Automatically ducks background media…, Execute unducking on Windows via pycaw, restoring exact prior volume levels., Execute unducking on Linux via pulsectl. (+19 more)

### Community 94 - "focus_protocol.py"
Cohesion: 0.47
Nodes (5): Focus Protocol Plugin for ALFRED Mark-LIV. Manages deep work intervals,…, Execute focus protocol actions., _read_state(), run(), _write_state()

### Community 95 - "._apply_ptt_shortcut"
Cohesion: 0.18
Nodes (5): _press(), Floating overlay panel shown when the ⚙ header button is toggled., Repaint the push-to-talk row from the saved setting., Bind the chord inside the window when no global hook is available. On macOS and…, Report a windowed press/release to whoever owns the microphone.

### Community 96 - "🎙️ 5. Master Tactical Voice Command Codex & Operational Handbook"
Cohesion: 0.20
Nodes (10): 👁️ 1. Desktop Automation, Screen & Multimodal Vision, ⚙️ 2. Operating System, Hardware Settings & Applications, ⚡ 3. Compound Protocols & Workflow Macros, 🧠 4. Memory, History & Universal Reversibility, 📰 5. Intelligence, Briefings, News & Weather, 🎙️ 5. Master Tactical Voice Command Codex & Operational Handbook, 📱 6. Quantum Mobile Remote & Web Telemetry Uplink, 🎧 7. Spotify AI Agent & Music Streaming (+2 more)

### Community 97 - "capture_screen"
Cohesion: 0.15
Nodes (8): capture_screen(), _capture_screen(), Hybrid return payload for screen captures. - Behaves as a 3-tuple `(img_bytes,…, Captures primary or specified monitor, queries active OS window context,…, Default entry point used by main.py., ScreenCapturePayload, _do_stream(), tuple

### Community 98 - "LocalLLMManager"
Cohesion: 0.18
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
Cohesion: 0.15
Nodes (13): 2. 100% Local & Air-Gapped Offline Execution: Switching from Gemini to Local API, Configuration Template for LM Studio / vLLM (OpenAI-Compatible):, Configuration Template for Ollama:, Configuration Template for OpenRouter API (Frontier Multi-Model Gateway):, Detailed Step-by-Step Guide: How to Switch to a Local API, Gemini Live API vs. Local Offline API Comparison, Option A: Ollama (Recommended — Simplest Setup), Option B: LM Studio (Recommended for GUI Users) (+5 more)

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

### Community 132 - "TestScreenProcessorWindowContext"
Cohesion: 0.15
Nodes (8): format_window_context(), Format the standard metadata block: [WINDOW_CONTEXT] App: <Name> | Title:…, Verifies system falls back to 'App: Unknown' without raising exceptions., Verification Requirement: Verify [WINDOW_CONTEXT] header contains VS Code and…, Verifies that active window query resolves in < 15ms and adheres to schema., Verifies exact string formatting requirements., Verifies capture_screen() returns valid compressed image and window context., TestScreenProcessorWindowContext

### Community 133 - "daily_brief"
Cohesion: 0.13
Nodes (13): daily_brief(), _get_greeting(), _get_live_weather(), _get_reminders_brief(), _get_system_vitals(), Check scheduled reminders in ~/.alfred/reminders or ~/.jarvis/reminders., Inspect core CPU, RAM, and Battery vitals., Executes the daily briefing and delivers spoken synthesis. (+5 more)

### Community 135 - "._dispatch_tool"
Cohesion: 0.21
Nodes (14): add_monitor(), check_all(), _is_blocked(), list_monitors(), _load(), BackgroundMonitor — user-configured topic watching. Checks DDG news once per…, Run all pending topic checks (once per day per topic). Returns a list of…, remove_monitor() (+6 more)

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
Cohesion: 0.13
Nodes (16): Action to show an image popup overlay., qt_sequence(), The same chord as a QKeySequence string., get_brief_enabled(), save_brief_enabled(), psutil, pyqt6_qtcore, pyqt6_qtgui (+8 more)

### Community 140 - "pathlib"
Cohesion: 0.10
Nodes (20): asyncio, base64, core, _make_uploads_dir(), Path, dashboard/server.py — ALFRED Local HTTP Dashboard Plain HTTP on port 8000 (no…, Return (and create) the cross-platform uploads folder., fastapi (+12 more)

### Community 141 - "Q: Read uiperformance.md and continousmonitoring.md and perform the tasks in the most efficient manner"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Read uiperformance.md and continousmonitoring.md and perform the tasks in the most efficient manner, Source Nodes

### Community 143 - "Continuous Screen Monitoring Plan"
Cohesion: 0.29
Nodes (6): Assumptions, Continuous Screen Monitoring Plan, Monitoring Behavior, Stop Conditions, Summary, Tests

### Community 145 - "Q: Implement the ALFRED MK-IV speech-reactive graphical UI plan efficiently"
Cohesion: 0.50
Nodes (3): Answer, Q: Implement the ALFRED MK-IV speech-reactive graphical UI plan efficiently, Source Nodes

### Community 148 - "18. Quick Start & Installation"
Cohesion: 0.67
Nodes (3): 18. Quick Start & Installation, 1. Prerequisites, 2. Setup & Execution

### Community 151 - "format_visual_payload"
Cohesion: 0.40
Nodes (3): format_visual_payload(), Prepares the visual frame payload dictionary for the Gemini Live API…, Verifies metadata block is prepended directly to the visual frame payload.

### Community 152 - "Q: change wake key to hey Alfred no t jarvis"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: change wake key to hey Alfred no t jarvis, Source Nodes

### Community 153 - "App Performance Plan"
Cohesion: 0.33
Nodes (5): App Performance Plan, Assumptions, Key Changes, Summary, Test Plan

### Community 156 - "._play_audio"
Cohesion: 0.20
Nodes (7): callback(), _open_mic(), _pcm_level(), _pcm_visemes(), True while the speakers may still be finishing our last sentence., Map a block of int16 PCM samples to a 0.0–1.0 loudness level for the HUD…, Slice a PCM block into (level, openness, width) frames, one per 20 ms. Returns…

### Community 171 - ".__init__"
Cohesion: 0.14
Nodes (4): _fl(), Update application and window icon in realtime., Returns True if auto-start is currently registered on this OS., Open the API key and neural backend configuration overlay from settings.

## Knowledge Gaps
- **81 isolated node(s):** `Purpose`, `Rules`, `Purpose`, `Rules`, `Persona & Demeanor` (+76 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1215 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **25 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MainWindow` connect `MainWindow` to `qcol`, `._apply_name_update`, `JarvisUI`, `ui.py`, `mono_font`, `.__init__`, `_scaled_icon_pixmap`, `._build_jarvis_icon`, `tech_font`, `save_app_icon`, `SetupOverlay`, `._wake_state`, `_HudOverlay`, `screen_monitor.py`, `._build_right_panel`, `.clear_chat`, `_FakeButton`, `._apply_ptt_shortcut`?**
  _High betweenness centrality (0.081) - this node is a cross-community bridge._
- **Why does `JarvisLive` connect `JarvisLive` to `._dispatch_tool`, `system_monitor.py`, `JarvisUI`, `pathlib`, `.run`, `EchoGuard`, `ScreenMonitorController`, `_tlog`, `._play_audio`, `llm_client.py`, `.__init__`, `VisemeStream`, `load_api_keys`, `DashboardServer`, `screen_monitor.py`, `PushToTalk`, `TestBackgroundWorkerPool`, `_FakeButton`, `main.py`, `_SysMetrics`, `memory_manager.py`, `echo.py`, `WakeWordDetector`, `._build_system_instruction`, `ScreenMonitorStatus`?**
  _High betweenness centrality (0.070) - this node is a cross-community bridge._
- **Why does `JarvisUI` connect `JarvisUI` to `main.py`, `.__init__`, `._apply_name_update`, `ui.py`, `mono_font`, `.__init__`, `HudCanvas`, `JarvisLive`, `._wake_state`, `_HudOverlay`, `_tlog`, `._apply_ptt_shortcut`, `.clear_chat`?**
  _High betweenness centrality (0.057) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `JarvisLive` (e.g. with `Key Changes` and `ProactiveEngine`) actually correct?**
  _`JarvisLive` has 14 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Purpose`, `Rules`, `Purpose` to the rest of the system?**
  _81 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `game_updater.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06190476190476191 - nodes in this community are weakly interconnected._
- **Should `file_controller.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06690140845070422 - nodes in this community are weakly interconnected._