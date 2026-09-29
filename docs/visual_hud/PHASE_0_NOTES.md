# Phase 0 Recon: Visual HUD v3 (THREAD + DEDUPE + NO LOOP)

## 1. Trace: Who Starts Timers & Touches Players Off-Thread?
- **Call Chain**:
  - `actions/hud_video.py:hud_video()` receives voice/tool command on a worker thread.
  - Line 227 spawns `threading.Thread(target=_resolve_and_play, ...)`.
  - Line 224: `controller.begin_resolve(...)` runs on worker thread -> calls `self._resolve_timer.start()` (`QObject::startTimer: Timers cannot be started from another thread`).
  - Worker thread runs `extract_stream_url()` and calls `controller.on_resolved(ref)` (line 130).
  - In `HudVideoController.on_resolved()`:
    - Line 405: `self._resolve_timer.stop()` runs on worker thread (`QObject::killTimer: Timers cannot be stopped from another thread`).
    - Line 412: `self._on_backend_play(ref, self._muted)` calls `LocalUrlBackend.load(ref)` directly on the worker thread.
  - In `LocalUrlBackend.load()`:
    - Line 87: `self._player.setSource(url)` and `self._player.play()` run on worker thread, initiating internal QtMultimedia timers and FFmpeg decoding contexts off the GUI thread.
- **Graphify Nodes**:
  - `$graphify-root$_actions_hud_video_hud_video` (`actions/hud_video.py:hud_video`)
  - `$graphify-root$_actions_hud_video_resolve_and_play` (`actions/hud_video.py:_resolve_and_play`)
  - `$graphify-root$_core_hud_video_controller_hudvideocontroller_begin_resolve` (`core/hud_video/controller.py:begin_resolve`)
  - `$graphify-root$_core_hud_video_controller_hudvideocontroller_on_resolved` (`core/hud_video/controller.py:on_resolved`)
  - `$graphify-root$_core_hud_video_backends_local_url_localurlbackend_load` (`core/hud_video/backends/local_url.py:load`)

---

## 2. Root Cause Analysis of the Loop
- **Hypothesis 1: Tool result `"Resolving: …"` is fed back to the model, which re-calls `hud_video`.**
  - **CONFIRMED**: `hud_video` returned `f"[Visual HUD] Resolving: {target[:60]}"`. Because this is a non-terminal status, the model treated the action as unfinished and re-invoked `hud_video` in subsequent turns.
- **Hypothesis 2: TTS / toast / video audio is heard by STT and re-transcribed as the same command.**
  - **CONFIRMED**: `hud_video` executed `speak(random.choice(VIDEO_ACK_LINES))` and `speak(f"Playing in Visual HUD: {ref.title}")` while microphone input was active and ungated. The microphone picked up the speaker audio and echoed the command back into STT.
- **Hypothesis 3: A watchdog or retry re-dispatches on halt.**
  - **REJECTED**: No automated watchdog loop exists; re-dispatching is entirely driven by rapid incoming turns from the model/STT.
- **Hypothesis 4: `[halt] Server-side interruption` is the Gemini/phone cancel of a long yt-dlp, which the model treats as failure and retries.**
  - **CONFIRMED**: Server interruption halts the turn, and because the tool result was non-terminal and un-debounced, the model immediately re-issued the same tool call.

---

## 3. Server-side Interruption & Cancellation
- `[halt] Server-side interruption signal received` is triggered when Gemini Live detects audio on the incoming channel.
- `main.py:1426-1430` sets `_bg_halt_event`. However, `actions/hud_video.py` spawned unmanaged `threading.Thread` instances that did not listen to any cancellation tokens. Orphaned `yt-dlp` tasks continued running in the background and dumped obsolete media into `QMediaPlayer`.

---

## 4. In-Flight Policy & Concurrency
- **Existing State**: There is currently no single-flight guard, deduplication, or debounce.
- Firing `hud_video play "new Dune trailer"` 5 times within 2 seconds launched 5 parallel `yt-dlp` subprocesses, causing CPU spikes, network contention, and simultaneous GUI collisions.

---

## 5. Player Ownership & FFmpeg Demuxer Clashes
- `LocalUrlBackend` possesses a single `QMediaPlayer` instance.
- However, when a new `setSource()` was called while a previous stream was actively decoding without a synchronous GUI-thread `stop()` and wait for `StoppedState`, the underlying FFmpeg demuxer thread was interrupted mid-packet. This caused:
  - `[tls] Failed to send close message`
  - `[matroska,webm] Invalid track number 1`

---

## 6. URL Logging & Privacy Leak
- `core/hud_video/backends/youtube.py` extracts raw stream URLs containing signed query parameters (`expire=...`, `sig=...`).
- When FFmpeg opens the stream, `Input #0` diagnostic lines printed to stderr. Furthermore, unstripped URLs were logged in exception handlers.
- Muting `qt.multimedia.ffmpeg` and stripping query parameters in all loggers is required.

---

## 7. Files to Modify in Subsequent Phases
1. `core/hud_video/controller.py` — GUI-thread marshalling, `assert_gui_thread()`, queued signal handlers, and clean stop sequence.
2. `core/hud_video/backends/local_url.py` — GUI-thread assertions and `PLAYER_STOP_WAIT_MS` handling.
3. `core/hud_video/backends/youtube.py` — URL query parameter stripping and host-only logging.
4. `actions/hud_video.py` — Single-flight deduplication (`RESOLVE_DEBOUNCE_MS = 800`, `SAME_TARGET_TTL_S = 30`), terminal tool output, `SPEAK_RESOLVE = False`, STT gating.
5. `main.py` — FFmpeg logging suppression and STT mic gating after video start.
6. Test suites: `tests/hud_video/test_thread_marshal.py`, `tests/hud_video/test_dedupe_singleflight.py`.
