# Phase 6 Notes — HUD Surface & Audio Integration

## 1. Summary of Changes
- Integrated streaming status display directly into the tactical HUD bottom bar in `ui.py`.
- Added `MainWindow._streaming_status_sig = pyqtSignal(str, str, str)` marshaled safely to GUI thread slot `MainWindow._apply_streaming_status(provider, surface, state)`.
- Configured format: `f"{provider.upper()} · {surface.lower()} · {state.upper()}"` (e.g., `CRUNCHYROLL · chrome · PLAYING`).
- When state is idle or stopped, the status pill automatically hides without causing repaints or timers.
- Added wrapper `AlfredUI.set_streaming_status(provider, surface, state)`.
- Reused `player.show_toast(...)` for all navigation and playback updates.
- Audio ducking integration: Leveraged `core.audio_ducker` via ALFRED's `SPEAKING` state transitions in `main.py`. Target processes include `chrome.exe`, `msedge.exe`, `firefox.exe`, `brave.exe`, and `netflix.exe`. Volume ducks to 30% during speech and restores exact prior levels via `_original_volumes` dictionary.
- Answer window integration: Wired `_prompt_surface_choice` to `core.sentry.answer_window.AnswerWindow` synchronously. If prompt times out or cancels, returns `None`, strictly preventing default guesses.

## 2. Graphify Nodes & Code Locations
- Status Bar Indicator: `MainWindow._streaming_status_pill` in `ui.py`
- Signal Marshaling: `MainWindow._streaming_status_sig` in `ui.py`
- UI Wrapper: `AlfredUI.set_streaming_status` in `ui.py`
- Streaming Pilot Status Sync: `actions.streaming_pilot._sync_status` in `actions/streaming_pilot.py`
- Audio Ducker: `core.audio_ducker.duck_media_apps` & `core.audio_ducker.unduck_media_apps`
- Answer Window: `core.sentry.answer_window.AnswerWindow.request_answer_sync`

## 3. Measured Results & Verification
- Unit test suite verifies status updates, toast emissions, and answer window cancellation logic.
- Repaint happens strictly on state change (`PLAYING`, `PAUSED`, `HOME`), adding zero idle CPU overhead.
