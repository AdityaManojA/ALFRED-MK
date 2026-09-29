# Phase 4 Notes: Fetch Reference Image on Request (P4)

## 1. Summary of Changes
- **Image Cache (`core/image_viewer/cache.py`)**:
  - Implemented `ImageViewerCache` enforcing 100 MB disk cap (`IMAGE_CACHE_MAX_MB = 100`), thread-safe access with `threading.Lock`, and LRU eviction based on access timestamp (`st_atime`).
  - Strict privacy protections: logs domain host only, hashing cache keys with SHA-256 (`[:16]`). Query strings, tokens, and authorization credentials are scrubbed before logging and never written to disk paths.
- **Fetch Pipeline (`core/image_viewer/fetch.py`)**:
  - Implemented `fetch_image()` with timeouts and download limits (`FETCH_TIMEOUT_S = 8.0`, `FETCH_MAX_MB = 15`).
  - Enforced content-type allowlist (`image/jpeg`, `image/png`, `image/webp`, `image/bmp`, `image/gif`).
  - Pre-validation with `QImageReader` to verify image dimensions and header integrity before decoding or GUI construction.
  - Implemented `ReferenceImageSession` with candidate resolution (local files checked first, Openverse CC web search fallback) and forward/backward cycling (`next_candidate()`, `previous_candidate()`).
- **Intent Classification & Routing (`core/imagery/intent.py`)**:
  - Implemented `classify_image_intent(utterance)` and backwards-compatible `detect(utterance)`.
  - Routes voice queries:
    - `"show me a reference image of X"` / `"pull up a picture of X"` -> `action="search"`, `query="X"`
    - `"another one"` / `"next"` / `"next image"` -> `action="next"`
    - `"previous image"` / `"previous picture"` / `"prev"` -> `action="prev"`
    - `"close the image"` / `"dismiss the image"` -> `action="close"`
    - Explicit local file paths -> `action="path"`
  - Strict clash prevention:
    - Rejects music/playback requests (`"play ..."`).
    - Rejects Visual HUD video intents (presence of `VIDEO_LOCUS_PHRASES` like `"on screen"`, `"in the app"` or `VIDEO_INDICATORS` like `"trailer"`, `"video"`).
    - Rejects HUD close phrases (`"close the visual hud"`, `"back to the globe"`, `"restore the avatar"`).
- **Action & Voice Persona (`actions/show_image.py`)**:
  - Updated `show_image` action handler:
    - Interacts with `ReferenceImageSession` and `get_image_viewer()`.
    - Handles `"search"`, `"next"`, `"prev"`, and `"close"`.
    - Marshals display requests to the Qt main thread via `viewer.show_requested.emit(...)`.
    - ALFRED persona rules strictly adhered to:
      - Successful display shows a toast only (`"Reference image: <host>"`); no voice announcement.
      - Failed fetch or no candidate triggers spoken failure: `"Couldn't find one, sir."` and displays no empty window.
- **Thread Marshalling & Sizing (`core/image_viewer/viewer.py`)**:
  - Added `show_requested` and `close_requested` PyQt signals to `ImageViewerWindow` so background threads marshal to GUI safely.
  - Connected `next_requested` and `prev_requested` UI buttons `[❮]` and `[❯]` and hotkeys `[N]` / `[P]` directly to candidate cycling.

---

## 2. Graphify Nodes & Edges Referenced
- `$graphify-root$_actions_show_image_py` (`actions/show_image.py`): Upgraded tool schema, candidate cycling, and persona speech rules.
- `$graphify-root$_core_imagery_intent_py` (`core/imagery/intent.py`): Intent classification and deterministic clash avoidance.
- `$graphify-root$_core_imagery_sources_base_imageresult` (`core/imagery/sources/base.py:ImageResult`): Data model for candidate images.
- `$graphify-root$_core_imagery_sources_local_localsource` (`core/imagery/sources/local.py:LocalSource`): Local image searcher.
- `$graphify-root$_core_imagery_sources_web_websource` (`core/imagery/sources/web.py:WebSource`): Openverse CC search provider.
- `core_registry` (`core/registry.py`): Process-wide registry for `image_viewer` and `reference_image_session`.

---

## 3. Test Verification
- `tests/test_image_fetch.py`: 15/15 tests passing.
  - Fake HTTP mock tests (404, bad content-type, oversize, timeout, corrupt payload).
  - Cache LRU eviction and host-only privacy tests.
  - Candidate cycling and wraparound tests.
  - Intent classification and clash avoidance tests.
  - Action persona tests (toast-only on success, `"Couldn't find one, sir."` speech on failure).
- Existing test suites:
  - `tests/test_image_viewer_fit.py`: 7/7 passing.
  - `tests/test_lazy_viewer.py`: 3/3 passing.
  - `tests/test_ui_mismatches_ast.py`: 2/2 passing.
  - `tests/hud_video`: 75/75 passing.

---

## 4. Open Questions & Notes
- None. Phase 4 criteria fully satisfied. Proceeding to Phase 5.
