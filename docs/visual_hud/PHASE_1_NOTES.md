# Phase 1 Notes: GUI-Thread Marshal & Timer Crash Fix (P1)

## 1. Summary of Changes
- **Thread Assertion (`assert_gui_thread`)**:
  - Implemented `assert_gui_thread()` in `core/hud_video/controller.py`.
  - Added assertions to all GUI-mutating backend and controller operations in `core/hud_video/backends/local_url.py` (`load`, `play`, `pause`, `stop`, `set_muted`, `set_volume`, `seek`) and `core/hud_video/controller.py` (`_do_*` methods).
- **Queued Signal Marshalling (`HudVideoController`)**:
  - Added cross-thread signals:
    - `_sig_begin_resolve(str, str)` -> `_do_begin_resolve`
    - `_sig_source_ready(object, float)` -> `_do_source_ready`
    - `_sig_signal_error(str)` -> `_do_signal_error`
    - `_sig_set_muted(bool)` -> `_do_set_muted`
    - `_sig_set_volume(float)` -> `_do_set_volume`
  - Re-routed all public methods (`begin_resolve`, `on_resolved`, `signal_error`, `set_muted`, `set_volume`, `play`, `pause`, `stop`, `seek`, `seek_rel`, `toggle`, `replay`) through `_is_off_thread()`.
  - Ensured all timers (`_idle_timer`, `_error_timer`, `_resolve_timer`) are started and stopped exclusively on the GUI thread.
- **Player & FFmpeg Demuxer Hygiene**:
  - `LocalUrlBackend.load()` now asserts GUI thread, checks if playback is active, and performs a clean `stop()` before calling `setSource()` on the `QMediaPlayer`.

---

## 2. Graphify Nodes & Edges Referenced
- `$graphify-root$_core_hud_video_controller_assert_gui_thread` (`assert_gui_thread()`): Global Qt GUI thread validator.
- `$graphify-root$_core_hud_video_controller_hudvideocontroller` (`HudVideoController`): Cross-thread queued signal marshaller.
- `$graphify-root$_core_hud_video_backends_local_url_localurlbackend` (`LocalUrlBackend`): Thread-safe `QMediaPlayer` backend.

---

## 3. Test Verification
- `tests/hud_video/test_thread_marshal.py`: 3/3 tests passed.
  - `test_assert_gui_thread_on_main_thread`: Passes on Qt main thread.
  - `test_assert_gui_thread_fails_on_worker_thread`: Raises `RuntimeError` on worker thread.
  - `test_cross_thread_begin_resolve_and_ready`: Verified that background worker thread dispatches onto Qt main thread without `QObject::startTimer` or `killTimer` warnings.
- Total Visual HUD tests: 78/78 passing.
