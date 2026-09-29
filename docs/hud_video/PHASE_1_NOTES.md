# PHASE 1 — Surface + Controller Skeleton: Implementation Notes

**Date:** 2026-09-29
**Graphify delta:** 4410 nodes, 8904 edges (was 4160/8430). 16 new files indexed.

---

## Graphify Nodes Referenced

| Node | File | Role |
|---|---|---|
| `MainWindow` (Community 0, 134 edges) | `ui.py:7858` | Host for `_hud_cam_stack` |
| `HudCanvas` (Community 20) | `ui.py:1205` | Slot 0 of the stack (unchanged) |
| `_hud_cam_stack` | `ui.py:8017` | `QStackedWidget`; slot 2 = video |
| `TronScoreBackgroundPlayer` (Community 55) | `ui.py:177` | Duck target on unmute |
| `JarvisUI` (Community 108) | `ui.py:11172` | Proxy facade; now has `hud_video_controller` |
| `HudVideoController` (new) | `core/hud_video/controller.py` | State machine |
| `HudVideoSurface` (new) | `core/hud_video/surface.py` | Qt widget, stack slot 2 |
| `LocalUrlBackend` (new) | `core/hud_video/backends/local_url.py` | QMediaPlayer adapter |

---

## Architecture Implemented

### State Machine (controller.py)

```
IDLE ──begin_resolve()──► RESOLVING ──on_resolved()──► LOADING ──on_backend_ready()──► PLAYING
                                                                        │
                                                                   ──pause()──► PAUSED
                                                                   ──stop()──► IDLE
                          ──signal_error()──► ERROR ──(timer 3.5s)──► IDLE
```

All timers:
- `VIDEO_RESOLVE_TIMEOUT_S = 30` — guard against hanging RESOLVING
- `VIDEO_ERROR_DISPLAY_S = 3.5` — ERROR flash duration
- `VIDEO_IDLE_UNLOAD_S = 300` — auto-stop after 5 min paused background

### Stack Slot Assignment (ui.py:8017)

```
_hud_cam_stack (QStackedWidget):
  [0] HudCanvas      — avatar/globe (unchanged)
  [1] _cam_cont      — live camera (unchanged)
  [2] HudVideoSurface — NEW: video player with loading chrome
```

`_on_hud_video_show()` → `setCurrentIndex(2)`
`_on_hud_video_hide()` → `setCurrentIndex(0)`

Both slots fire via `_hud_video_show_sig` / `_hud_video_hide_sig` (thread-safe signals).

### Surface Panels (surface.py)

```
HudVideoSurface (QWidget)
└── _content_stack (QStackedWidget)
    [0] _loading_panel: _SpinnerWidget + _status_lbl
    [1] _video_widget: QVideoWidget (fills when PLAYING)
    [2] _error_panel: _error_lbl (red flash)
```

Floating overlays (positioned in `resizeEvent`):
- `_mute_badge` — top-right "MUTED" badge
- `_pause_overlay` — centre "⏸ PAUSED" label

### Backend Wire-up (_init_hud_video, ui.py)

```python
ctrl.wire(
    on_show_surface  = lambda: self._hud_video_show_sig.emit(),
    on_hide_surface  = lambda: self._hud_video_hide_sig.emit(),
    on_backend_play  = lambda ref, muted: (backend.load(ref) or backend.set_muted(muted)),
    on_backend_pause = backend.pause,
    on_backend_resume= backend.play,
    on_backend_stop  = backend.stop,
    ...
)
backend.on_ready.connect(ctrl.on_backend_ready)
backend.on_error.connect(lambda msg: ctrl.signal_error(msg[:60]))
backend.on_ended.connect(ctrl.stop)
surf.stop_requested.connect(ctrl.stop)
```

### Controller exposure for action bridge

```python
# In _init_hud_video:
import main as _main_module
_main_module._hud_video_controller = ctrl
```

Action handler (`actions/hud_video.py:_get_controller`) picks this up:
```python
import main as _main
return getattr(_main, "_hud_video_controller", None)
```

---

## Minimise / Restore Policy (Implemented)

`MainWindow.changeEvent` (ui.py:11044) now also notifies the video controller:
```python
if self.isMinimized():
    self._hud_video_controller.on_minimise()  # pause
else:
    self._hud_video_controller.on_restore()   # resume
```

Policy: **pause on minimise, resume on restore**.
After `VIDEO_IDLE_UNLOAD_S` background, auto-stop and unload.

---

## Early Ack TTS Pattern (hud_video.py)

```python
# In hud_video() action handler:
if speak:
    speak(random.choice(VIDEO_ACK_LINES))          # TTS fires immediately
controller.begin_resolve(f"Searching: {target}…")  # loading chrome shows
threading.Thread(target=_resolve_and_play, ...).start()  # off-thread
```

First pixel → TTS ack gap: ~0 (both happen before resolve runs).

---

## Phase 3 Stop Point: yt-dlp

- **Decision:** User approved `pip install yt-dlp`.
- **Status:** Installed. Added to `requirements.txt`.
- `core/hud_video/backends/youtube.py` now activates: `extract_stream_url(watch_url)`
  calls `yt_dlp` module, returns CDN URL, which `LocalUrlBackend.load()` plays.

---

## Test Results

```
Ran 32 tests in 0.070s
OK
```

Tests cover:
- All 10 locus phrases detected
- All negative cases (bare "play Starboy", "play Dune trailer")
- All 11 transport commands
- YouTube URL detection + video ID extraction
- Media extension fast-path
- Path guard rejection (Heavenly Restriction)

---

## Files Created / Modified

| File | Status |
|---|---|
| `core/hud_video/__init__.py` | New |
| `core/hud_video/intent.py` | New |
| `core/hud_video/controller.py` | New |
| `core/hud_video/resolve.py` | New |
| `core/hud_video/surface.py` | New |
| `core/hud_video/backends/__init__.py` | New |
| `core/hud_video/backends/local_url.py` | New |
| `core/hud_video/backends/youtube.py` | New |
| `actions/hud_video.py` | New |
| `tests/hud_video/test_intent.py` | New |
| `ui.py` | Modified: QVideoWidget import, signals, `_init_hud_video`, `changeEvent` |
| `requirements.txt` | Modified: `yt-dlp>=2024.1,<2027` |
| `docs/hud_video/PHASE_0_NOTES.md` | New |

---

## Acceptance Checklist (Phase 1)

- [x] State machine: IDLE → RESOLVING → LOADING → PLAYING → PAUSED → ERROR → IDLE
- [x] `HudVideoSurface` widget lives in `_hud_cam_stack` slot 2
- [x] When IDLE, `HudCanvas` (slot 0) unchanged — bit-identical behaviour
- [x] Loading UI: spinner + status line in theme palette
- [x] API: `play()`, `pause()`, `resume()`, `stop()`, `set_muted()`, `toggle_mute()`
- [x] Signals: `state_changed`, `ready`, `failed`
- [x] Stop → restore avatar (`setCurrentIndex(0)`)
- [x] Minimise policy: pause on minimise, resume on restore
- [x] 32 unit tests pass (intent, transport, resolve, path_guard)
- [x] ui.py syntax clean
- [x] graphify updated: 4410 nodes

---

## Remaining Phases

- **Phase 2:** Resolve pipeline integration (YouTube/direct URL/local — unit tested but not E2E wired to Phase 3 stream extraction yet)
- **Phase 3:** yt-dlp installed; `backends/youtube.py` ready to activate
- **Phase 4:** `hud_video` TOOL schema done; prompt.txt update + transport voice routing
- **Phase 5:** Theme switch live test, memory/CPU idle verification
- **Phase 6:** Full test suite, VERIFY.md, README update
