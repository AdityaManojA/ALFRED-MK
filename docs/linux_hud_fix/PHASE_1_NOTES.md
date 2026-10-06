# Phase 1 Notes: Cross-Platform Drag Fix

## 1. Summary of Changes
- Created `ui/drag_handler.py` introducing `CrossPlatformDragHandler`.
- Implemented Wayland compositor delegation using `QWindow.startSystemMove()`.
- Implemented delta math `widget.move(current_global - drag_offset)` fallback for X11 (`xcb`), Windows (`win32`), and macOS (`cocoa`).
- Implemented `DRAG_THRESHOLD_PX = 5` to filter out accidental mouse clicks and jitters.
- Integrated `CrossPlatformDragHandler` into `BatGlobeOrb` (`ui.py:L4702`) and `MinimizedHudOverlay` (`ui.py:L4380`).
- Bound header restriction `MAX_HEADER_DRAG_Y_PX = 42` for `MinimizedHudOverlay` so clicking on transcript or controls does not initiate unwanted drags.

## 2. Graphify Nodes & Code Locations
- Drag Handler Module: `ui/drag_handler.py`
- Wayland Detection: `ui.drag_handler.is_wayland`
- Drag Handler Class: `ui.drag_handler.CrossPlatformDragHandler`
- Bat Globe Integration: `ui.BatGlobeOrb.mousePressEvent`, `mouseMoveEvent`, `mouseReleaseEvent`
- Mini HUD Integration: `ui.MinimizedHudOverlay.mousePressEvent`, `mouseMoveEvent`, `mouseReleaseEvent`

## 3. Measured Results & Verification
- Unit test `test_wayland_delegates_to_start_system_move` confirms that when `is_wayland() == True`, exceeding `DRAG_THRESHOLD_PX` triggers `windowHandle().startSystemMove()` with 0 `widget.move()` calls.
- Unit test `test_xcb_x11_applies_move_math` confirms that when `is_wayland() == False`, `widget.move()` is executed with correct delta coordinates.
- Unit test `test_drag_threshold_prevents_accidental_click_drag` confirms clicks within 5px threshold trigger click handlers (`_on_orb_clicked`) without triggering window dragging.
