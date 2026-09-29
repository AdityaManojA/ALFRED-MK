# Image Viewer v2 — Phase 3: Sizing & Fitting Implementation Notes

## Changes Made
1. **Created `core/image_viewer/fit.py`**:
   - Pure, mathematical geometric sizing calculation `fit_size(img_w, img_h, avail_w, avail_h, frac=VIEWER_MAX_SCREEN_FRAC, dpr=1.0)`.
   - Named constants:
     - `VIEWER_MAX_SCREEN_FRAC = 0.85`
     - `VIEWER_MIN_PX = 240`
     - `VIEWER_MAX_DECODE_PX = 3840`
   - Constraints enforced:
     - Aspect ratio is strictly preserved across all dimensions.
     - Never crops and never upscales beyond native size unless below `VIEWER_MIN_PX`.
     - Clamped to available screen dimensions (accounting for multi-monitor setups).
     - Downscales huge 8K images exceeding `VIEWER_MAX_DECODE_PX` to prevent memory exhaustion.

2. **Letterbox Image Canvas (`core/image_viewer/viewer.py`)**:
   - `_ImageCanvas` caches a smooth-scaled `QPixmap` on load and on resize only.
   - Zero heap allocations inside `paintEvent` (prebuilt QBrush and QPen).
   - Letterboxes cleanly with black background.
   - Caption strip displaying the source host sits in a dedicated layout bar strictly below the canvas.

3. **Unit Tests (`tests/test_image_viewer_fit.py`)**:
   - Tested landscape downscaling.
   - Tested portrait downscaling.
   - Tested native fitting when smaller than screen fraction.
   - Tested square aspect ratio preservation.
   - Tested 8K image bound enforcement with no off-screen bounds.
   - Tested tiny image minimum bounds meeting `VIEWER_MIN_PX`.
   - All 7 tests passing.

## Graphify Nodes Referenced
- `core_image_viewer_fit_fit_size` (`fit_size` in `core/image_viewer/fit.py`)
- `core_image_viewer_viewer_imagecanvas` (`_ImageCanvas` in `core/image_viewer/viewer.py`)
- `core_image_viewer_viewer_imageviewerwindow` (`ImageViewerWindow` in `core/image_viewer/viewer.py`)
- `tests_test_image_viewer_fit` (`tests/test_image_viewer_fit.py`)
