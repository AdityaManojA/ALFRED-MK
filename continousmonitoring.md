# Continuous Screen Monitoring Plan

## Summary
Replace the current Sentry Mode webcam behavior with true screen monitoring. Clicking `[ ▣ ] SENTRY MODE` starts/stops screen monitoring, and voice commands like “stop monitoring the screen” also stop it. The feature is meant for tasks like: “Alfred, tell me when the Antigravity IDE agent completes its task.”

## Key Changes
- Remove camera startup from `ui.py::_toggle_sentry_mode`; Sentry Mode should no longer call `start_camera_stream()`.
- Add a `ScreenMonitorController` owned by `JarvisLive` in `main.py`.
- Add UI callbacks:
  - `ui.on_screen_monitor_toggle(enabled: bool)`
  - `ui.set_screen_monitor_state(active: bool, label: str)`
- Update the Sentry button text/state:
  - Off: `[ ▣ ]  SENTRY MODE`
  - On: `[ ◈ ]  SCREEN MONITORING`
- Add voice/tool support with a new inline tool or action:
  - `screen_monitor`
  - parameters: `action: start | stop | status`, `goal: string`, `interval_seconds: number`
  - examples: “monitor my screen”, “tell me when Antigravity finishes”, “stop monitoring”

## Monitoring Behavior
- Default mode: screen-only, not camera.
- Capture the screen every 3 seconds by default using existing `actions.screen_processor.capture_screen()`.
- Store only the latest observation in memory, not a growing screenshot archive.
- Each observation includes:
  - compressed screenshot bytes
  - active app/title from `[WINDOW_CONTEXT]`
  - timestamp
  - optional OCR/text summary if available later
- For a goal like “tell me when Antigravity completes,” compare recent observations for likely completion signals:
  - active window/title changes
  - visible status text changes
  - screen no longer changing for several cycles
  - explicit words like done, complete, finished, success, failed, error
- Only send a frame to the AI when a meaningful state change or possible completion is detected, not every interval.

## Stop Conditions
- User clicks the Sentry button again.
- User says: “stop monitoring”, “stop watching my screen”, “turn off sentry mode”, or similar.
- App shutdown stops the monitor task cleanly.
- If screen capture fails repeatedly, stop after 3 consecutive failures and log an error.

## Tests
- Unit test start/stop/status for `ScreenMonitorController`.
- Mock `capture_screen()` and verify polling runs until stopped.
- Verify Sentry Mode no longer starts camera stream.
- Verify clicking the button twice starts then stops monitoring.
- Verify voice/tool `screen_monitor stop` stops the same running monitor.
- Verify completion detection triggers one notification and then stops or marks complete.

## Assumptions
- Default interval is 3 seconds.
- No screenshots are persisted to disk by default.
- Monitoring is screen-only unless a separate future camera feature is requested.
- Click + voice stop is the default, since that matches your request.
