# Phase 2 Notes: Kill the Remaining Off-Thread Timers

## Summary
Eliminated all `QObject::startTimer: Timers cannot be started from another thread` warnings by strictly guarding Qt timer operations with `assert_gui_thread()` and routing cross-thread requests via Qt Queued Signals.

## Graphify Citations
- Node: `core/gui_thread.py::assert_gui_thread`
- Node: `ui.py::HudCanvas::_start_animations`
- Node: `ui.py::HudCanvas::set_sentry_snapshot`
- Node: `ui.py::TronScoreBackgroundPlayer::play`
- Node: `ui.py::TronScoreBackgroundPlayer::pause`
- Node: `ui.py::TronScoreBackgroundPlayer::set_ducked`

## Key Implementation Details
1. **Central GUI-Thread Assertion Helper (`core/gui_thread.py`):**
   - Created `is_gui_thread()` and `assert_gui_thread(context_name)` checking against `QApplication.instance().thread()`.
2. **`HudCanvas` Timer Marshalling (`ui.py`):**
   - Added `_req_sentry_snapshot` and `_req_start_animations` pyqtSignals.
   - When called from background Sentry/analysis threads, `set_sentry_snapshot()` and `_start_animations()` emit signals to execute safely on the GUI thread.
   - Guarded `_do_start_animations()` and `_apply_sentry_snapshot()` with `assert_gui_thread()`.
3. **`TronScoreBackgroundPlayer` Audio Engine Marshalling (`ui.py`):**
   - Added thread marshaling signals:
     - `_req_set_ducked`
     - `_req_play`
     - `_req_pause`
     - `_req_pause_core`
     - `_req_resume_core`
     - `_req_set_base_volume`
     - `_req_load_track`
     - `_req_toggle_play`
   - `_fade_timer.start()`, `_fade_timer.stop()`, and `QMediaPlayer` state transitions are now 100% executed on Qt's main GUI thread.
