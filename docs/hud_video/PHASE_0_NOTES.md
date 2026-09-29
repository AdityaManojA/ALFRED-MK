# PHASE 0 RECONNAISSANCE NOTES — HUD VIDEO SURFACE

**Date:** 2026-09-29
**Scope:** Pure recon, zero code changes.
**Files read:** `ui.py`, `main.py`, `core/path_guard.py`, `requirements.txt`,
`actions/youtube_video.py`, `core/prompt.txt`, `graphify-out/GRAPH_REPORT.md`

---

## 1. Avatar / Globe Host — Layout & Lifecycle

### Graphify nodes referenced
- `HudCanvas` (Community 20) — god-node-adjacent, 25 edges
- `MainWindow` (Community 0) — 134 edges, primary god node
- `JarvisUI` (Community 108) — 56 edges, thread-safe facade over MainWindow
- `TronScoreBackgroundPlayer` (Community 55) — 39 edges
- `_hud_cam_stack` — inferred from `MainWindow`; see ui.py:8017

### `HudCanvas` (ui.py:1205)
The centrepiece of the HUD is a **custom `QWidget`** subclass that does everything
via `QPainter` in software: animated 3-D vector globe, oscilloscope waveforms,
scanline overlay, hex matrix stream, arc reactor. No OpenGL, no GPU.

Key attributes:
```
hud_style = "reactive"
_live_amp / _amp_disp    — audio reactivity written from audio threads
_visemes                 — (frames, t0, hop) schedule for lip-sync
_static_layers           — per-size/theme QPixmap cache (expensive)
_particles               — 54 cyber-particles, no per-frame alloc
```

`push_visemes(frames, hop, at)` is called from `JarvisUI.push_visemes` ->
`MainWindow.hud.push_visemes`.

**What "avatar" means in this codebase:** The globe/waveform/reactor on `HudCanvas`.
There is no separate avatar widget — all is custom `paintEvent` code in one `QWidget`.

### `_hud_cam_stack` (ui.py:8017)
`MainWindow` already uses a `QStackedWidget` with **two slots**:
- Index 0 -> `self.hud` (animated `HudCanvas`)
- Index 1 -> `_cam_cont` (live camera `QLabel`)

Switch driven by `_on_cam_stream(start: bool)` (ui.py:8128):
```python
def _on_cam_stream(self, start: bool) -> None:
    if start:
        self._hud_cam_stack.setCurrentIndex(1)
    else:
        self._hud_cam_stack.setCurrentIndex(0)
        self._cam_live_lbl.clear()
```

**Implication:** We add a **third slot (index 2)** for the video surface.
The camera pattern is the proven blueprint.

### Minimize / theme / reconfigure behaviour
- **Minimise:** `changeEvent` (ui.py:11044) fires `_hud_overlay.begin_minimize_session()`.
  `_hud_cam_stack` hides with the window — no teardown. Policy: **pause on minimise**.
- **Theme change:** `HudCanvas` re-reads `class C` tokens each `paintEvent`. Video
  surface only needs to re-apply CSS border from `C.PRI`.
- **Fullscreen (F11):** Splitter and stack stretch naturally (proven by camera path).
- **Reconfigure:** `SetupOverlay` is a floating overlay — does not affect the stack.

---

## 2. Existing Media Paths — Reuse Analysis

### `QMediaPlayer` / `QAudioOutput` — ALREADY IN USE
`TronScoreBackgroundPlayer` (ui.py:177) imports and uses it:
```python
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput  # ui.py:50
self._player = QMediaPlayer(self)                           # ui.py:323
```
`PyQt6.QtMultimedia` is **confirmed present** (tested at runtime).

### `PyQt6.QtWebEngineWidgets` — NOT INSTALLED
```
ModuleNotFoundError: No module named 'PyQt6.QtWebEngineWidgets'
```
Not in `requirements.txt`. ~100 MB Chromium engine. Requires user approval to add.

### Existing `youtube_video.py` (actions/youtube_video.py)
Already present. Provides:
- `_scrape_first_video_url(query)` — returns first non-Shorts YouTube watch URL
- `_extract_video_id(url)` — regex extractor for video IDs
- `_is_valid_youtube_url(url)` — bool check
- `_scrape_video_info(video_id)` — title, channel, views, duration

Current `play` action **opens in system browser** via `subprocess.Popen`.
No stream-URL extraction exists (no yt-dlp, no pytube).

### Audio Core (`TronScoreBackgroundPlayer`)
Has `set_ducked(bool)` for speech ducking. Reuse: when video plays with sound,
call `self._bg_music.set_ducked(True)`; on mute/stop, call `set_ducked(False)`.

### No VLC, mpv, or other heavy media runtimes present.

---

## 3. Voice -> Action Routing Today

### System prompt (core/prompt.txt:82-90)
```
- "Play a song" / "play music" / "play [artist/track]" -> call spotify_control
  ONCE with action='play' and query=<name>. Do NOT target YouTube unless the user
  explicitly asks for a video.
- "Pause/resume/play/stop audio core" / "tron music" -> call audio_core ONCE.
```

### Tool dispatch (main.py:1965-1972)
```python
elif self._action_registry.has(name):
    _ctx = {"player": self.ui, "speak": self.speak, ...}
    r = await loop.run_in_executor(None, lambda: self._action_registry.run(name, args, _ctx))
```
Actions discovered from `actions/*.py` via `core/action_loader.py`.
`speak` callback posts to Gemini Live — fires TTS immediately, before tool result.

### Current `youtube_video` TOOL schema
- `action`: play | summarize | get_info | trending
- `query`: search query
- No `in_app_player` field; `play` opens system browser.

### Insert point for locus gate
New action `hud_video` in `actions/hud_video.py`. Deterministic `intent.py` locus
check is the server-side gate — model cannot start HUD video on bare "play X".

---

## 4. Reusable Helpers for Resolve

| Helper | Location | Usage |
|---|---|---|
| `_scrape_first_video_url(query)` | `actions/youtube_video.py:76` | YouTube search backend |
| `_extract_video_id(url)` | `actions/youtube_video.py:108` | Video ID extraction |
| `_is_valid_youtube_url(url)` | `actions/youtube_video.py:115` | URL type check |
| `_scrape_video_info(video_id)` | `actions/youtube_video.py:226` | Title for `PlayableRef.title` |
| `web_search` action | `actions/web_search.py` | Fallback search |
| `check_path_access(path)` | `core/path_guard.py:111` | Local file validation |

**YouTube stream resolution:** No yt-dlp present.
- Option A: `yt-dlp` subprocess — not in requirements; **STOP in Phase 3, ask user**.
- Option B: `PyQt6-WebEngine` embed — not installed; heavy (~100 MB).
- Decision: `yt-dlp` preferred (no C libs, pure Python wheels).

---

## 5. TTS Entry Point — Early Ack Pattern

`speak` callback (main.py:1606):
```python
def speak(self, text: str):
    asyncio.run_coroutine_threadsafe(
        self.session.send_client_content(
            turns={"role": "user", "parts": [{"text": text}]},
            turn_complete=True
        ),
        self._loop
    )
```
Available immediately, before any IO. Pattern already used at youtube_video.py:329:
```python
if speak:
    speak("Fetching the transcript now, sir. One moment.")
```
We follow this: `speak("Coming up, sir.")` fires while resolve runs off-thread.

---

## 6. HUD Software Renderer Constraints & Backend Decision

### Constraint
`requirements.txt:10-12`: avatar rendered in software with QPainter, no OpenGL, no GPU.
`HudCanvas` uses `WA_OpaquePaintEvent`. OpenGL-based overlays would conflict.

### Backend matrix

| Option | Status | CPU idle | Mute | Windows |
|---|---|---|---|---|
| `QVideoWidget` + `QMediaPlayer` | **Available** | ~0 when stopped | vol=0 | Yes |
| `QGraphicsVideoItem` | Available | ~0 when stopped | vol=0 | Yes |
| `QWebEngineView` YouTube embed | NOT installed | moderate | JS mute | needs install |
| yt-dlp stream -> `QMediaPlayer` | yt-dlp absent; stop+ask | ~0 when stopped | vol=0 | Yes after install |

### Chosen: `QVideoWidget` + `QMediaPlayer`
- `PyQt6.QtMultimedia` already imported at ui.py:50.
- `QVideoWidget` is a plain `QWidget` — works with software painter + `QStackedWidget`.
- Plays local files, HTTP direct URLs (mp4/webm/mkv/m3u8).
- YouTube: `yt-dlp --get-url <watch_url>` -> CDN URL -> `QMediaPlayer`.

### Platform notes
- macOS: AVFoundation backend. Same code path.
- Linux: GStreamer. Works with gst-plugins-good/bad installed.

---

## 7. Proposed Module Layout

```
core/hud_video/
  __init__.py       # exports HudVideoController, PlayableRef
  controller.py     # state machine: IDLE/RESOLVING/LOADING/PLAYING/PAUSED/ERROR
  surface.py        # HudVideoSurface(QWidget): QVideoWidget + loading chrome
  resolve.py        # URL / path / search -> PlayableRef
  intent.py         # locus-phrase detection + payload strip
  backends/
    __init__.py     # BackendBase ABC
    local_url.py    # QMediaPlayer backend (local + direct URLs)
    youtube.py      # yt-dlp -> stream URL -> local_url backend

actions/
  hud_video.py      # TOOL schema + early-ack handler
```

### `PlayableRef` dataclass
```python
@dataclass
class PlayableRef:
    kind: Literal["youtube", "direct_url", "local_file"]
    uri: str               # playable URI (stream URL for YouTube)
    title: str             # display + TTS
    thumb_url: str | None = None
    source_query: str | None = None  # query, locus already stripped
```

### Controller state machine
```
IDLE -> RESOLVING -> LOADING -> PLAYING -> PAUSED -> IDLE
                                    |
                                    v
                                  ERROR -> IDLE
```
`VIDEO_IDLE_UNLOAD_S = 300` — stop after 5 min background.

---

## 8. Stack Slot Assignment

Existing `_hud_cam_stack` (ui.py:8017) gains a third slot:
- Index 0 -> `HudCanvas` (unchanged)
- Index 1 -> `_cam_cont` (live camera, unchanged)
- **Index 2 -> `HudVideoSurface`** (new)

Switching in:  `self._hud_cam_stack.setCurrentIndex(2)`
Switching out: `self._hud_cam_stack.setCurrentIndex(0)`

Zero risk to existing camera and avatar paths.

---

## 9. Locus-Phrase Routing Design

```python
# core/hud_video/intent.py
VIDEO_LOCUS_PHRASES = (
    "in the app", "in app",
    "in the player", "in player", "on the player",
    "in the hud", "on the hud", "in hud",
    "on the screen", "on screen",
    "in the batcomputer", "on the batcomputer",
)
PLAY_INTENT_WORDS = ("play", "watch", "show", "put", "stream", "load")
```

"on screen" included — rare in Spotify context, no collision expected.

"play this in player" with no URL context: check clipboard for URL first; if
no URL found, one-shot clarify "What would you like me to play, sir?"

---

## 10. Open Questions / Stop Points

| # | Question | Decision |
|---|---|---|
| 1 | **yt-dlp** — needed for YouTube playback in HUD | **STOP in Phase 3**. Ask user before install. |
| 2 | **PyQt6-WebEngine** as YouTube alternative | Not recommended (100 MB). Prefer yt-dlp. |
| 3 | "play this in player" with no URL context | One-shot clarify. |
| 4 | Pause on minimise vs keep playing | **Pause on minimise**, resume on restore. |
| 5 | "pause" ambiguity when video active vs Spotify | Video wins when controller state is PLAYING/PAUSED. |

---

## 11. System Prompt Addition (Phase 4)

```
HUD video: use the hud_video tool ONLY when the user says play/watch/show/stream
… in the app / in player / in the hud / on screen (or listed aliases).
Bare "play X" without those phrases is always music (spotify_control). Never
read a URL aloud — use the video title only.
```

---

## 12. Phase Readiness Checklist

- [x] Avatar slot: `_hud_cam_stack` index 0 = HudCanvas; index 2 = new video surface
- [x] `QMediaPlayer` confirmed available (already imported at ui.py:50)
- [x] `QWebEngineView` confirmed NOT installed
- [x] Early ack TTS pattern confirmed (`speak()` callback, main.py:1606)
- [x] `path_guard.check_path_access` confirmed for local files
- [x] `youtube_video.py` helpers confirmed reusable
- [x] Locus phrases defined; no Spotify collision expected
- [x] Module layout proposed
- [x] Stop points identified: yt-dlp (Phase 3), user approval required
