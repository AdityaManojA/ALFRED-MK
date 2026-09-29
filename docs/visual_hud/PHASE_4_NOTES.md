# Visual HUD v3 — Phase 4 Notes: Tests, Documentation & Graphify

## 1. Overview
In Phase 4, we added comprehensive unit tests covering GUI thread marshaling, deduplication/single-flight cancellation, terminal output formats, stream URL privacy, and demuxer teardown hygiene. We also prepared the live verification checklist in `docs/visual_hud/VERIFY.md` and updated the repository knowledge graph with Graphify.

## 2. Graphify Knowledge Graph Citations
- **Nodes Referenced:**
  - `HudVideoController` (`core/hud_video/controller.py`): Thread boundary enforcement via `assert_gui_thread()` and queued Qt signals (`_sig_begin_resolve`, `_sig_source_ready`, `_sig_signal_error`, `_sig_set_muted`, `_sig_set_volume`, `_sig_stop`, `_sig_pause`, `_sig_play`, `_sig_toggle`, `_sig_replay`, `_sig_seek`, `_sig_seek_rel`).
  - `LocalUrlBackend` (`core/hud_video/backends/local_url.py`): Demuxer shutdown hygiene with `PLAYER_STOP_WAIT_MS = 300` and `_wait_stopped()`.
  - `_SingleFlightManager` (`actions/hud_video.py`): Target normalization, debounce (`RESOLVE_DEBOUNCE_MS = 800`), TTL in-flight caching (`SAME_TARGET_TTL_S = 30`), and generational cancellation tokens.
  - `extract_stream_url` (`core/hud_video/backends/youtube.py`): Host-only stream logging (`urlparse(stream_url).netloc`) for privacy.
  - `main.py`: `QT_LOGGING_RULES` suppression of FFmpeg demuxer warnings and TLS close error noise.

## 3. Unit Test Suite Summary
The entire `tests/hud_video/` suite contains 83 passing unit tests:
1. `tests/hud_video/test_thread_marshal.py`:
   - `test_off_thread_begin_resolve_marshaled_to_gui_thread`: Asserts non-GUI thread call to `begin_resolve()` triggers queued signal and asserts GUI thread.
   - `test_off_thread_source_ready_marshaled_to_gui_thread`: Asserts `on_resolved()` dispatches `_sig_source_ready` and executes `load()` only on the GUI thread.
   - `test_local_url_backend_asserts_gui_thread`: Verifies direct calls from worker threads to `LocalUrlBackend.load()`, `play()`, `stop()`, etc., raise `RuntimeError` on non-GUI threads.
2. `tests/hud_video/test_dedupe_singleflight.py`:
   - `test_twenty_duplicate_calls_start_single_resolve`: Verifies 20 rapid invocations for the same normalized target start exactly 1 resolve task and return terminal debounce messages for the remaining 19.
   - `test_different_target_cancels_previous_resolve`: Verifies changing target increments the active generation token, causing older background worker results to be cleanly discarded.
3. `tests/hud_video/test_playback_hygiene.py`:
   - `test_tool_output_is_terminal_and_no_resolving_string`: Verifies all tool outputs are terminal strings (`"Playing ..."` or `"Visual HUD is already preparing ..."`) with no interim `"Resolving:"` string that would prompt an LLM tool loop.
   - `test_privacy_googlevideo_query_token_not_logged`: Verifies raw stream query parameters and authentication tokens are scrubbed from log output.
   - `test_switching_sources_twice_runs_cleanly`: Verifies loading sequential sources invokes `_wait_stopped()` and releases backend resources cleanly.

## 4. Verification Document
- Created `docs/visual_hud/VERIFY.md` containing end-to-end live testing instructions for voice playback, debounce, source switching, HUD close, and CPU profiling.
