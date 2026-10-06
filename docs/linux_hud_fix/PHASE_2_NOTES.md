# Phase 2 Notes: Mini HUD Visibility Fix

## 1. Summary of Changes
- Refactored `MinimizedHudOverlay` initialization in `ui.py`:
  - Enforced `Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint`.
  - Confirmed absence of `Qt.WindowType.Tool` (which causes Linux window managers like Mutter/KWin to hide or drop unparented widgets).
  - Added dynamic tiling window manager floating hint: `if is_tiling_wm(): flags |= Qt.WindowType.Dialog`.
  - Added explicit transient parent linking in `begin_minimize_session()`:
    ```python
    if hasattr(self, "_main_window") and self._main_window:
        wh = self.windowHandle()
        m_wh = self._main_window.windowHandle()
        if wh is not None and m_wh is not None:
            wh.setTransientParent(m_wh)
    ```
  - Ensured initial geometry is strictly non-zero (`420x230`) and clamped to valid visible screen boundaries before calling `show()` and `raise_()`.

## 2. Graphify Nodes & Code Locations
- Mini HUD Class: `ui.MinimizedHudOverlay` (`ui.py:L4380`)
- Session Initiation: `ui.MinimizedHudOverlay.begin_minimize_session`
- Window Flags: `ui.MinimizedHudOverlay.setWindowFlags`
- Transient Parent: `QWindow.setTransientParent`

## 3. Measured Results & Verification
- Test `test_minimized_hud_overlay_flags_and_properties` in `tests/test_linux_hud_drag.py`: Verified `FramelessWindowHint` and `WindowStaysOnTopHint` are active, and `(flags & WindowType_Mask) != Tool`.
- Verified `begin_minimize_session()` maps window with valid geometry and sets transient parent without raising exceptions.
- Screenshot `docs/linux_hud_fix/screenshots/mini_hud_dragged_bottom_right.png` visually verified: all elements rendered, high contrast, zero clipping.
