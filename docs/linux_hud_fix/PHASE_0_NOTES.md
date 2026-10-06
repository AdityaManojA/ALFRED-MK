# Phase 0 Reconnaissance Notes: Linux HUD Visibility & Drag Fix

## 1. Main HUD & Bat Globe
- **Class & File:** `BatGlobeOrb` in `ui.py` (L4702), Graphify Node: `ui_batglobeorb`. Main tactical window is `MainWindow` in `ui.py` (L7303), Graphify Node: `ui_mainwindow`.
- **Window Flags Currently Set on BatGlobeOrb:**
  ```python
  self.setWindowFlags(
      Qt.WindowType.Window
      | Qt.WindowType.FramelessWindowHint
      | Qt.WindowType.WindowStaysOnTopHint
  )
  ```
- **Widget Attributes:**
  - `WA_TranslucentBackground = True`
  - `WA_ShowWithoutActivating = False`
- **Tiling WM & Wayland Behavior:**
  - On Wayland and tiling window managers (i3, Sway, Hyprland), unhinted frameless `Qt.WindowType.Window` instances are placed in the center grid or forced into tiled mode.
  - Client-side calls to `self.move()` are rejected by the Wayland compositor, leaving the orb stuck in the center of the screen.

## 2. Minimised HUD Overlay
- **Class & File:** `MinimizedHudOverlay` in `ui.py` (L4380), Graphify Node: `ui_minimizedhudoverlay`.
- **Window Flags Currently Set:**
  ```python
  self.setWindowFlags(
      Qt.WindowType.Window
      | Qt.WindowType.FramelessWindowHint
      | Qt.WindowType.WindowStaysOnTopHint
  )
  ```
- **Widget Attributes:**
  - `WA_TranslucentBackground = True`
  - `WA_ShowWithoutActivating = True`
- **Ownership & Lifecycle:**
  - Separate top-level window instantiated with `super().__init__(None)` (unparented `QWidget`).
  - Shown via `begin_minimize_session()` (`show()`, `raise_()`) triggered by `MainWindow.changeEvent` upon `QEvent.Type.WindowStateChange` when `self.isMinimized()` is `True`.
  - Hidden via `hide_overlay()` (`hide()`, `_save_position()`) when `MainWindow` is restored or closed.
- **Root Cause of Non-Visibility on Linux:**
  - Many Linux compositors (especially GNOME Mutter and KDE KWin under Wayland) drop or suppress unparented `Qt.WindowType.Window` windows created with `WA_ShowWithoutActivating` when the main window minimizes.
  - Without an explicit transient parent link or valid pre-map geometry, the compositor refuses to stack or map the subsurface, or leaves it at (0, 0) off-screen.

## 3. Current Drag Implementation
- **MinimizedHudOverlay (ui.py:L4649-L4666):**
  ```python
  def mousePressEvent(self, event) -> None:
      if event.button() == Qt.MouseButton.LeftButton and event.position().y() <= 42:
          self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
          event.accept()
          return
      super().mousePressEvent(event)

  def mouseMoveEvent(self, event) -> None:
      if event.buttons() & Qt.MouseButton.LeftButton and self._drag_offset is not None:
          self.move(event.globalPosition().toPoint() - self._drag_offset)
          event.accept()
          return
      super().mouseMoveEvent(event)
  ```
- **BatGlobeOrb (ui.py:L4848-L4876):**
  ```python
  def mouseMoveEvent(self, e: QMouseEvent):
      if e.buttons() & Qt.MouseButton.LeftButton and self._press_pos is not None:
          cur_pos = e.globalPosition().toPoint()
          if (cur_pos - self._press_pos).manhattanLength() > 4:
              self._is_dragging = True
              delta = cur_pos - self._last_drag_pos
              self.move(self.pos() + delta)
              self._last_drag_pos = cur_pos
      super().mouseMoveEvent(e)
  ```
- **Diagnosis:** Both classes use manual `self.move(...)` coordinate math. Neither uses `QWindow.startSystemMove()`.

## 4. Display Server & Wayland Security Barrier
- **Detection:** `QGuiApplication.platformName()`. Returns:
  - `"wayland"` (or `"wayland-egl"`) on Wayland
  - `"xcb"` on X11
  - `"windows"` on Windows
  - `"cocoa"` on macOS
- **Wayland Constraint:**
  - Under Wayland xdg-shell protocol, client applications are forbidden from positioning toplevel windows on the desktop via global coordinates (`self.move(x, y)`).
  - Attempting to drag via `self.move()` in `mouseMoveEvent` does nothing on Wayland.
  - The compositor requires `self.windowHandle().startSystemMove()` to delegate the drag to the display server compositor.
  - On X11 (`xcb`), `self.move()` math is reliable.

## 5. Geometry & Position Persistence
- **Current Position Logic:**
  - `MinimizedHudOverlay` reads `config/hud_overlay_pos.json`.
  - `BatGlobeOrb` reads `config/bat_globe_pos.json`.
  - Default fallbacks calculate bottom-right (`bounds.right() - width - 28`).
- **Target Specification:**
  - Standardize persistence across both floating widgets into `data/ui_state.json`.
  - On first boot: Position in the top-right quadrant (`bounds.right() - width - 24`, `bounds.top() + 48`).
  - Subsequent boots: Restore from `data/ui_state.json`.
  - On close/hide/minimize: Persist coordinates immediately.

---

## Exact Files to Touch in Next Phases
1. `ui/drag_handler.py` (New): Reusable `CrossPlatformDragMixin` with Wayland `startSystemMove()` and X11/Win32 fallback math.
2. `ui.py`:
   - Integrate `CrossPlatformDragMixin` into `BatGlobeOrb` and `MinimizedHudOverlay`.
   - Fix window flags and transient parent for `MinimizedHudOverlay`.
   - Update position initialization and persistence in `data/ui_state.json`.
3. `tests/test_linux_hud_drag.py` (New): Unit tests for drag handler platform branching, Wayland delegation, and coordinate persistence.
