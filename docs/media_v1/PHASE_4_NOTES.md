# Media Command v1 — Phase 4: HUD Image Deck

## Graphify nodes used

- `ui_mainwindow`, `ui_mainwindow_init`, `HudVideoSurface`, and `ThemeChrome` identified the retained MainWindow overlay pattern and themed HUD surface.

## Changes

- Added `core/imagery/cache.py`: a byte-only cache at `data/image_cache/`, keyed only by `sha256(value)[:16]` and capped by `IMAGE_CACHE_MAX_MB`.
- Added `core/ui/image_deck.py`: a draggable, closable HUD image panel. A `QRunnable` decodes and scales `QImage` off the UI thread once; the UI thread converts the completed image to one cached `QPixmap` for the QLabel.
- `MainWindow` retains a single image deck and exposes `show_image_deck(path, caption)` for the upcoming image sources and chat tool.

## Verification

- Cache tests assert the plaintext query never appears in cache filenames.
- The panel adds no timer and no custom `paintEvent`; idle display therefore does not add a frame-loop allocation path.
