# Visual HUD v3 — Phase 3 Notes: Tear-down & FFmpeg Hygiene

## 1. Overview
In Phase 3, we addressed demuxer teardown race conditions and FFmpeg/TLS console noise during source transitions and teardown.

## 2. Graphify Knowledge Graph Citations
- **Nodes Referenced:**
  - `LocalUrlBackend` (Node in Community 162 / `core/hud_video/backends/local_url.py`): Added `PLAYER_STOP_WAIT_MS` and `_wait_stopped()` to ensure clean demuxer shutdown before changing media source or clearing backend.
  - `extract_stream_url` (Node in `core/hud_video/backends/youtube.py`): Ensured stream logging records host only (`urlparse(stream_url).netloc`) rather than raw signed googlevideo URLs with sensitive authentication tokens.
  - `main.py`: Updated startup configuration for `QT_LOGGING_RULES`.

## 3. Implementation Details

### A. Demuxer Teardown & Stop Wait (`LocalUrlBackend`)
- Added constant `PLAYER_STOP_WAIT_MS = 300` at top of `core/hud_video/backends/local_url.py`.
- Implemented `_wait_stopped(max_ms=PLAYER_STOP_WAIT_MS)` using `QElapsedTimer` and `QCoreApplication.processEvents()` to ensure `QMediaPlayer` enters `StoppedState` before clearing the media source or setting a new source.
- Updated `load()` to execute `self.stop()` (which waits for stopped state and releases decoder/file handles) before calling `self._player.setSource(url)`.
- Updated `stop()` to wait for stopped state before clearing source to `QUrl()`.

### B. FFmpeg & TLS Demux Log Muting (`main.py`)
- Extended `QT_LOGGING_RULES` environment variable initialization in `main.py:52`:
  ```python
  _os.environ.setdefault(
      "QT_LOGGING_RULES",
      "qt.multimedia.ffmpeg=false;qt.multimedia.ffmpeg.*=false;qt.tls.*=false",
  )
  ```
- Suppresses FFmpeg demuxer warnings, `Input #0` spew, and TLS close message errors (`[tls] Failed to send close message`, `[matroska,webm] Invalid track number 1`) when switching or terminating streams.

### C. Privacy & URL Logging (`core/hud_video/backends/youtube.py`)
- Replaced partial URL truncation logging with host-only logging:
  ```python
  host = urlparse(stream_url).netloc
  log.info("[hud_video] yt-dlp resolved %d URL(s); stream host: %s", len(urls), host)
  ```
- Ensures no signed CDN query parameters (such as Google Video playback tokens) are written to console or logs.

### D. Hardware Acceleration (d3d11) Policy
- `d3d11` hwaccel errors during VP9/WebM demuxing are treated as normal software fallback paths. They are muted by `QT_LOGGING_RULES` and not treated as playback failures or re-resolve triggers.

## 4. Test Results
- Discovery suite `tests/hud_video/`: 80/80 passed cleanly.
