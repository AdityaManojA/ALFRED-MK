# Minimized HUD Linux Lifecycle & Visibility Reconnaissance Notes
Date: 2026-09-29

## 1. Graphify Nodes & Code Locations
- `ui_minimizedhudoverlay` (`ui.py:L3716`): Minimized transcript overlay widget (`MinimizedHudOverlay`).
- `ui_mainwindow_changeevent` (`ui.py:L10383`): MainWindow `changeEvent` handling `WindowStateChange`.
- `ui_minimizedhudoverlay_begin_minimize_session` (`ui.py:L3898`): Overlay reveal logic.
- `ui_minimizedhudoverlay_hide_overlay` (`ui.py:L3904`): Overlay hide logic.
- `ui_minimizedhudoverlay_update_sentry_indicator` (`ui.py:L3855`): Sentry state indicator updating.
- `ui_mainwindow_apply_sentry_snapshot` (`ui.py:L10221`): Snapshot routing to HUD overlay.
- `tests_test_minimized_hud_overlay_testminimizedhudoverlay` (`tests/test_minimized_hud_overlay.py`): Test suite.

---

## 2. Phase 0 Diagnostic Findings

### 1. Overlay Ownership and Creation Path
- `MinimizedHudOverlay` is instantiated once during `MainWindow.__init__` (`ui.py:L7477`):
  ```python
  self._hud_overlay = MinimizedHudOverlay(self, self._log_sig, self._assistant_name)
  ```
- `MainWindow` retains a strong reference in `self._hud_overlay`.
- In `MinimizedHudOverlay.__init__`, `super().__init__(None)` is passed. It is an unparented `QWidget`.
- It sets window flags:
  ```python
  self.setWindowFlags(
      Qt.WindowType.Window
      | Qt.WindowType.FramelessWindowHint
      | Qt.WindowType.WindowStaysOnTopHint
  )
  ```
- Lifetime methods:
  - `begin_minimize_session()`: clears `_user_closed`, resets window state to `WindowNoState`, calls `show()`, `raise_()`.
  - `hide_overlay()`: saves position and calls `hide()`.
  - `closeEvent()`: if not shutting down, marks `_user_closed = True`, calls `hide()`, and ignores the event to preserve instance.
  - `shutdown()`: marks `_shutting_down = True`, saves position, and accepts `close()`.

### 2. Minimize Triggers: Main App vs Linux Window Manager
- **Window Manager Title Bar Minimize**: Triggers `WindowStateChange` on `MainWindow`. `MainWindow.changeEvent(event)` detects `self.isMinimized()` and calls `self._hud_overlay.begin_minimize_session()`. When restored, `MainWindow.changeEvent(event)` detects not minimized and calls `self._hud_overlay.hide_overlay()`.
- **Main HUD Minimize Control**: When the main window is minimized, `isMinimized()` becomes `True` and invokes `begin_minimize_session()`.

### 3. Qt Events & Signals Ordering on Linux (X11 & Wayland)
- On Linux (especially with X11 window managers like Mutter/KWin/XFWM and Wayland compositors):
  1. Window minimizing does not always hide child transient windows, but unparented windows with `Qt.WindowType.Window` need explicit `show()`, `raise_()`, and on Wayland need proper positioning before/after mapping.
  2. Calling `self.show()` without `Qt.WidgetAttribute.WA_ShowWithoutActivating` on some Linux compositors causes focus fights or fails to restack if the window manager minimizes all application windows when the main window minimizes if they belong to the same process group without proper flags.
  3. Adding `self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)` ensures the overlay appears unobtrusively without stealing keyboard focus or causing the window manager to immediately re-focus the minimized main window.
  4. Positioning in `_load_position`: If `QApplication.screenAt(position)` or `primaryScreen()` has not finished initial geometry calculation or if multi-monitor available geometry has negative offsets on X11, `_load_position` must clamp properly against `availableGeometry()`.

### 4. Window Type & Compositor Considerations
- **Session Type Detection**:
  - `WAYLAND_DISPLAY` set -> Wayland session.
  - `DISPLAY` set without `WAYLAND_DISPLAY` -> X11 session.
- **Translucency (`WA_TranslucentBackground`)**:
  - Requires an active composite manager on Linux (e.g. Compton, Picom, Mutter, KWin, or Wayland native compositor).
  - If no compositor is running on legacy X11, translucent backgrounds may render black. The CSS fallback `#overlayShell { background: rgba(3, 14, 26, 238); ... }` ensures solid visual readability regardless.
- **Window Flags**:
  - `Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint` is cross-platform and supported across Windows, macOS, and Linux X11/Wayland.
  - `Qt.WidgetAttribute.WA_ShowWithoutActivating` prevents activation focus churn.

### 5. MONITOR & FOCUS State Synchronization
- When `begin_minimize_session()` is called, it should immediately fetch the latest `SentrySnapshot` from `get_sentry_mode_manager().get_snapshot()` and call `self.update_sentry_indicator(...)` so the mini HUD doesn't wait for a subsequent status event to show active monitor/focus pills.

---

## 3. Proposed Fix Strategy

1. **Overlay Visibility & Activation**:
   - In `MinimizedHudOverlay.__init__`, set `self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)` so displaying the mini HUD never steals focus or triggers window-manager activation bounce.
   - In `begin_minimize_session()`:
     - Check `if self._user_closed: return` so a user-dismissed overlay during the current minimize session is respected if triggered via spurious window state events, but refreshed upon a new minimize transition.
     - Call `self._load_position()` on restore/show to adapt to dynamic display/DPI changes.
     - Immediately sync current Sentry snapshot (`mgr.get_snapshot()`).
     - Call `self.show()` and `self.raise_()`.

2. **Screen Geometry Safety**:
   - Improve `_load_position()` in `MinimizedHudOverlay` to safely handle multi-monitor virtual geometry and screen change events across Linux X11/Wayland.

3. **Lifecycle & Signal Safety**:
   - Ensure `_apply_sentry_snapshot` safely passes the full snapshot to `_hud_overlay` under an exception boundary.
   - Retain full compatibility with Windows and macOS.

---

## 4. Implementation Details
- In `MinimizedHudOverlay.__init__` (`ui.py`):
  - Added `self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)`.
  - Retained `Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint`.
- In `MinimizedHudOverlay.begin_minimize_session()`:
  - Invokes `self._load_position()` and `self._sync_sentry_state()` to immediately populate active Sentry monitor/focus states and accurate screen geometry before calling `show()` and `raise_()`.
- In `tests/test_minimized_hud_linux.py`:
  - Added unit test suite validating window flags, non-activating attribute, show/hide minimize lifecycle, duplicate prevention, and multi-monitor screen clamping.

---

## 5. Verification Matrix & Environment Status

| Environment / Check | Status | Details |
| :--- | :--- | :--- |
| **Linux (X11 / Wayland session detection)** | **DOCUMENTED** | `WAYLAND_DISPLAY` -> Wayland, `DISPLAY` -> X11. `WA_ShowWithoutActivating` ensures non-stealing top-level presentation |
| **Linux X11 / Wayland live run** | **NOT RUN / BLOCKED** | Local execution environment is Windows-only; no Linux/X11/Wayland display server installed in environment |
| **Overlay creation & lifetime retention** | **PASS** | Retained on `MainWindow._hud_overlay`, unparented top-level |
| **Minimize → Mini HUD visible & state synced** | **PASS** | `begin_minimize_session()` updates position, Sentry status, and calls `show()`/`raise_()` |
| **Restore → Mini HUD dismissed** | **PASS** | `hide_overlay()` saves position and calls `hide()` |
| **Repeated minimize/restore cycles** | **PASS** | No duplicate widgets or dangling connections |
| **Windows compatibility preserved** | **PASS** | Unchanged Windows presentation and persistence contracts |

