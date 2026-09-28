# Phase 7 Implementation Notes: Mini Translucent HUD & Floating Desktop Countdown Card

## 1. Objectives & Summary
Phase 7 introduces persistent, unobtrusive visual status indicators for Sentry Mode:
1. **Floating Desktop Countdown Card** (`core/sentry/focus/card.py`):
   - Compact 170x48 px frameless widget with translucent obsidian background (`rgba(10, 16, 26, 225)`).
   - Cyan progress ring tracking % time remaining.
   - Digital `mm:ss` countdown timer.
   - Red border and status glow during excursions (`drifting=True`).
   - Smooth left-click repositioning strictly clamped to desktop available geometry (`clamp_to_screen`).
   - Right-click tactical context menu:
     - Snooze (15 s)
     - Lock on this tab
     - Extend (+10 m)
     - Excuse (Research)
     - Pause / Resume
     - End session
   - Strictly hides when focus is inactive; zero allocations in `paintEvent`.
2. **Minimized HUD Overlay Enhancements** (`ui.py`):
   - Dynamic indicator pill on `_sentry_btn`:
     - Idle: `S`
     - Monitor active: `MON ●` (green when active, yellow when waiting for answer)
     - Focus active: `FOC mm:ss` (cyan countdown, pulsing red border during drift)
3. **Integration**:
   - `ui.py` `MainWindow` instantiates and wires `FloatingFocusCard` to `FocusState`.
   - `ui_overlay.py` integrates and exports `FloatingFocusCard`.

## 2. Graphify References & Hot Paths
- `core.sentry.focus.card.FloatingFocusCard`: Standalone floating card widget.
- `ui.MinimizedHudOverlay.update_sentry_indicator`: Updated to display `MON ●` and `FOC mm:ss`.
- `ui.MainWindow`: Instantiates `_focus_card` and forwards sentry state snapshots.
- `ui_overlay.TelemetryHUD`: Integrated `FloatingFocusCard` state updates.

## 3. Verification & Test Suite
- `tests/focus/test_focus_card.py`:
  - `test_card_does_not_spawn_when_inactive`: Verifies card stays hidden when focus is inactive.
  - `test_card_shows_and_formats_countdown_when_active`: Verifies card displays `24:31` and calculates progress correctly.
  - `test_card_drift_warning_state`: Verifies red drift warning state.
  - `test_clamp_to_screen_boundaries`: Verifies dragging outside desktop bounds is safely clamped.
  - `test_indicator_pill_states`: Verifies `MinimizedHudOverlay` updates across idle, monitor active (green/yellow), and focus countdown/drift states.
- `tests/test_minimized_hud_overlay.py`: All 6 tests pass.
- All 27 Focus tests and 17 Sentry tests passing cleanly.
