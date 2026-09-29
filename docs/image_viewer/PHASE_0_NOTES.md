# Image Viewer v2 — Phase 0: Reconnaissance Notes

## 1. The Crash Analysis
- **Where is `set_media_arbiter` defined?**
  - Defined on `MainWindow` in `ui.py:11105` (`ui_mainwindow_set_media_arbiter`):
    ```python
    def set_media_arbiter(self, arbiter) -> None:
        self._media_arbiter = arbiter
        self._bg_music.set_media_arbiter(arbiter)
        arbiter.state_changed.connect(self._on_media_state_changed)
        self._on_media_state_changed(arbiter.state)
    ```
  - Defined on `TronScoreBackgroundPlayer` in `ui.py:375` (`ui_tronscorebackgroundplayer_set_media_arbiter`).
  - **Missing on `JarvisUI`**: `main.py:789` holds `self.ui` which is an instance of `JarvisUI`. While `JarvisUI` delegates many methods to its inner `self._win` (`MainWindow`), `set_media_arbiter` was never implemented on `JarvisUI`, causing `AttributeError: 'JarvisUI' object has no attribute 'set_media_arbiter'` at boot.
- **Where is `media_arbiter` created, and who else calls it?**
  - Created in `main.py:787` via `get_media_arbiter()` (`core/media/arbiter.py:206`).
  - Notice callback set in `main.py:788` (`self.media_arbiter.set_notice_callback(self.speak)`).
  - Claims/releases `AudioSource.TTS` in `main.py:1326, 1335`.
  - Claims/releases `AudioSource.APP_PLAYER` in `ui.py:388, 390` (`TronScoreBackgroundPlayer`).
- **What does it arbitrate: audio, Visual HUD video, or the image viewer?**
  - Arbitrates **audio sources** (`AudioSource.APP_PLAYER`, `AudioSource.TTS`, `AudioSource.ALERT`).
  - Manages external media app suppression and speech ducking.
  - It does **not** arbitrate the image viewer (which is silent and visual).

## 2. Other `self.ui.<attr>` Mismatches in `main.py`
AST analysis of `main.py` against `JarvisUI` identified the following missing attributes / methods on `JarvisUI`:
1. `set_media_arbiter(self, arbiter)`: Called at `main.py:789` $\rightarrow$ crashes on boot. Needs forwarder to `self._win.set_media_arbiter(arbiter)`.
2. `toggle_mute(self)`: Called at `main.py:3052` by mobile dashboard action handler $\rightarrow$ crashes if invoked. Needs forwarder to `self._win._toggle_mute()`.
3. `on_wake_install`: Assigned at `main.py:958` dynamically.
4. `wake_is_ready`: Assigned at `main.py:954` dynamically.
5. `request_say`: Assigned at `main.py:935` dynamically.
6. `_win` and `root`: Instance attributes set in `JarvisUI.__init__`.

## 3. Existing Image Viewer Analysis
- **Which class and file is it?**
  - `ImageDeckPanel` in `core/ui/image_deck.py` (`core_ui_image_deck_imagedeckpanel`).
  - Legacy `ImagePopupOverlay` in `ui.py:5256` and `actions/show_image_popup.py`.
- **Where is it constructed, and what calls `show()`?**
  - `ImageDeckPanel` is constructed eagerly during startup inside `MainWindow.__init__` at `ui.py:8012` (`self._image_deck = ImageDeckPanel(self)`).
  - It calls `self.show(); self.raise_()` unconditionally inside `ImageDeckPanel.show_image()`.
  - Violates lazy allocation rules by instantiating widgets and global thread pools at boot even if never requested.
- **How is it sized and parented?**
  - Hardcoded fixed size: `IMAGE_PANEL_MAX_W = 480`, `IMAGE_PANEL_MAX_H = 360` (`self.setFixedSize(480, 360)`).
  - Parented as a child widget to `MainWindow` (`parent=self`).
  - Fails to scale to image aspect ratios, causing letterboxing/distortion, and cannot expand to high-res or large viewing sizes.

## 4. Reference-Image Route Analysis
- **Which intent matches "show me a reference image of X"?**
  - Matched in `core/prompt.txt` ("Show me …" / "pull up a picture of …" $\rightarrow$ `show_image`).
  - Matched in `core/imagery/intent.py` (`detect(utterance)` checks prefixes `"show me "`, `"pull up a picture of "`, `"show me the file "`).
- **What is the source of the image?**
  - Local folders: `core/imagery/sources/local.py` searches `Pictures`, `Downloads`, and `Desktop`.
  - Web source: `core/imagery/sources/web.py` queries Openverse API (`https://api.openverse.org/v1/images`).
- **Is there a fetch and validate helper?**
  - `actions/show_image.py` has a synchronous `requests.get` with basic disk cache (`core/imagery/cache.py`), but lacks `QImageReader` pre-validation, candidate cycling ("another one / next"), aspect-ratio screen fitting, or thread-safe UI signal marshalling.

## 5. Layering Architecture
- **Status of Visual HUD v2 `Z_*` constants and `raise_overlay()`**:
  - Fully implemented and verified in `core/hud_video/layering.py`:
    - `Z_VISUAL_HUD = 10`
    - `Z_HUD_BUTTONS = 20`
    - `Z_DROPDOWN_CARD_TOAST = 30`
    - `Z_SETTINGS_MODAL = 40`
  - Helper functions `make_frameless_overlay()`, `raise_overlay()`, and `centre_overlay_globally()` are active.
  - The new Image Viewer v2 will be configured as a frameless top-level window owned by `MainWindow` and sit below settings modals and dropdown cards.

## 6. Stale Track Path Report
- **Source of `D:/Projects/Alfred-Mark-IV/…`**:
  - Found in `ui.py:247` within the `_candidates` list of `TronScoreBackgroundPlayer._find_tracks()`:
    ```python
    Path(r"d:\Projects\Alfred-Mark-IV\The Son of Flynn (From TRON Legacy Score).mp3")
    ```
  - Also recorded in `config/music_playlist.json` as the saved `current_track`.
  - Per instructions, this path is reported and left unchanged.

## 7. Proposed File Layout (Image Viewer v2)
```
core/image_viewer/
├── __init__.py        # Re-exports and public interface
├── viewer.py          # ImageViewerWindow (frameless top-level window, Qt-thread safe, zero per-paint allocations)
├── fit.py             # Pure sizing calculations (fit_size with DPR, screen bounds, aspect ratio)
├── fetch.py           # Worker thread fetcher (timeout, size limit, content-type allowlist, QImageReader validation)
└── cache.py           # Disk-backed LRU image cache with byte limit and cleanup
```

## Graphify Nodes Referenced
- `ui_mainwindow_set_media_arbiter` (`MainWindow.set_media_arbiter` in `ui.py`)
- `ui_tronscorebackgroundplayer_set_media_arbiter` (`TronScoreBackgroundPlayer.set_media_arbiter` in `ui.py`)
- `core_media_arbiter_get_media_arbiter` (`get_media_arbiter` in `core/media/arbiter.py`)
- `core_media_arbiter_audiosource` (`AudioSource` in `core/media/arbiter.py`)
- `core_ui_image_deck_imagedeckpanel` (`ImageDeckPanel` in `core/ui/image_deck.py`)
- `core_hud_video_layering_raise_overlay` (`raise_overlay` in `core/hud_video/layering.py`)
- `core_hud_video_layering_z_visual_hud` (`Z_VISUAL_HUD` in `core/hud_video/layering.py`)
- `actions_show_image_show_image` (`show_image` in `actions/show_image.py`)
- `core_imagery_intent_detect` (`detect` in `core/imagery/intent.py`)
