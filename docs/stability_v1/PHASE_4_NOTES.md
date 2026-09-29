# Phase 4 Notes: TTS Silent Fix

## Summary
Fixed the silent no-op issue when TTS vocalization is invoked without an active Gemini live connection or during background/local execution, and added a startup self-check.

## Graphify Citations
- Node: `main.py::AlfredApp::speak`
- Node: `main.py::AlfredApp::_speak_local`
- Node: `main.py::AlfredApp::_tts_self_check`
- Node: `core/tts/__init__.py::get_engine`
- Node: `core/tts/engine_default.py::EngineDefault`

## Key Implementation Details
1. **Fallback Local Speech Synthesis (`main.py`):**
   - `speak(text)` previously aborted silently when `self.session` was None.
   - Now routes to `_speak_local(text)` which spins up an async worker using `core.tts.get_engine()` to play audio via sounddevice.
2. **Missing Announcement Method Implementation:**
   - Implemented `_safe_background_announce()` to reliably speak progress completion announcements.
3. **Startup Self-Check (`main.py`):**
   - Added `_tts_self_check()` in `AlfredApp.__init__`.
   - Validates sounddevice output devices and initializes the active TTS engine, logging a single descriptive error line if audio hardware or TTS engines are unavailable.
