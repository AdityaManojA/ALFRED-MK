# Graph Report - Alfred-Mark-IV  (2026-09-27)

## Corpus Check
- 101 files · ~201,129 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 14 file(s) not represented in the graph (top: .ico 7, (none) 3, .obj 2)

## Summary
- 2641 nodes · 5152 edges · 152 communities (126 shown, 26 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 209 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `598dfc87`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- game_updater.py
- file_controller.py
- add_clipboard_item
- file_processor.py
- web_search.py
- code_helper.py
- TelemetryHUD
- doc_rag.py
- system_monitor.py
- JarvisUI
- protocol_engine.py
- computer_settings.py
- MainWindow
- dev_agent.py
- ui.py
- FileDropZone
- tts.py
- EchoGuard
- desktop.py
- action_loader.py
- qcol
- JarvisLive
- config_manager.py
- setter
- .__init__
- plugin_loader.py
- _tlog
- computer_control.py
- local_pipeline.py
- .run
- mono_font
- TronScoreBackgroundPlayer
- _BrowserSession
- ClipboardManager
- .test_error_isolation_in_concurrent_tasks
- .__init__
- audio_devices.py
- GraphManager
- datetime
- CentralizedCache
- crypto-js.min.js
- screen_find.py
- ._build_right_panel
- .__init__
- TacticalAudioPlayerWidget
- VisemeStream
- screen_processor.py
- TestProtocolEngine
- TestStreamingMemoryBenchmark
- spotify_control.py
- server.py
- CustomizeOverlay
- computer_settings
- unduck_media_apps
- tech_font
- ._receive_audio
- ._build_app
- ._dispatch_tool
- find_element
- time
- LocalLLMManager
- TestBackgroundWorkerPool
- ScreenCapturePayload
- LocalSTTManager
- NotesTerminalWidget
- save_app_icon
- LocalTTSManager
- ALFRED — MARK-IV (Wayne Protocol Edition)
- _SysMetrics
- json
- echo.py
- ._apply_name_update
- WakeWordDetector
- get_active_window_info
- daily_brief.py
- create_protocol
- undo.py
- LocalPipelineCoordinator
- ._aes_key
- LogWidget
- test_screen_processor.py
- DashboardServer
- MemoryOverlay
- SetupOverlay
- PushToTalk
- ._build_jarvis_icon
- ImagePopupOverlay
- confirm.py
- os
- check_path_access
- _get_user_protocols_path
- _VolumeSliderPopup
- _detect_action
- PluginManagerOverlay
- _gemini_grounding
- ._apply_ptt_shortcut
- 🎙️ 3. Master Tactical Voice Command Codex & Operational Handbook
- ProactiveEngine
- TestScreenProcessorWindowContext
- Daily Brief Protocol
- Email Handling Rules
- Executive Assistant Persona & Behavioral Standards
- Detailed Step-by-Step Guide: How to Switch to a Local API
- /email-triage Workflow
- _template.py
- 6. Spotify AI Agent: Dual-Tier Web API & Native Playback Architecture
- _get_base_dir
- _unduck_linux
- Graphify + Antigravity Project Workflow & Setup Guide
- _get_macos_wifi_interface
- ._decrypt
- _ensure_network_access
- rules/graphify.md
- workflows/graphify.md
- chromadb
- chromadb_config
- setup.py
- fastembed
- sentence_transformers
- TestAudioDucker
- watchdog_events
- watchdog_observers
- format_window_context
- get_push_to_talk_enabled
- ._listen_audio
- subprocess
- File & Folder Exploration and Notes Directives
- install_and_download
- duck_media_apps
- /deep-work Workflow
- main.py
- File & Folder Exploration Workflow
- TTSPlayer
- test_traceback_benchmark.py
- get_available_app_icons
- ._toggle_sentry_mode
- SubjectDossierCard
- 15. Bug Fixes & Stability Updates
- _RootShim
- audio_core
- classify_content_type
- Step 1: Install & Set Up Your Preferred Local LLM Server
- type_text
- 17. Quick Start & Installation
- get_base_dir
- create_local_pipeline

## God Nodes (most connected - your core abstractions)
1. `MainWindow` - 101 edges
2. `JarvisLive` - 66 edges
3. `JarvisUI` - 49 edges
4. `tech_font()` - 38 edges
5. `mono_font()` - 37 edges
6. `_BrowserSession` - 32 edges
7. `TronScoreBackgroundPlayer` - 32 edges
8. `computer_control()` - 26 edges
9. `is_heavenly_restricted()` - 26 edges
10. `DashboardServer` - 26 edges

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

## Communities (152 total, 26 thin omitted)

### Community 0 - "game_updater.py"
Cohesion: 0.06
Nodes (81): _build_google_flights_url(), flight_finder(), _format_spoken(), _format_text_report(), _get_base_dir(), _parse_date(), _parse_flights_with_gemini(), Path (+73 more)

### Community 1 - "file_controller.py"
Cohesion: 0.12
Nodes (44): copy_file(), create_file(), create_folder(), delete_file(), explore_folder(), file_controller(), find_files(), _format_size() (+36 more)

### Community 2 - "add_clipboard_item"
Cohesion: 0.10
Nodes (18): add_clipboard_item(), clipboard_manager_action(), get_recent_clipboards(), paste_clipboard_item(), Any, Return the most recent count items in chronological order (oldest to newest…, Polling loop inspecting OS clipboard., Action handler called by ALFRED action dispatcher. (+10 more)

### Community 3 - "file_processor.py"
Cohesion: 0.14
Nodes (32): _detect_type(), file_processor(), _file_size_str(), _gemini_client(), _output_path(), _process_archive(), _process_audio(), _process_code() (+24 more)

### Community 4 - "web_search.py"
Cohesion: 0.08
Nodes (41): _compare(), _fetch_item(), _ddg_news(), _ddg_search(), _format_ddg(), _format_news(), _gemini_available(), _gemini_headlines() (+33 more)

### Community 5 - "code_helper.py"
Cohesion: 0.08
Nodes (48): _build(), _clean_code(), code_helper(), _detect_intent(), _edit_action(), _explain_action(), _fix_code(), _get_gemini() (+40 more)

### Community 6 - "TelemetryHUD"
Cohesion: 0.13
Nodes (11): main(), QWidget, Set up the update timer., Set up system tray icon for control., Handle mouse press for dragging., Handle mouse move for dragging., Update all telemetry displays., Main entry point for the HUD widget. (+3 more)

### Community 7 - "doc_rag.py"
Cohesion: 0.09
Nodes (35): _ChangeHandler, _chunk_text(), crawl_and_index(), _delete_file_chunks(), _detokenize_tokens(), _extract_text_from_file(), _get_chroma_collection(), _get_embedding_model() (+27 more)

### Community 8 - "system_monitor.py"
Cohesion: 0.07
Nodes (38): _get_cpu_temp(), _get_gpu_usage(), get_system_status(), _is_private_or_loopback(), is_protected_process(), _nvml_gpu(), Any, actions/system_monitor.py — System Metric Checks, Process Tree Watchdog &… (+30 more)

### Community 9 - "JarvisUI"
Cohesion: 0.05
Nodes (20): main(), JarvisUI, Thread-safe: raise the irreversible-action gate. Called from action handlers…, Thread-safe: take the gate down., Thread-safe: feed a 0.0–1.0 live audio level to the HUD waveform. Called from…, Ask the avatar to look somewhere for a moment (see HoloAvatar.glance)., Thread-safe: post a schedule of (level, openness, width) mouth frames for…, Thread-safe: wipe the on-screen conversation chat feed. (+12 more)

### Community 10 - "protocol_engine.py"
Cohesion: 0.17
Nodes (22): execute_protocol(), _execute_tool(), get_action_registry(), interpolate_variables(), _is_failure(), list_protocols(), load_protocols(), match_trigger() (+14 more)

### Community 12 - "MainWindow"
Cohesion: 0.05
Nodes (13): QMainWindow, MainWindow, Slot — display camera preview overlay (main thread)., Slot — runs on Qt main thread. Updates and shows the content panel., Slot — Qt main thread. Lays a document review into the content panel., Slot — Qt main thread. Puts a fresh quiz on the board., Place a floating overlay in the middle of the HUD and show it., Update bottom-left tactical audio player to display and control Spotify… (+5 more)

### Community 13 - "dev_agent.py"
Cohesion: 0.09
Nodes (41): apply_heal_patch(), _build_project(), _classify_error(), dev_agent(), _diagnose_trace(), _extract_culprit_script(), _fix_files(), _get_model() (+33 more)

### Community 14 - "ui.py"
Cohesion: 0.11
Nodes (23): Action to show an image popup overlay., list_devices(), Device names for 'input' or 'output'. Falls back to a synchronous query if the…, core_avatar, get_input_device(), get_output_device(), _patch_config(), Read-modify-write one or more keys in api_keys.json. Every setter in this file… (+15 more)

### Community 15 - "FileDropZone"
Cohesion: 0.08
Nodes (8): QDragEnterEvent, QDropEvent, CyberGraphicLineButton, _DropCanvas, _file_category(), FileDropZone, _fmt_size(), Tactical button rendered strictly with vector graphic lines, sharp 2px border…

### Community 16 - "tts.py"
Cohesion: 0.09
Nodes (23): Local Text-to-Speech wrappers for MARK XL. Provides unified interface for…, _compress_silence(), create_tts_player(), EdgeTTSEngine, ElevenLabsTTSEngine, _import_kokoro_pipeline(), KokoroTTSEngine, _synth() (+15 more)

### Community 17 - "EchoGuard"
Cohesion: 0.08
Nodes (14): band_energies(), EchoGuard, ndarray, Classifies microphone blocks while the assistant is speaking. Usage:…, True once the estimate rests on enough real echo to be trusted., Residual left by this room's own echo. Higher = harder to separate., False when the acoustics are too poor to judge on content alone. Speakers…, The residual a block must clear right now to count as a voice. (+6 more)

### Community 18 - "desktop.py"
Cohesion: 0.12
Nodes (36): _ask_gemini_for_desktop_action(), _build_sandbox(), clean_desktop(), desktop_control(), _execute_generated_code(), _get_api_key(), _get_base_dir(), get_current_wallpaper() (+28 more)

### Community 19 - "action_loader.py"
Cohesion: 0.14
Nodes (13): ActionRecord, ActionRegistry, _call_handler(), discover_actions(), _is_heavenly_restricted_params(), _opt_upper(), Path, Action discovery, validation, and dispatch — the built-in twin of… (+5 more)

### Community 20 - "qcol"
Cohesion: 0.08
Nodes (19): QColor, QPainter, QPixmap, HudCanvas, qcol(), Ask the avatar to look somewhere for a moment (see HoloAvatar.glance)., Thread-safe: hand over a schedule of (level, openness, width) frames. The…, Thread-safe entry point for the audio threads. Stores the louder of the… (+11 more)

### Community 21 - "JarvisLive"
Cohesion: 0.11
Nodes (9): JarvisLive, Called when user clicks the CLEAR button in desktop GUI., Called when phone/dashboard sends a clear-chat directive., Chord pressed or released — may arrive on the hotkey thread., Called from the detector thread when 'Hey Jarvis' is heard., Auto-sleep after the configured silence window (wake-word mode only)., Enable/disable wake word from the settings UI. Returns a status token:…, Manual sleep/wake button in the UI. (+1 more)

### Community 22 - "config_manager.py"
Cohesion: 0.06
Nodes (50): LiveConnectConfig, The optional knobs, kept apart so one bad field can be dropped wholesale. Every…, ensure_config_dir(), get_app_icon(), get_assistant_name(), get_base_dir(), get_brief_enabled(), get_gemini_key() (+42 more)

### Community 23 - "setter"
Cohesion: 0.09
Nodes (5): setter, _work(), Combined state for the two wake-word buttons. Readiness is a cheap,…, Thread-safe UI slot: wipe chat display., Wipe chat log and trigger any registered callback (e.g. backend/mobile sync).

### Community 24 - ".__init__"
Cohesion: 0.11
Nodes (5): _fl(), Floating overlay panel shown when the ⚙ header button is toggled., Returns True if auto-start is currently registered on this OS., Open the API key and neural backend configuration overlay from settings., Update application and window icon in realtime.

### Community 25 - "plugin_loader.py"
Cohesion: 0.10
Nodes (21): _call_run(), discover_plugins(), _load_error(), _opt_upper(), PluginRecord, PluginRegistry, Exception, Path (+13 more)

### Community 26 - "_tlog"
Cohesion: 0.15
Nodes (10): broadcast_progress(), _deliver_news(), runner(), Announce background completion ensuring ALFRED does not talk over active speech., Execute a single background job, streaming [control] [background XX%] progress., Worker loop consuming background jobs from background_task_queue., Format terminal log report without emojis using red bracketed tags, and…, Two-phase briefing optimized for speed: Phase 1 — instant greeting (no tools) →… (+2 more)

### Community 27 - "computer_control.py"
Cohesion: 0.17
Nodes (27): _base_dir(), _clear_field(), _click(), _clipboard_get(), _clipboard_paste(), computer_control(), _drag(), _focus_window() (+19 more)

### Community 28 - "local_pipeline.py"
Cohesion: 0.17
Nodes (24): call_llm(), call_llm_stream(), call_llm_text(), _chat_endpoint(), check_model_available(), ensure_ollama_running(), _get_headers(), get_llm_provider() (+16 more)

### Community 29 - ".run"
Cohesion: 0.13
Nodes (10): BaseException, _get_api_key(), _is_reconnect_signal(), _keep_context_of(), Background task: voice alerts when metrics exceed thresholds., Check user-configured topics once per day; speak alerts when new headlines…, Periodically sweeps garbage during idle silence so full Generation 2…, Forward phone mic PCM chunks from dashboard queue into the Gemini Live session. (+2 more)

### Community 30 - "mono_font"
Cohesion: 0.14
Nodes (5): QVBoxLayout, mono_font(), PluginSettingsOverlay, Floating overlay — renders per-plugin settings forms. Fully generic: it…, Collapsible panel below the HUD — shows search results, news, briefings. Hidden…

### Community 31 - "TronScoreBackgroundPlayer"
Cohesion: 0.08
Nodes (12): control_playback(), QObject, _base_dir(), Path, Background music audio engine. Plays background score continuously on loop…, Set base normal volume (0.0 to 1.0). Speech ducking scales to 50% of base., Duck to 50% of base volume when speaking, restore to base volume when…, Called when Spotify plays a track. Pauses Tron background music, sets Spotify… (+4 more)

### Community 32 - "_BrowserSession"
Cohesion: 0.05
Nodes (23): browser_control(), _BrowserSession, _detect_default_browser(), _find_exe_windows(), _find_opera_windows(), _firefox_profile_dir(), _log(), _normalize_url() (+15 more)

### Community 33 - "ClipboardManager"
Cohesion: 0.09
Nodes (17): ClipboardManager, cosine_similarity(), _get_active_window_info(), is_sensitive_content(), Compute cosine similarity between two float vectors., Thread-safe persistent clipboard manager with semantic indexing., Lazily initialize local fastembed model., Compute 384-dimensional vector embedding for text. (+9 more)

### Community 34 - ".test_error_isolation_in_concurrent_tasks"
Cohesion: 0.29
Nodes (5): Verify that an exception in one concurrent task does not break or cancel…, Verify that a batch of tasks run with a concurrency limit of 5 scales sub-…, TestConcurrencyLimiter, execute_task(), safe_run()

### Community 35 - ".__init__"
Cohesion: 0.17
Nodes (7): _Popen, Exception, Turn hold-to-talk on or off. Returns the scope actually achieved., Raised inside the session TaskGroup to force a clean, voluntary reconnect (e.g.…, Session-scoped task: when a voluntary reconnect is requested, raise a signal…, _ReconnectSignal, _OrigPopen

### Community 36 - "audio_devices.py"
Cohesion: 0.12
Nodes (18): configure(), _display_name(), _is_pseudo(), prefetch(), _work(), _query(), _collect(), core/audio_devices.py — pick which microphone and which speakers ALFRED uses.… (+10 more)

### Community 37 - "GraphManager"
Cohesion: 0.11
Nodes (14): GraphManager, Any, Path, Save the graph data to the JSON file atomically., Add an entity node to the graph. Returns True if successful., Add a relationship (edge) between two nodes. Returns True if successful., Apply exponential decay to all temporary nodes. Returns the number of nodes…, Query the knowledge graph for a concept and return connected subgraph up to… (+6 more)

### Community 38 - "datetime"
Cohesion: 0.05
Nodes (51): _clean_header_str(), _extract_body_snippet(), gmail_manager(), _load_gmail_creds(), Any, Gmail Manager Action for ALFRED Mark-LIV. Provides full Gmail connectivity: -…, Send an email using Gmail SMTP SSL., Action entry point for Gmail interaction. (+43 more)

### Community 39 - "CentralizedCache"
Cohesion: 0.06
Nodes (22): CentralizedCache, _canonicalize(), decorator(), wrapper(), Any, Stores value in cache with TTL. Fails open gracefully if storage fails., Deletes a key from cache. Fails open gracefully., Invalidates all keys starting with prefix. Useful for mutation hooks. (+14 more)

### Community 41 - "screen_find.py"
Cohesion: 0.15
Nodes (18): _calculate_similarity(), _get_frame_key(), get_onnx_session(), get_rapid_ocr(), _ocr_grounding(), Any, ndarray, actions/screen_find.py — Local Hybrid Element Grounding for ALFRED. Performs… (+10 more)

### Community 42 - "._build_right_panel"
Cohesion: 0.13
Nodes (5): QHBoxLayout, Read api_keys.json config dict. Returns {} on any error., Style the COGNITIVE TRACE toggle to reflect its on/off state., Show or hide the agent's internal reasoning trace in the chat log., _read_full_config()

### Community 43 - ".__init__"
Cohesion: 0.08
Nodes (14): BiometricFingerprintWidget, _CameraPreview, ClipboardPanel, CRTReconWidget, ImagePopupOverlay, MetricBar, QWidget, Halftone / CRT Dithered Optical Recon Scanner Widget (Screenshot 1: Top-Left… (+6 more)

### Community 44 - "TacticalAudioPlayerWidget"
Cohesion: 0.16
Nodes (4): _EqualizerBarsWidget, Mini animated cyber audio wave visualizer., Bottom-Left Cyber Tactical Audio Player Widget. Styled matching the HUD /…, TacticalAudioPlayerWidget

### Community 45 - "VisemeStream"
Cohesion: 0.13
Nodes (12): collections, coverage(), Text → mouth shape, fused with the audio the avatar is actually speaking. Why…, Reduce any character to a bare Latin letter, or "" if it has none. This is what…, Fraction of the letters in `text` we can reduce to a Latin sound., Split a line of speech into (viseme, duration-weight) pairs. Returns [] for…, Fuses the transcript's shape sequence onto the audio's timing. Thread note:…, Blend audio frames [(level, openness, width)] with the text queue. (+4 more)

### Community 46 - "screen_processor.py"
Cohesion: 0.15
Nodes (19): _base_dir(), _capture_camera(), _cv2_backend(), _detect_camera_index(), _get_camera_index(), _get_os(), _load_config(), _probe_camera() (+11 more)

### Community 47 - "TestProtocolEngine"
Cohesion: 0.12
Nodes (7): Verify that a tool failure halts subsequent steps immediately., Verify voice trigger word resolution (e.g. 'FCC CLAUDE')., Verify protocol_engine TOOL action handler dispatching., Verification Requirement: Define test_protocol in protocols.yaml that opens…, Verify variable interpolation into strings, lists, and dicts., Verify that if any step is blocked by path restrictions, the engine aborts…, TestProtocolEngine

### Community 48 - "TestStreamingMemoryBenchmark"
Cohesion: 0.15
Nodes (7): patch, Verifies streaming CSV to JSON array export in chunks with backpressure.…, Verifies stream_text_metrics processes large text files in 64KB chunks without…, Verifies that actions.file_controller.read_file only buffers up to max_chars…, Returns current process Resident Set Size (RSS) in bytes., Generates a large dataset (150,000 records, ~20MB-30MB on disk) and verifies…, TestStreamingMemoryBenchmark

### Community 49 - "spotify_control.py"
Cohesion: 0.05
Nodes (42): authorize_user(), _get_base_dir(), get_devices(), get_spotify_client(), manage_queue(), _OAuthCallbackHandler, Any, Path (+34 more)

### Community 50 - "server.py"
Cohesion: 0.11
Nodes (17): base64, index(), _ensure_certs(), _local_ip(), _make_uploads_dir(), Path, dashboard/server.py — ALFRED Local HTTP Dashboard Plain HTTP on port 8000 (no…, Return the best LAN-facing IPv4 address, no internet required. (+9 more)

### Community 51 - "CustomizeOverlay"
Cohesion: 0.10
Nodes (9): QPointF, QRectF, CustomizeOverlay, _lbl(), HueWheel, Circular colour picker. The user drags the handle (small white circle) around…, Floating glassmorphic overlay for configuring Assistant Persona, Commander…, Highlight the selected voice pill; dim the rest. (+1 more)

### Community 52 - "computer_settings"
Cohesion: 0.12
Nodes (16): brightness_get(), brightness_set(), computer_settings(), dark_mode(), press_key(), Current brightness 0-100, or None where it cannot be read., Set brightness to an absolute percentage. Only used to restore a value captured…, Current master volume 0-100, or None if this platform will not say. Undo needs… (+8 more)

### Community 53 - "unduck_media_apps"
Cohesion: 0.24
Nodes (7): Restore ducked media applications to their exact original volume levels. :param…, unduck_media_apps(), _pcm_level(), _pcm_visemes(), Stop JARVIS mid-speech: drain queued audio and open mic immediately., Map a block of int16 PCM samples to a 0.0–1.0 loudness level for the HUD…, Slice a PCM block into (level, openness, width) frames, one per 20 ms. Returns…

### Community 54 - "tech_font"
Cohesion: 0.14
Nodes (9): QFont, CapabilitiesOverlay, Floating glassmorphic overlay displaying a categorized directory of everything…, Floating overlay — QR code for instant phone pairing + manual key fallback., Call from any thread when a phone successfully connects., RemoteKeyOverlay, _lbl(), tech_font() (+1 more)

### Community 55 - "._receive_audio"
Cohesion: 0.20
Nodes (6): FunctionResponse, _clean_transcript(), _is_repeat_chunk(), _run_tool_bounded(), Send a captured frame immediately after its tool response. The frame is already…, True if this transcript chunk has already been seen this turn. Guards against…

### Community 56 - "._build_app"
Cohesion: 0.17
Nodes (11): action_ep(), audio_ws(), _auth(), download_file(), list_files(), phone_audio_ws(), _resolve_ws_auth(), _safe_filename() (+3 more)

### Community 57 - "._dispatch_tool"
Cohesion: 0.20
Nodes (6): _is_heavenly_restricted(), _do_shutdown(), Queue a background task and return task metadata immediately., Check if any argument references the restricted Personal-Assistant directory., Summarise the current session in 1-2 sentences and save to long_term.json., Direct action execution from mobile dashboard buttons.

### Community 58 - "find_element"
Cohesion: 0.12
Nodes (14): _screen_find(), find_element(), is_icon_query(), Determine if target query is specifically targeting an icon/non-text element., Main entry point for local hybrid UI element grounding. 1. Executes RapidOCR on…, Action handler called by ALFRED action dispatcher., screen_find(), 8. Full Desktop Control & Operating System Automation (+6 more)

### Community 59 - "time"
Cohesion: 0.14
Nodes (18): Tactical Audio Core Control Action for ALFRED. Controls the tactical HUD's…, actions/clipboard_manager.py — Persistent, Semantically Indexed Clipboard…, Process-level Audio Ducking for ALFRED. Automatically ducks background media…, core/cache.py — Centralized Caching Layer for ALFRED Mark-II. Provides high-…, Push-to-talk — hold a key, speak, release. Why this exists ---------------…, Local wake-word detection for ALFRED ("Hey Jarvis"). Design goals: • ZERO cost…, functools, hashlib (+10 more)

### Community 60 - "LocalLLMManager"
Cohesion: 0.20
Nodes (7): LocalLLMManager, Handle tool calls by executing them and getting final response., Manages local LLM interactions., Set system prompt and available tools., Add message to conversation history., Clear conversation history., Generate response from local LLM.

### Community 61 - "TestBackgroundWorkerPool"
Cohesion: 0.14
Nodes (6): Verify that calling interrupt() sets halt event, immediately stops active…, Verify that _safe_background_announce waits until ALFRED finishes speaking…, Verify queue_background_task is registered in TOOL_DECLARATIONS., Verify that queue_background_task returns immediately (sub-millisecond), and…, Dispatch a mock task and verify voice PTT interaction continues with sub-second…, TestBackgroundWorkerPool

### Community 62 - "ScreenCapturePayload"
Cohesion: 0.20
Nodes (4): Hybrid return payload for screen captures. - Behaves as a 3-tuple `(img_bytes,…, ScreenCapturePayload, _do_stream(), tuple

### Community 63 - "LocalSTTManager"
Cohesion: 0.05
Nodes (25): LocalSTTManager, audio_callback_wrapper(), Process audio bytes for transcription based on engine type., Cancel any pending debounce timer, thread-safe., Reset the FINISH_MS countdown from zero., Timer callback: commit the accumulated sentence to the queue., Immediately commit whatever is in the buffer (+ optional extra word)., Process audio using Vosk streaming STT. Final results are held for FINISH_MS… (+17 more)

### Community 65 - "save_app_icon"
Cohesion: 0.40
Nodes (5): Update App Icon Action for ALFRED Mark-LIV. Switches the application window,…, Updates the main application icon and taskbar badge in realtime., update_app_icon(), Save the chosen app icon setting to config., save_app_icon()

### Community 66 - "LocalTTSManager"
Cohesion: 0.11
Nodes (12): create_local_stt_engine(), Factory function to create a local STT manager., create_local_tts_engine(), LocalTTSManager, Flush any remaining text in buffer., Main loop for processing text queue and speaking., Factory function to create a local TTS manager., Manages local text-to-speech synthesis with streaming capabilities. (+4 more)

### Community 67 - "ALFRED — MARK-IV (Wayne Protocol Edition)"
Cohesion: 0.13
Nodes (14): 10. Real-Time Insignia & Chassis Hot-Swapper, 11. Protocol Engine & Multi-Step Macro Playbooks (`config/protocols.yaml`), 12. Local Hybrid Visual Grounding (RapidOCR + ONNX + Gemini Fallback), 13. Process-Level Audio Ducking & Background Concurrency, 16. System Architecture & File Structure, 18. Configuration Reference (`config/api_keys.json`), 19. Knowledge Graph (`graphify`), 20. Author & Credits (+6 more)

### Community 68 - "_SysMetrics"
Cohesion: 0.13
Nodes (7): Thread-safe speech channel for plugins: lets a plugin ask JARVIS to say…, Thread-safe: ask the run loop to tear down and rebuild the Live session. Called…, Voice picker applied. The voice is baked into the session at connect time, so a…, Microphone or speaker changed. Both streams are opened inside the session…, _nvml_gpu_windows(), Return NVIDIA GPU utilisation % using nvml.dll directly — zero subprocess., _SysMetrics

### Community 69 - "json"
Cohesion: 0.08
Nodes (34): Update Daily Briefing Preferences Action for ALFRED Mark-LIV. Permanently…, Permanently saves daily briefing preferences into long-term memory., update_daily_briefing(), json, _all_entries(), all_entries_for_ui(), _empty_memory(), _entry_value() (+26 more)

### Community 70 - "echo.py"
Cohesion: 0.18
Nodes (6): is_ducked(), Return whether media ducking is currently active., Telling the user's voice apart from our own coming back through the speakers.…, Local Speech-to-Text wrappers for MARK XL. Provides unified interface for…, Speech-to-Text engines for MARK XL. Whisper – offline transcription via faster-…, numpy

### Community 71 - "._apply_name_update"
Cohesion: 0.16
Nodes (10): Persist the chosen Live voice. Unknown names collapse to the default so a bad…, save_voice(), apply_ui_accent(), current_palette(), Applies DOSSIER CRT [A-34] (#8e9bff), VECTOR CRT [WAKU] (#a8ff3e), or BATMAN…, A snapshot of the accent-linked colours currently on class C., LIVE full theme change. Replaces the old palette colours with the new ones in…, Live preview — paints the whole interface the new colour (does NOT write to… (+2 more)

### Community 72 - "WakeWordDetector"
Cohesion: 0.17
Nodes (5): Runs the wake model in a dedicated thread. The mic thread calls feed() with raw…, Load the model and spawn the inference thread. Returns True on success. Safe to…, Called from the mic callback (real-time thread). Must stay cheap and never…, WakeWordDetector, Load the detector once (model loads on first start). Idempotent.

### Community 73 - "get_active_window_info"
Cohesion: 0.20
Nodes (10): get_active_window_context(), get_active_window_info(), _get_linux_window_info(), _get_macos_window_info(), _get_windows_window_info(), Query foreground window handle, title, and process name on Windows., Query active frontmost window on macOS via Quartz or AppleScript fallback., Query active window on Linux via xdotool or wmctrl. (+2 more)

### Community 74 - "daily_brief.py"
Cohesion: 0.15
Nodes (18): daily_brief(), _get_gmail_brief(), _get_greeting(), _get_live_weather(), _get_reminders_brief(), _get_system_vitals(), Daily Brief Action for ALFRED Mark-LIV. Provides the ultimate morning and daily…, Fetch unread emails summary via gmail_manager. (+10 more)

### Community 75 - "create_protocol"
Cohesion: 0.20
Nodes (9): create_protocol(), _do_save(), _ensure_user_protocols_dir(), Save macro definitions to user-specific protocols file., Create a new workflow playbook and save to config/protocols.yaml. Supports…, Ensure the user-specific protocols directory exists., save_protocols(), Verify dynamic workflow creation with confirmation banner. (+1 more)

### Community 76 - "undo.py"
Cohesion: 0.17
Nodes (10): clear(), _Entry, history(), peek(), core/undo.py — one shared undo stack for every action that changes state. WHY…, Forget the stack. Called when the app shuts down so closures holding old file…, Label of the operation that `undo_last()` would reverse, or ''., Most recent first — used by the UI panel and the `undo` tool's list mode. (+2 more)

### Community 77 - "LocalPipelineCoordinator"
Cohesion: 0.09
Nodes (17): LocalPipelineCoordinator, stream_callback(), Coordinates STT → LLM → TTS flow., Set callbacks for UI updates., Log message via callback or print., Set UI state via callback., Start the local pipeline., Stop the local pipeline. (+9 more)

### Community 78 - "._aes_key"
Cohesion: 0.24
Nodes (7): auto_login(), clear_chat_ep(), device_login_ep(), login(), revoke_devices(), _derive_key(), SHA-256(sessionKey‖salt) → 32-byte AES-256 key (microseconds, no PBKDF2 needed).

### Community 79 - "LogWidget"
Cohesion: 0.25
Nodes (3): QTextEdit, LogWidget, Cancel any in-flight typing animation, drain the queue, and clear the display.

### Community 80 - "test_screen_processor.py"
Cohesion: 0.20
Nodes (9): capture_screen(), _capture_screen(), _compress(), format_visual_payload(), Prepares the visual frame payload dictionary for the Gemini Live API…, Captures primary or specified monitor, queries active OS window context,…, Default entry point used by main.py., Unit and integration tests for screen_processor.py window context grounding.… (+1 more)

### Community 81 - "DashboardServer"
Cohesion: 0.16
Nodes (3): DashboardServer, URL for manual browser entry. When HTTPS active, points to alias port (also…, Verify DashboardServer tracks background tasks and exposes them via endpoint.

### Community 82 - "MemoryOverlay"
Cohesion: 0.17
Nodes (8): ConfirmBanner, _HudOverlay, MemoryOverlay, Base for the floating panels placed by hand over the HUD. They are children of…, The gate in front of an action that cannot be taken back. The old confirmation…, Everything ALFRED has stored about you, and when it learned it. Memory used to…, Take every item out of the layout and detach it from the widget tree in this…, Size the panel to its content, re-centre it, and repaint what the old size…

### Community 84 - "PushToTalk"
Cohesion: 0.20
Nodes (5): PushToTalk, Begin watching. Returns the scope actually achieved., Feed a press/release from a Qt shortcut (non-Windows, or no hook)., Calls `on_change(held: bool)` whenever the chord is pressed or released. Start…, global' once a system-wide hook is running, else 'window'.

### Community 85 - "._build_jarvis_icon"
Cohesion: 0.22
Nodes (4): Render an ALFRED tactical icon at 4× resolution and downsample for crisp…, Create a Windows .lnk shortcut WITHOUT launching PowerShell or cmd. Tries…, Resolve the user's REAL desktop directory instead of assuming ~/Desktop, which…, Create a desktop shortcut on Windows / macOS / Linux. Never opens a terminal,…

### Community 86 - "ImagePopupOverlay"
Cohesion: 0.15
Nodes (9): action(), ImagePopupOverlay, QWidget, Handle mouse move for window dragging., Handle mouse release for window dragging., Show the popup centered over the parent widget., Show an image popup overlay., Popup overlay to display an image with a dismiss button. (+1 more)

### Community 87 - "confirm.py"
Cohesion: 0.21
Nodes (11): bind(), _log(), _Pending, core/confirm.py — a confirmation the model cannot forge. THE PROBLEM WITH THE…, Called by the UI when the user presses CONFIRM or CANCEL. Runs the stored…, Wire this module to the HUD. Called once from main.py at startup., Park an irreversible action behind the on-screen gate. Returns the sentence the…, request() (+3 more)

### Community 88 - "os"
Cohesion: 0.17
Nodes (12): Streams CSV records in chunks of 500 records, never loading the full payload…, stream_csv_records(), asyncio, csv, os, tempfile, Memory & Streaming Optimization Benchmark Tests chunked streaming file…, tests/test_cache.py — Comprehensive Test Suite for CentralizedCache. Tests: -… (+4 more)

### Community 89 - "check_path_access"
Cohesion: 0.21
Nodes (8): _normalize(), open_app(), check_path_access(), get_allowed_c_roots(), Path, Validate whether a given path is allowed to be accessed. Returns: (True, "") if…, Return list of permitted roots on C: drive (Desktop and Documents)., 2. Security, Privacy & Defensive Architecture

### Community 90 - "_get_user_protocols_path"
Cohesion: 0.22
Nodes (11): _get_default_protocols_path(), get_protocols_file(), _get_user_name(), _get_user_protocols_dir(), _get_user_protocols_path(), Path, Get the configured user name from api_keys.json., Get the directory for user-specific protocol files. (+3 more)

### Community 91 - "_VolumeSliderPopup"
Cohesion: 0.33
Nodes (3): QFrame, Sleek tactical cyber popup for adjusting master background music volume.…, _VolumeSliderPopup

### Community 92 - "_detect_action"
Cohesion: 0.40
Nodes (5): _detect_action(), _normalise(), Resolve a free-text description to an action name, locally. Returns {"action":…, What to tell the model when nothing matched. Names real actions so its retry…, _suggest()

### Community 93 - "PluginManagerOverlay"
Cohesion: 0.31
Nodes (3): QPushButton, PluginManagerOverlay, Floating overlay — lists discovered plugins with per-plugin ON/OFF toggles.

### Community 94 - "_gemini_grounding"
Cohesion: 0.22
Nodes (9): _capture_screen_image(), _gemini_grounding(), _get_api_key(), _onnx_element_grounding(), Capture current screen into a PIL Image., Run local ONNX element detector (OmniParser-v2 / Florence-2). Returns:…, Fallback visual grounding via Gemini Live / Flash API., Retrieve Gemini API key from api_keys.json or environment. (+1 more)

### Community 95 - "._apply_ptt_shortcut"
Cohesion: 0.29
Nodes (5): qt_sequence(), The same chord as a QKeySequence string., _press(), Bind the chord inside the window when no global hook is available. On macOS and…, Report a windowed press/release to whoever owns the microphone.

### Community 96 - "🎙️ 3. Master Tactical Voice Command Codex & Operational Handbook"
Cohesion: 0.20
Nodes (10): 👁️ 1. Desktop Automation, Screen & Multimodal Vision, ⚙️ 2. Operating System, Hardware Settings & Applications, ⚡ 3. Compound Protocols & Workflow Macros, 🎙️ 3. Master Tactical Voice Command Codex & Operational Handbook, 🧠 4. Memory, History & Universal Reversibility, 📰 5. Intelligence, Briefings, News & Weather, 📱 6. Quantum Mobile Remote & Web Telemetry Uplink, 🎧 7. Spotify AI Agent & Music Streaming (+2 more)

### Community 97 - "ProactiveEngine"
Cohesion: 0.22
Nodes (4): ProactiveEngine, ProactiveEngine 2.0 — context-aware, time-aware, non-repetitive background…, Decides when ALFRED should speak unprompted and builds a context-rich prompt.…, Build a context snapshot for Gemini. Rotates through three focus areas so…

### Community 98 - "TestScreenProcessorWindowContext"
Cohesion: 0.22
Nodes (5): Verifies system falls back to 'App: Unknown' without raising exceptions., Verification Requirement: Verify [WINDOW_CONTEXT] header contains VS Code and…, Verifies that active window query resolves in < 15ms and adheres to schema., Verifies capture_screen() returns valid compressed image and window context., TestScreenProcessorWindowContext

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
Nodes (9): 1. 100% Local & Air-Gapped Offline Execution: Switching from Gemini to Local API, Configuration Template for LM Studio / vLLM (OpenAI-Compatible):, Configuration Template for Ollama:, Configuration Template for OpenRouter API (Frontier Multi-Model Gateway):, Detailed Step-by-Step Guide: How to Switch to a Local API, Gemini Live API vs. Local Offline API Comparison, Step 2: Configure ALFRED's Target Backend in `config/api_keys.json`, Step 3: Launch ALFRED & Verify Connection (+1 more)

### Community 103 - "/email-triage Workflow"
Cohesion: 0.50
Nodes (3): /email-triage Workflow, Objective, Steps

### Community 104 - "_template.py"
Cohesion: 0.50
Nodes (3): Drop-in ALFRED plugin template. Copy this file, rename it (no leading…, parameters: dict of the args Gemini extracted, matching PLUGIN['parameters'].…, run()

### Community 105 - "6. Spotify AI Agent: Dual-Tier Web API & Native Playback Architecture"
Cohesion: 0.22
Nodes (9): 6. Spotify AI Agent: Dual-Tier Web API & Native Playback Architecture, Dual-Tier Control Architecture, Elimination of the Toggle Inversion Bug, High-Performance Client & Anti-Feedback Architecture, Key Capabilities & Default Music Routing, Spotify API & OAuth 2.0 Setup Guide, Step 1: Create a Spotify Developer Application, Step 2: Add Credentials to `config/api_keys.json` (+1 more)

### Community 106 - "_get_base_dir"
Cohesion: 0.67
Nodes (3): _get_api_key(), _get_base_dir(), Path

### Community 107 - "_unduck_linux"
Cohesion: 0.40
Nodes (5): Execute unducking on Windows via pycaw, restoring exact prior volume levels., Execute unducking on Linux via pulsectl., _unduck_linux(), _worker(), _unduck_windows()

### Community 110 - "._decrypt"
Cohesion: 0.40
Nodes (4): command(), ws_ep(), _decrypt_cbc(), Decrypt base64(IV[16] ‖ ciphertext) with AES-256-CBC + PKCS7.

### Community 111 - "_ensure_network_access"
Cohesion: 0.25
Nodes (3): _ensure_network_access(), Cross-platform, best-effort: open port in the OS firewall for LAN access. Runs…, Second HTTPS server on PORT+1 sharing the same app and in-memory state. Chrome…

### Community 116 - "setup.py"
Cohesion: 0.36
Nodes (7): _check_assets(), _check_python(), main(), MARK LIV — one-time setup. Installs the Python dependencies for THIS operating…, Fail immediately and clearly rather than deep inside a pip resolver. A wrong…, The avatar's face is a shipped file; a truncated clone should say so., _run()

### Community 124 - "TestAudioDucker"
Cohesion: 0.29
Nodes (4): patch, Verify that duck_media_apps lowers target media processes by 70% (0.3 factor),…, Verify Linux pulsectl ducking fallback logic., TestAudioDucker

### Community 127 - "format_window_context"
Cohesion: 0.50
Nodes (3): format_window_context(), Format the standard metadata block: [WINDOW_CONTEXT] App: <Name> | Title:…, Verifies exact string formatting requirements.

### Community 128 - "get_push_to_talk_enabled"
Cohesion: 0.29
Nodes (5): chord_label(), Human-readable name of the chord, for the UI and the logs., get_push_to_talk_enabled(), Hold-a-key-to-speak. When on, the mic is closed unless the chord is held., Repaint the push-to-talk row from the saved setting.

### Community 129 - "._listen_audio"
Cohesion: 0.40
Nodes (3): callback(), _open_mic(), True while the speakers may still be finishing our last sentence.

### Community 130 - "subprocess"
Cohesion: 0.32
Nodes (7): _available(), install_for_config(), _pip(), MARK XL — Dependency auto-installer. Called automatically on first launch and…, Return True if the module can be imported (no actual import)., Install all missing packages required by *config*. Blocking — always call from…, subprocess

### Community 131 - "File & Folder Exploration and Notes Directives"
Cohesion: 0.40
Nodes (4): 1. File Opening (`open`), 2. Folder Exploration (`explore`), 3. Dedicated Intel & Notes Terminal (`intel_notes`), File & Folder Exploration and Notes Directives

### Community 132 - "install_and_download"
Cohesion: 0.40
Nodes (6): install_and_download(), is_installed(), is_ready(), True if the openwakeword package is importable (no model check)., True if openwakeword is installed AND its model files are present on disk. This…, One-click setup for the UI button: pip-install openwakeword if missing, then…

### Community 133 - "duck_media_apps"
Cohesion: 0.29
Nodes (7): _duck_linux(), duck_media_apps(), _worker(), _duck_windows(), Execute ducking on Linux via pulsectl., Lower external media application volume (by default to 30%, i.e. ducking by…, Execute ducking on Windows via pycaw.

### Community 134 - "/deep-work Workflow"
Cohesion: 0.50
Nodes (3): /deep-work Workflow, Objective, Steps

### Community 135 - "main.py"
Cohesion: 0.10
Nodes (25): add_monitor(), check_all(), _is_blocked(), list_monitors(), _load(), BackgroundMonitor — user-configured topic watching. Checks DDG news once per…, Run all pending topic checks (once per day per topic). Returns a list of…, remove_monitor() (+17 more)

### Community 136 - "File & Folder Exploration Workflow"
Cohesion: 0.40
Nodes (4): File & Folder Exploration Workflow, Step 1: Target Identification, Step 2: Open File vs Explore Folder, Step 3: Record Intel or Links

### Community 137 - "TTSPlayer"
Cohesion: 0.29
Nodes (3): Wraps any *Engine. Exposes a blocking speak() method meant to be called from a…, Synthesise and play text. BLOCKING – call from a dedicated thread., TTSPlayer

### Community 138 - "test_traceback_benchmark.py"
Cohesion: 0.40
Nodes (4): _parse_traceback(), Performance Benchmark: dev_agent._parse_traceback Tests O(1) hash map lookups…, Measures lookup time across 50,000 mock project files and 500 stack frames., TestTracebackBenchmark

### Community 139 - "get_available_app_icons"
Cohesion: 0.40
Nodes (5): format_icon_display_name(), get_available_app_icons(), Format an icon file name into an authentic, sleek tactical insignia title., Updates the main application window, taskbar icon, and chassis insignia in…, Scan Icons/ and config/ for all available badges/icons.

### Community 140 - "._toggle_sentry_mode"
Cohesion: 0.33
Nodes (3): Toggle continuous visual context (camera stream) monitoring., Thread-safe: start live camera feed in the full HUD area., Thread-safe: stop the live camera feed.

### Community 144 - "audio_core"
Cohesion: 0.50
Nodes (4): audio_core(), Any, Main handler for the Audio Core control action., 5. Dual-Mode Tactical Audio Matrix & Background Sound Engine

### Community 145 - "classify_content_type"
Cohesion: 0.50
Nodes (3): classify_content_type(), Determine category: url, email, json, code, or text., Verify content type heuristic classification.

### Community 146 - "Step 1: Install & Set Up Your Preferred Local LLM Server"
Cohesion: 0.50
Nodes (4): Option A: Ollama (Recommended — Simplest Setup), Option B: LM Studio (Recommended for GUI Users), Option C: vLLM or llama.cpp (High-Throughput / Linux Servers), Step 1: Install & Set Up Your Preferred Local LLM Server

### Community 148 - "17. Quick Start & Installation"
Cohesion: 0.67
Nodes (3): 17. Quick Start & Installation, 1. Prerequisites, 2. Setup & Execution

## Knowledge Gaps
- **52 isolated node(s):** `Purpose`, `Rules`, `Purpose`, `Rules`, `Persona & Demeanor` (+47 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1096 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **26 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MainWindow` connect `MainWindow` to `get_push_to_talk_enabled`, `get_available_app_icons`, `._toggle_sentry_mode`, `ui.py`, `FileDropZone`, `15. Bug Fixes & Stability Updates`, `config_manager.py`, `setter`, `.__init__`, `.closeEvent`, `mono_font`, `._build_right_panel`, `.__init__`, `tech_font`, `._apply_name_update`, `._build_jarvis_icon`, `confirm.py`, `PluginManagerOverlay`, `._apply_ptt_shortcut`?**
  _High betweenness centrality (0.081) - this node is a cross-community bridge._
- **Why does `JarvisLive` connect `JarvisLive` to `._listen_audio`, `main.py`, `system_monitor.py`, `JarvisUI`, `15. Bug Fixes & Stability Updates`, `EchoGuard`, `config_manager.py`, `_tlog`, `.run`, `.__init__`, `VisemeStream`, `unduck_media_apps`, `._receive_audio`, `._dispatch_tool`, `TestBackgroundWorkerPool`, `_SysMetrics`, `json`, `WakeWordDetector`, `DashboardServer`, `PushToTalk`, `os`, `ProactiveEngine`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._
- **Why does `JarvisUI` connect `JarvisUI` to `.__init__`, `main.py`, `._apply_name_update`, `.__init__`, `._toggle_sentry_mode`, `ui.py`, `15. Bug Fixes & Stability Updates`, `JarvisLive`, `setter`, `.__init__`, `PluginManagerOverlay`, `._apply_ptt_shortcut`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Are the 9 inferred relationships involving `JarvisLive` (e.g. with `ProactiveEngine` and `SystemMonitor`) actually correct?**
  _`JarvisLive` has 9 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Purpose`, `Rules`, `Purpose` to the rest of the system?**
  _52 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `game_updater.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05616605616605617 - nodes in this community are weakly interconnected._
- **Should `file_controller.py` be split into smaller, more focused modules?**
  _Cohesion score 0.12329931972789115 - nodes in this community are weakly interconnected._