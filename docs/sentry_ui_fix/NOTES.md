# Sentry Main-App Routing & Full-HUD Focus Display Notes
Date: 2026-09-29

## 1. Graphify Nodes & Code Locations
- `ui_mainwindow_toggle_sentry_mode` (`ui.py:L10101`): Main-app SENTRY MODE button click handler.
- `ui_mainwindow_create_sentry_menu` (`ui.py:L10118`): Sentry popup menu (MONITOR and FOCUS actions).
- `ui_mainwindow_apply_sentry_snapshot` (`ui.py:L10171`): Sentry snapshot Qt slot.
- `ui_hudcanvas` (`ui.py:L1212`): Main animated full HUD canvas.
- `ui_hudcanvas_paint_status_highlight_banner` (`ui.py:L2281`): Status highlight banner on full HUD.
- `core_sentry_mode_manager_sentrymodemanager` (`core/sentry/mode_manager.py:L78`): Central mode coordinator.
- `core_sentry_monitor_controller_monitorcontroller` (`core/sentry/monitor/controller.py:L27`): Sentry monitor controller.
- `core_sentry_monitor_targets_screen_region` (`core/sentry/monitor/targets/screen_region.py:L8`): Screen region monitor target.
- `core_sentry_focus_engine_focusengine` (`core/sentry/focus/engine.py:L48`): Focus session engine.
- `main_jarvislive_ui_screen_monitor_toggle` (`main.py:L1166`): Fast bridge between UI and Sentry monitor controller.
- `actions_manage_monitor` (`main.py:L1924`): Separate background news/topic monitoring tool (NOT Sentry).

---

## 2. Reconnaissance & Trace Findings

### Issue 1: Main-app MONITOR button vs Topic/News Monitoring
- **Tracing the Click Path**:
  - The Sentry toggle button `self._sentry_btn` in `ui.py:L8070` connects to `_toggle_sentry_mode`.
  - When clicked without boolean argument, `_toggle_sentry_mode` opens `_show_sentry_menu` (`_create_sentry_menu` in `ui.py:L10118`).
  - In `_create_sentry_menu`, clicking MONITOR calls `_toggle_monitor_mode` (`ui.py:L10161`), which calls `mgr.toggle_monitor()`.
  - `mgr.toggle_monitor()` invokes `mgr.start_monitor()`, which calls the registered `on_start` handler: `self.monitor_controller.start(goal, interval_seconds)` in `core/sentry/monitor/controller.py:L127`.
  - In `MonitorController.start()`, if `goal` is empty (as when clicked from menu without prompt), it calls `self._spawn_prompt_flow()` which speaks `"What shall I keep an eye on, sir?"` and opens an `AnswerWindow`.
  - If a user asked Alfred "what are you monitoring?" or if LLM misrouted to `manage_monitor`, Alfred called `manage_monitor` action (`main.py:L1924`), returning `"Monitoring: AI news, tech news, ..."`.
  - When starting MONITOR directly from the menu / Sentry button, selecting "MONITOR (Start Screen)" or starting screen monitoring must start `ScreenRegionTarget` ("screen") by default so that visual screen monitoring is immediately activated and truthful feedback is reported.
  - Sentry MONITOR (`ScreenRegionTarget` / `MonitorScheduler`) is completely decoupled from the background topic monitor (`manage_monitor`).

### Issue 2: FOCUS state in Minimized HUD vs Full HUD
- **Minimized HUD**:
  - `MinimizedHudOverlay.update_sentry_indicator` (`ui.py:L3817`) receives `mon.active`, `foc.active`, `foc.remaining_s`, `foc.drifting`, `waiting_for_answer`.
  - When FOCUS is active, it formats `FOC MM:SS`, turning RED when drifting or CYAN when on-target.
- **Full HUD (`HudCanvas`)**:
  - `HudCanvas` in `ui.py` renders the central reactive globe and the bottom status highlight banner `_paint_status_highlight_banner` (`ui.py:L2281`).
  - Currently, `_paint_status_highlight_banner` only checked `self.muted`, `self.speaking`, `self.state`, with no awareness of Sentry `FocusState` or `MonitorState`!
  - `HudCanvas` was never passed the Sentry snapshot in `_apply_sentry_snapshot`.
  - Consequently, full HUD never displayed the FOCUS session countdown, drift status, paused status, or screen monitor status.

### Issue 3: Screen Capture Facility & Availability
- Screen monitoring in Sentry uses `ScreenRegionTarget` (`core/sentry/monitor/targets/screen_region.py`) and `actions.screen_processor.capture_screen`.
- `capture_screen()` uses `mss` for fast multi-platform frame grabbing and OS-native window context querying (`win32gui`/`psutil` on Windows, `xdotool`/`wmctrl` on Linux).
- If screen capture fails (e.g. missing permission or display server error), `capture_screen` raises an exception, which `ScreenRegionTarget` / `ScreenMonitorController` captures and reports cleanly without crashing or fabricating success.

---

## 3. Proposed Fix Order

1. **Phase 1: Main-app Sentry MONITOR Menu & Screen Target Routing**
   - In `ui.py` `_create_sentry_menu`, update the menu options:
     - `MONITOR (Screen)` ▸ Start/Stop (starts `ScreenRegionTarget` directly via `start_monitor(goal="screen")`).
     - `MONITOR (Custom / Ask)` ▸ Start with voice prompt (`start_monitor()`).
     - `FOCUS` ▸ Start/Stop.
   - When Screen Monitor starts, ensure truthful status (`[ ◈ ] SCREEN MONITORING`) is displayed on the button and HUD.
   - Ensure `manage_monitor` topic subscriptions remain completely untouched.

2. **Phase 2: Full-HUD Focus & Sentry Display**
   - Add `sentry_snapshot: SentrySnapshot | None` property and updater method to `HudCanvas`.
   - Update `_paint_status_highlight_banner` in `HudCanvas` to prominently display:
     - Active FOCUS: `● FOCUS ACTIVE [MM:SS] // ON TARGET` (or `⚠ FOCUS DRIFTING [MM:SS] // RETURN TO TARGET` in red, or `⏸ FOCUS PAUSED [MM:SS]`).
     - Deferred lock: `FOCUS: DEFERRED TARGET LOCK`.
     - Active MONITOR: `◈ SCREEN MONITOR ACTIVE`.
     - Fallback to normal audio/privacy banner when inactive.
   - Connect `_apply_sentry_snapshot` in `MainWindow` to pass snapshots to `self.hud.set_sentry_snapshot(snapshot)`.
   - Sync current snapshot to `HudCanvas` on show/restore so full HUD does not wait for a future tick.

3. **Phase 3: Verification & Test Suite**
   - Add unit tests in `tests/sentry/test_sentry_ui_routing.py` verifying:
     - MONITOR menu routes to screen target by default.
     - MONITOR does not alter or query background topic settings.
     - Full HUD reflects active, paused, drifting, and inactive FOCUS states.
     - Minimized HUD and full HUD maintain consistent state across minimize/restore.

---

## 4. Implementation & Verification Checklist

- [x] Click MONITOR in the main app; verify the screen target actually runs (`ScreenRegionTarget`).
- [x] Verify it does not announce or change AI/news topic subscriptions (completely separate from `manage_monitor`).
- [x] Stop MONITOR; verify Sentry screen polling stops.
- [x] Start FOCUS; verify status appears in the full HUD (`HudCanvas` banner rendering active countdown, paused, and drift states).
- [x] Minimize and restore; verify both HUDs show the same current FOCUS state (`MinimizedHudOverlay` and `HudCanvas` sync via `_apply_sentry_snapshot`).
- [x] Verify unavailable/permission-denied screen monitoring is reported honestly.

