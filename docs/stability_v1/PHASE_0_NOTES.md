# ALFRED-MK-V: Uplink Stability + Media Controls Fix — Phase 0 Recon Notes

## Overview
Comprehensive architectural and root-cause analysis for the 7 bugs in scope across uplink websocket transport, off-thread Qt timers, chat history sync, TTS audio output, Spotify controls, Sys audio play/pause symmetry, and screenshot delivery to uplink.

---

## 1. Transport Reset (ConnectionResetError WinError 10054)
- **Component & Sockets**:
  - Windows Proactor Event Loop (`_ProactorBasePipeTransport._call_connection_lost`) handling WebSocket connections in `dashboard/server.py` (`/ws`, `/ws/audio`, `/ws/phone-audio`).
  - Occurs when a client browser tab closes, refreshes, or drops network connectivity abruptly without a clean TCP FIN handshake.
- **Event Loop Context**:
  - In `main.py`, the primary asyncio event loop is instantiated on a background daemon thread (`runner`) via `asyncio.run(alfred.run())`.
  - The Qt main application runs on the main thread via `ui.root.mainloop()`.
- **Root Cause**:
  - `dashboard/server.py` endpoint receive loops only caught `WebSocketDisconnect`, allowing `ConnectionResetError` / `ConnectionAbortedError` / `OSError` to propagate to the Proactor transport's default exception handler.
  - The default asyncio Proactor exception handler on Windows prints full tracebacks for benign remote TCP resets (`WinError 10054`).
- **Target Files & Functions**:
  - `main.py`: Install custom loop exception handler on `self._loop` (`_silence_proactor_connection_lost`).
  - `dashboard/server.py`: `ws_ep`, `audio_ws`, `phone_audio_ws`, `broadcast`.
- **Graphify Nodes**: `$graphify-root$_main_py`, `$graphify-root$_dashboard_server_py`.

---

## 2. Off-Thread Timer (QObject::startTimer)
- **Call Sites Correlating with Cadence & Background Workers**:
  - `ui.py` `HudCanvas.set_sentry_snapshot()` / `_start_animations()`: Calls `self._tmr.start(16)` from sentry background monitor threads (`core/sentry/`).
  - `ui.py` `TronScoreBackgroundPlayer`: `play()`, `pause()`, `set_ducked()`, `set_base_volume()` start/stop `self._fade_timer` (a `QTimer`) and call `self._player.pause()`/`play()` from worker threads (`actions/audio_core.py`, `actions/spotify_control.py`, media arbiter callbacks).
  - `ui.py` `LogWidget.append_log()`: `_enqueue` calls `self._next()` which calls `self._tmr.start(6)` without guaranteeing execution on the GUI thread if `_sig` is emitted synchronously.
- **Root Cause**:
  - Qt timers (`QTimer`) can only be started or stopped from the thread where the `QObject` lives (the main GUI thread).
- **Target Files & Functions**:
  - `ui.py`: `HudCanvas`, `TronScoreBackgroundPlayer`, `LogWidget`, `MainWindow`.
  - Add `assert_gui_thread()` helper in `core/gui_thread.py` or `ui.py` and marshal all worker-to-UI timer operations via Qt signals (`pyqtSignal`) with `Qt.ConnectionType.QueuedConnection`.
- **Graphify Nodes**: `$graphify-root$_ui_py_hudcanvas`, `$graphify-root$_ui_py_tronscorebackgroundplayer`, `$graphify-root$_ui_py_logwidget`.

---

## 3. Chat History on Uplink Connect
- **History Storage & Synchronization**:
  - History is stored in `dashboard/server.py` in `self._history: list[dict]`.
  - On `/ws` connection, `ws_ep` currently iterates `self._history[-50:]` and sends individual JSON entries.
- **Root Cause**:
  - Sending items one by one sequentially over streaming websocket during handshake causes perceptible rendering delay on slower connections.
  - History length was hardcoded to 50 items and did not include pre-existing session logs from `main.py` if the server restarted or if previous interactions occurred before dashboard init.
- **Target Files & Functions**:
  - `dashboard/server.py`: Add named constant `UPLINK_HISTORY_N = 100`, send initial history in a structured `"history"` packet during handshake.
  - `dashboard/static/app.html`: Handle `"history"` event in one batch render.
- **Graphify Nodes**: `$graphify-root$_dashboard_server_py_ws_ep`, `dashboard/static/app.html`.

---

## 4. TTS Silent Root Cause
- **Audio Output Pipeline**:
  - In `main.py`, `_speak_local` is hardcoded to `win32com.client.Dispatch("SAPI.SpVoice")` inside a silent `try...except: pass` block.
  - In `main.py`, `speak(text)` only sent prompts to `self.session` (Gemini Live) if active, dropping speech entirely when Gemini is not connected, in local LLM mode, or when actions execute.
  - In `core/tts/engine_default.py`, output uses `sounddevice.play()`. If the audio device was busy or misconfigured, it failed silently.
- **Root Cause**:
  - Disconnect between `main.py` speech methods and the `core.tts` engine catalog (`EdgeTTSEngine`, `KokoroTTSEngine`, `ElevenLabsTTSEngine`, `EngineJarvis`).
  - Lack of startup self-check to test audio output initialization.
- **Target Files & Functions**:
  - `main.py`: `speak()`, `_speak_local()`, `run_local()`.
  - `core/tts/engine_default.py` & `core/local_ttt.py`: Provide unified audio playback with fallback and startup self-test.
- **Graphify Nodes**: `$graphify-root$_main_py_speak`, `$graphify-root$_core_tts_engine_default_py`.

---

## 5. Spotify Button Binding
- **Execution Route**:
  - Button in `dashboard/static/app.html` calls `executeTacticalAction('spotify')`.
  - Uplink sends `{"type": "action", "action": "spotify", "params": {}}` to `main.py` `_on_dashboard_action`.
- **Root Cause**:
  - `main.py` line 3021 called `control_playback(sub, player=self.ui)`. `control_playback` in `actions/spotify_control.py` does not accept a `player` keyword argument, causing an immediate `TypeError`.
  - If Spotify credentials in `config/api_keys.json` are not authenticated, `control_playback` returned `False` without user-facing feedback.
- **Target Files & Functions**:
  - `main.py`: `_on_dashboard_action`.
  - `actions/spotify_control.py`: `control_playback`.
- **Graphify Nodes**: `$graphify-root$_main_py__on_dashboard_action`, `$graphify-root$_actions_spotify_control_py`.

---

## 6. Sys Audio Pause / Resume Symmetry
- **Audio Engine Mechanics**:
  - `ui.py` `TronScoreBackgroundPlayer`: Manages `QMediaPlayer` (`self._player`) and `QAudioOutput` (`self._audio`).
  - `actions/audio_core.py` handles "pause", "resume", "toggle", "volume".
- **Root Cause**:
  - `pause_audio_core()` called `_bg_music.pause_core()` from worker threads without Qt thread marshaling.
  - `_fade_timer` and `QMediaPlayer` calls from non-GUI threads fail silently on Qt.
  - Toggle button state in `TacticalAudioPlayerWidget` desynchronized from actual player state.
- **Target Files & Functions**:
  - `ui.py`: `TronScoreBackgroundPlayer`, `TacticalAudioPlayerWidget`, `MainWindow`.
  - `actions/audio_core.py`: `audio_core`.
- **Graphify Nodes**: `$graphify-root$_ui_py_tronscorebackgroundplayer`, `$graphify-root$_actions_audio_core_py`.

---

## 7. Screenshot Capture & Uplink Delivery
- **Existing Capture Facilities**:
  - `actions.screen_processor.capture_screen(monitor=1)` captures desktop frame and active window metadata via `mss` and PIL.
  - `dashboard/server.py` `/uploads/{filename}` serves files from `UPLOADS_DIR`.
  - `dashboard/static/app.html` already has `_onFileReceived` supporting `is_screenshot: true` with inline image rendering and download links.
- **Target Flow**:
  - When "take a screenshot" / action "screenshot" is triggered:
    1. Capture screen using `actions.screen_processor.capture_screen(monitor=1)`.
    2. Save as PNG (`SCREENSHOT_FORMAT = "png"`) in `UPLOADS_DIR / f"screenshot_{timestamp}.png"`.
    3. Broadcast `{"type": "file", "name": f"screenshot_{timestamp}.png", "size": size, "is_screenshot": True}`.
- **Target Files & Functions**:
  - `main.py`: `_on_dashboard_action`, `_action_registry`.
  - `actions/computer_control.py` & `dashboard/server.py`.
- **Graphify Nodes**: `$graphify-root$_actions_screen_processor_py`, `$graphify-root$_dashboard_server_py`.

---

## Exact Files to Touch Across Phases

| Phase | Bug Area | Files to Touch | Functions / Components |
|-------|----------|----------------|------------------------|
| **P1** | Uplink Transport Hardening | `main.py`, `dashboard/server.py` | `_silence_proactor_connection_lost`, `ws_ep`, `audio_ws`, `broadcast` |
| **P2** | Off-Thread QTimers | `ui.py`, `core/gui_thread.py` | `HudCanvas`, `TronScoreBackgroundPlayer`, `LogWidget`, `MainWindow` |
| **P3** | Chat History on Connect | `dashboard/server.py`, `dashboard/static/app.html` | `ws_ep`, `_history`, `_onHistoryReceived` |
| **P4** | TTS Silent Fix | `main.py`, `core/tts/engine_default.py`, `core/local_ttt.py` | `speak()`, `_speak_local()`, `_play_np()`, startup self-test |
| **P5** | Spotify Button | `main.py`, `actions/spotify_control.py` | `_on_dashboard_action`, `control_playback`, error toasts |
| **P6** | Sys Audio Pause | `ui.py`, `actions/audio_core.py` | `pause_audio_core()`, `resume_audio_core()`, `toggle_play()`, GUI thread marshaling |
| **P7** | Screenshot → Uplink File | `main.py`, `actions/computer_control.py`, `dashboard/server.py` | `screenshot` action handler, `UPLOADS_DIR` file broadcast |
| **P8** | Tests & Verification | `tests/`, `docs/stability_v1/VERIFY.md` | Unit test suite & checklist |
