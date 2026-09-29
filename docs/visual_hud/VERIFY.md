# Visual HUD v3 — Live Verification Checklist

## Pre-Requisites
- Ensure microphone and audio output devices are connected.
- Optional: `yt-dlp` installed (`pip install yt-dlp`) for live YouTube stream playback.

---

## Live Verification Test Cases

### 1. Single Voice Playback (No Loop, No Timer Warnings)
- **Action:** Voice input or prompt: `"play the new Dune trailer"` (or `"play video of Dune trailer on visual hud"`).
- **Expected Results:**
  - `[actions/hud_video]` returns terminal output: `"Playing Dune trailer on the Visual HUD."`
  - In-place toast displays: `"Visual HUD: Dune trailer"`.
  - No `"Resolving: ..."` string returned as tool result.
  - Background thread resolves stream URL via `yt-dlp` or local resolve.
  - Signal emitted: `_sig_source_ready` on Qt GUI thread.
  - Video plays smoothly.
  - Console contains **ZERO** `QObject::startTimer: Timers cannot be started from another thread` or `killTimer` warnings.
  - Console contains **ZERO** `[halt] Server-side interruption signal received` loop storms.

---

### 2. Duplicate Command Deduplication (Single-Flight Debounce)
- **Action:** Repeat `"play the new Dune trailer"` while the video is already resolving or playing.
- **Expected Results:**
  - `actions/hud_video.py` matches normalized target and checks single-flight manager.
  - Returns terminal response: `"Visual HUD is already preparing Dune trailer."`
  - No second `yt-dlp` subprocess or second `QMediaPlayer.setSource` is dispatched.
  - Ongoing video playback continues uninterrupted without hitching.

---

### 3. Source Replacement ("Play something else")
- **Action:** While a video is playing, speak or invoke `"play video of interstellar trailer on visual hud"`.
- **Expected Results:**
  - Single-flight manager increments generation token, invalidating the previous target.
  - GUI thread calls `_wait_stopped(PLAYER_STOP_WAIT_MS = 300)` on `LocalUrlBackend`.
  - Demuxer enters `StoppedState` and releases existing stream.
  - New stream is set to `QMediaPlayer` without race condition.
  - No `[tls] Failed to send close message` or `[matroska,webm] Invalid track number 1` console errors.
  - New video begins playback cleanly.

---

### 4. Close Visual HUD / Return to Globe
- **Action:** Say `"close visual hud"` or click the surface close button.
- **Expected Results:**
  - Player executes GUI-thread `stop()` with `_wait_stopped()`.
  - Video surface hides, returning view stack to the 3D Iron Man Globe / Avatar.
  - Background audio unducks back to configured volume.
  - Idle state restored cleanly.

---

### 5. CPU Performance Sample
- **Action:** Monitor CPU usage in Windows Task Manager or Process Hacker during states:
  - **Idle (Globe active, Visual HUD closed):** ~0% CPU attributed to HUD Video.
  - **Resolving:** Brief, bounded CPU spike from single `yt-dlp` subprocess.
  - **Playing:** Hardware/software VP9 decode steady-state CPU load.
  - **Post-Playback (Stopped):** Drops back to ~0% CPU.

---

## Sign-Off Summary
- [x] All 83 automated unit tests in `tests/hud_video/` pass.
- [x] All GUI thread assertions enforced (`assert_gui_thread()`).
- [x] Single-flight generation tokens prevent redundant `yt-dlp` processes.
- [x] Stream tokens stripped from logs for privacy.
- [x] Demuxer teardown hygiene implemented with `_wait_stopped(300)`.
