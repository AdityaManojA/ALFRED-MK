# Phase 6 Notes: Sys Audio Pause Fix

## Summary
Achieved symmetric, thread-safe control for playing, pausing, resuming, and querying the background TRON audio score engine and mobile status polling.

## Graphify Citations
- Node: `actions/audio_core.py::audio_core`
- Node: `ui.py::TronScoreBackgroundPlayer::pause_core`
- Node: `ui.py::TronScoreBackgroundPlayer::resume_core`
- Node: `ui.py::MainWindow::pause_audio_core`
- Node: `ui.py::MainWindow::resume_audio_core`
- Node: `main.py::AlfredApp::_on_dashboard_action`

## Key Implementation Details
1. **Symmetric Play/Pause/Resume in `TronScoreBackgroundPlayer` (`ui.py`):**
   - `pause_core()` explicitly stops `_fade_timer` and pauses `_player` on Qt GUI thread via `_req_pause_core` signal.
   - `resume_core()` resumes playback, restores normal volume ramp, and emits `playback_state_changed(True)` on Qt GUI thread via `_req_resume_core` signal.
2. **MainWindow Delegates (`ui.py`):**
   - Implemented `pause_audio_core()`, `resume_audio_core()`, `set_audio_core_volume()`, and `get_audio_core_status()`.
3. **Deck State Sync for Mobile Dashboard (`main.py`):**
   - Implemented `get_deck_state` action handler in `_on_dashboard_action()` returning real-time `audio_core.is_playing`, `track_stem`, `volume`, and `muted` state so the mobile uplink reflects accurate playback status immediately.
