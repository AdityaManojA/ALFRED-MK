# PHASE 1 NOTES — SENTRY DUAL-MODE SYSTEM WITH DROPDOWN
**Repository:** ALFRED-MK-V  
**Date:** 2026-09-29  
**Status:** Complete  

---

## 1. What Changed

### Core Mode Manager (`core/sentry/mode_manager.py`)
- Created `core/sentry/__init__.py` and `core/sentry/mode_manager.py`.
- Implemented `SentryModeManager` singleton owned by the application lifecycle (`JarvisLive`), decoupling mode state from individual Qt HUD widgets.
- Introduced whitelist-only immutable dataclasses:
  - `MonitorState`: `active: bool`, `target_count: int`, `last_alert_s: float`, `label: str`.
  - `FocusState`: `active: bool`, `paused: bool`, `deferred_lock: bool`, `locked_app: bool`, `locked_tab: bool`, `planned_s: int`, `elapsed_s: int`, `on_target_s: int`, `remaining_s: int`, `drifting: bool`, `drift_count: int`, `current_drift_s: int`, `tier: int`, `snoozed_until_s: float`, `excused: bool`, `nag_interval_s: int`, `intent_set: bool`.
  - `SentrySnapshot`: `monitor: MonitorState`, `focus: FocusState`, `timestamp: float`.
- Rate-limited Qt signal emission `state_changed(SentrySnapshot)` to strictly $\le$ 1 Hz (`STATE_EMIT_INTERVAL_S = 1.0`) with mutex-protected state transitions.
- Exposes `start_monitor`, `stop_monitor`, `toggle_monitor`, `start_focus`, `stop_focus`, and `toggle_focus`.

### Full HUD Dropdown (`ui.py`)
- Updated `MainWindow._sentry_btn`:
  - When clicked, opens a themed retro-cyber `QMenu` dropdown at the button position.
  - Dropdown options:
    - `[ ◈ ] MONITOR (ON) ▸ Stop` / `[ ▣ ] MONITOR (OFF) ▸ Start`
    - `[ ◉ ] FOCUS (ON) ▸ Stop` / `[ ○ ] FOCUS (OFF) ▸ Start`
  - Button text and icon dynamically reflect active modes:
    - Both inactive: `[ ▣ ]  SENTRY MODE`
    - Monitor only: `[ ◈ ]  SCREEN MONITORING`
    - Focus only: `[ ◉ ]  FOCUS MODE`
    - Both active: `[ ◈◉ ] SENTRY (2)`
  - Preserves 100% backward compatibility with `on_screen_monitor_toggle` and programmatic boolean toggles.

### Minimized Translucent HUD Dropdown (`ui.py`)
- Added `self._sentry_btn` (`QPushButton("S")`) to the `MinimizedHudOverlay` header bar beside the minimize/restore controls.
- Clicking `S` opens the exact same themed dropdown menu from the minimized overlay.
- Added `update_sentry_indicator(mon_active, foc_active)` which highlights the indicator (`S●`) in theme emerald (`C.GREEN`) for monitor, crimson (`C.RED`) for focus or both, and muted (`C.TEXT_MED`) when idle.

### Application Integration (`main.py`)
- Instantiated `self.sentry_mgr = get_sentry_mode_manager()` in `JarvisLive.__init__`.
- Registered `_start_screen_monitor` and `_stop_screen_monitor` as the driver callbacks for `MONITOR` mode.
- Connected `self.sentry_mgr.state_changed` to `self.ui.apply_sentry_snapshot` so any state change updates both full and mini HUD automatically.

### Automated Tests
- `tests/sentry/test_mode_manager.py`: Verifies singleton identity, initial states, independent mode toggling, whitelist privacy fields, and 1 Hz signal rate-limiting (5/5 tests passing).
- `tests/sentry/test_sentry_dropdown.py`: Verifies menu action labels, independent toggling via menu actions, button label updates, and `MinimizedHudOverlay` Sentry button & indicators (3/3 tests passing).
- Regression suite: All 36 tests across existing test suites pass.

---

## 2. Graphify Nodes & Symbols Used

| Node ID | Symbol | Role |
|---|---|---|
| `ui_mainwindow_toggle_sentry_mode` | `MainWindow._toggle_sentry_mode()` | Refactored from direct toggle to open dropdown menu with boolean compatibility |
| `main_rationale_1056` | `JarvisLive._ui_screen_monitor_toggle()` | Wired to `sentry_mgr.start_monitor()` / `stop_monitor()` |
| `ui_minimizedhudoverlay` | `MinimizedHudOverlay` | Added header Sentry control button and indicator update |
| `ui_c` | `class C` | Palette colors (`PANEL`, `BORDER_B`, `TEXT`, `GREEN`, `RED`, `TEXT_MED`) |
| `actions_screen_monitor_screenmonitorevent` | `ScreenMonitorController` | Existing screen/terminal monitoring preserved as the initial MONITOR driver |

---

## 3. Acceptance Verification

1. **Both modes toggle independently:** Verified in `test_dropdown_toggles_modes_independently` and `test_independent_mode_toggling`.
2. **Reachable from full and mini HUD:** Verified in `test_minimized_overlay_has_sentry_button_and_indicator`.
3. **Old terminal sentry still works exactly as before:** Verified in `test_sentry_click_uses_monitor_callback_and_never_needs_camera` and `test_main_start_stop_helpers_share_one_controller`.

---

## 4. Open Questions

None. Ready for Phase 2 (MONITOR Mode: Answer window and target generalization).
