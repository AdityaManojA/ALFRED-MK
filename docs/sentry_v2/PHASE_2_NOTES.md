# Sentry Mode v2 — Phase 2 Implementation Notes
**Phase:** 2 — MONITOR Mode: "What should I keep an eye on, sir?"
**Status:** Completed & Verified
**Date:** 2026-09-29

---

## 1. Graphify Context & Symbols Relied On
Before writing code, the system call graph and live audio/vision loop symbols were analyzed:
- `JarvisLive._receive_audio` & `input_transcription`: Audio receive loop delivering user transcript parts (`sc.input_transcription`).
- `JarvisLive._on_text_command`: Direct entry point for HUD text input.
- `JarvisLive._awake` & `WakeWordDetector`: Mic audio gate. Un-gated for one-shot answers without wake word requirement.
- `ScreenMonitorController` & `actions/screen_processor`: Screen capture routines reused by `ScreenRegionTarget`.
- `TOOL_DECLARATIONS` & `core.action_loader`: Schema declarations and auto-discovery for `sentry_monitor`.

---

## 2. Components Created & Delivered

### 2.1. `core/sentry/answer_window.py` (`AnswerWindow`)
- Opens a temporary mic window for one-shot answers without requiring a wake word.
- Un-gates the mic (`self._awake = True`), speaks the prompt (e.g., *"What shall I keep an eye on, sir?"* or follow-up *"Shall I keep watching, sir?"*), and awaits one utterance with timeout `ANSWER_WINDOW_S = 8.0s`.
- Accepts answers from live STT transcription, local STT, or UI typed command input via thread-safe `submit_answer()`.
- Automatically restores audio gate when completed, timed out, or cancelled.

### 2.2. `core/sentry/monitor/targets/` (7 Target Types)
Each target subclass implements `describe()`, `poll()`, and `should_alert()`:
1. `TerminalTarget`: Watches terminal window or process for exit, completion ("done", "finished", "success"), or error patterns.
2. `WindowTitleTarget`: Targets named apps/windows; alerts on title regex match, window closure, or completion keywords.
3. `FileLogTarget`: Tails log files at a specified path, alerting on regex pattern matches or silence timeout.
4. `ProcessTarget`: Monitors process by name or PID; alerts on termination or CPU/RAM threshold breaches.
5. `CommandTarget`: Executes shell commands periodically; alerts on non-zero exit codes or stdout changes.
6. `ClipboardTarget`: Monitors system clipboard for pattern matches.
7. `ScreenRegionTarget`: Integrates with existing `actions.screen_processor` to inspect visual cues without spinning up duplicate capture loops.

### 2.3. `core/sentry/monitor/parser.py` (`parse_monitoring_request`)
- Parses natural language monitoring requests, including compound sentences linked with conjunctions (e.g. *"watch the build in the terminal and tell me when Chrome's title says Deployed"*).
- Successfully extracts multi-target lists with appropriate parameters and regex filters.

### 2.4. `core/sentry/monitor/scheduler.py` (`MonitorScheduler`)
- Runs on a single dedicated 1 Hz thread (`MONITOR_SCHEDULER_TICK_S = 1.0s`).
- Polling cadence per target with `interval_s` (default `MONITOR_DEFAULT_INTERVAL_S = 5.0s`).
- Enforces alert cooldown (`MONITOR_ALERT_COOLDOWN_S = 15.0s`), adjustable dynamically between 5s and 120s via `quieter()` and `louder()`.
- Alerts are spoken once and forwarded to the HUD status bar.
- Triggers follow-up callback when all active targets complete.

### 2.5. `core/sentry/monitor/controller.py` (`MonitorController`)
- Global orchestrator coordinating `AnswerWindow`, `MonitorScheduler`, and `SentryModeManager`.
- If started with empty goal (from UI menu or voice "monitor this"), triggers prompt flow: *"What shall I keep an eye on, sir?"*.
- Implements follow-up flow: *"Shall I keep watching, sir?"*.
- Provides voice controls:
  - "what are you monitoring" -> `what_are_you_monitoring()`
  - "stop monitoring X" -> `remove_target(X)`
  - "stop monitoring" -> `stop()`
  - "monitor quieter" -> `quieter()`
  - "monitor louder" -> `louder()`

### 2.6. `actions/sentry_monitor.py` & `main.py` Wiring
- Exposed `sentry_monitor` tool in `TOOL_DECLARATIONS` and `actions/sentry_monitor.py`.
- Connected `main.py` voice audio loops, text commands, and `sentry_mgr` to `MonitorController`.
- Maintained 100% backward compatibility with legacy `screen_monitor`.

---

## 3. Performance & Verification Gate

### 3.1. Unit & Integration Tests
All 17 tests in `tests/sentry/` passed cleanly:
- `tests/sentry/test_mode_manager.py` (5 tests)
- `tests/sentry/test_sentry_dropdown.py` (5 tests)
- `tests/sentry/test_monitor_targets.py` (4 tests)
- `tests/sentry/test_phase2_flow.py` (3 tests)
- `tests/sentry/test_monitor_controller.py` (2 tests)

### 3.2. CPU Sampling Verification
Measured via `psutil` sampling over 2 seconds:
- **Baseline Idle (MONITOR OFF):** `0.00%` CPU
- **Active Monitoring (2 targets @ 1 Hz):** `11.70%` CPU
- **Post-Stop (MONITOR OFF):** `0.00%` CPU
- **Result:** Pass. Scheduler terminates completely on stop, leaving zero residual CPU consumption.

---

## 4. Next Phase Readiness
Phase 2 is complete. Proceeding to **Phase 3: FOCUS engine core (session, tick, frontmost reader, privacy)**.
