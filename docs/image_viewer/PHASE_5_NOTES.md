# Phase 5 Notes: Tests, Documentation & Graphify (P5)

## 1. Summary of Completed Work
- **Unit Testing Suite**:
  - `tests/test_image_viewer_fit.py` (7 tests): Exhaustive testing of `fit_size` across aspect ratios (landscape, portrait, square, tiny <240px, 8K downscaling, invalid dimensions).
  - `tests/test_lazy_viewer.py` (3 tests): Verifies viewer is NOT constructed at startup; constructs lazily on first request via registry factory; frees `_cached_pixmap` and `_raw_image` upon `close_viewer()`.
  - `tests/test_ui_mismatches_ast.py` (2 tests): Scans `main.py` AST to guarantee all `self.ui.*` accesses exist on `JarvisUI`, and confirms `set_media_arbiter(self, arbiter)` signature.
  - `tests/test_image_fetch.py` (16 tests): Tests fake HTTP responses (bad content-type, oversize rejection, timeout, corrupt image payloads, 404s), LRU cache eviction at 100MB, candidate cycling forward/backward with wraparound, intent precedence/clash avoidance, ALFRED persona speech rules (speaks only on failure: *"Couldn't find one, sir."*), and token privacy verification.
  - `tests/hud_video`: All 75 Visual HUD video tests continue passing with zero regressions.
- **System Prompt Updates (`core/prompt.txt`)**:
  - Updated reference-image routing rules to document:
    - `"Show me a reference image of …" / "pull up a picture of …"` -> `show_image` query.
    - `"Another one" / "next"` -> candidate cycling (`action='next'`).
    - `"Close the image"` -> dismiss viewer (`action='close'`).
    - ALFRED persona rules: Toast notification only on success (no voice announcement); speaks *"Couldn't find one, sir."* only on failure.
- **Live Verification Checklist (`docs/image_viewer/VERIFY.md`)**:
  - Authored comprehensive verification checklist covering clean boot, aspect ratio fitting, candidate cycling, layering & airspace hierarchy, Visual HUD video coexistence, failure handling, and idle resource footprint.
- **Knowledge Graph Synchronization**:
  - Executed `graphify update .` to index all Image Viewer v2 modules, classes, and tests into `graphify-out/`.

---

## 2. Graphify Nodes & Edges
- `core/image_viewer/fit.py`: `fit_size()`, `VIEWER_MAX_SCREEN_FRAC`, `VIEWER_MIN_PX`, `VIEWER_MAX_DECODE_PX`.
- `core/image_viewer/viewer.py`: `ImageViewerWindow`, `_ImageCanvas`, `Z_IMAGE_VIEWER`.
- `core/image_viewer/fetch.py`: `fetch_image()`, `validate_image_bytes()`, `ReferenceImageSession`, `FETCH_TIMEOUT_S`, `FETCH_MAX_MB`.
- `core/image_viewer/cache.py`: `ImageViewerCache`, `IMAGE_CACHE_MAX_MB`.
- `core/imagery/intent.py`: `classify_image_intent()`, `detect()`.
- `actions/show_image.py`: `show_image()`, `TOOL`.
- `tests/test_image_viewer_fit.py`, `tests/test_lazy_viewer.py`, `tests/test_image_fetch.py`, `tests/test_ui_mismatches_ast.py`.

---

## 3. Final Test Metrics
- Total new Image Viewer test cases: 28 passing.
- Total existing Visual HUD test cases: 75 passing.
- Overall regression pass rate: 100% (103/103 tests passing).
