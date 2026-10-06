# Phase 3 Notes: Globe Unsticking & Position Memory

## 1. Summary of Changes
- Replaced hardcoded center and bottom-right positions with unified persistence in `data/ui_state.json`.
- Implemented `calculate_top_right_quadrant(widget_w, widget_h, screen, margin_x=24, margin_y=48)` in `ui/drag_handler.py`:
  - On first boot without saved position, `BatGlobeOrb` and `MinimizedHudOverlay` position themselves in the top-right quadrant of `QScreen.availableGeometry()`.
  - On subsequent boots, coordinates are restored from `data/ui_state.json` (`window_key="bat_globe"` and `"mini_hud"`).
  - Maintained backward compatibility by falling back to legacy config files (`config/bat_globe_pos.json`, `config/hud_overlay_pos.json`) and dual-writing on save.
- Added tiling window manager support:
  - `is_tiling_wm()` detects i3, Sway, Hyprland, bspwm, dwm, awesome, xmonad.
  - Adds `Qt.WindowType.Dialog` flag to ensure the window manager floats the frameless widget rather than snapping it to a grid tile.

## 2. Graphify Nodes & Code Locations
- Position Persistence Utilities: `ui.drag_handler.load_window_position`, `ui.drag_handler.save_window_position`
- Top-Right Calculation: `ui.drag_handler.calculate_top_right_quadrant`
- Tiling WM Detection: `ui.drag_handler.is_tiling_wm`
- Bat Globe Position Handlers: `ui.BatGlobeOrb._load_position`, `ui.BatGlobeOrb._save_position`
- Mini HUD Position Handlers: `ui.MinimizedHudOverlay._load_position`, `ui.MinimizedHudOverlay._save_position`

## 3. Measured Results & Verification
- Unit test `test_save_and_load_window_position`: coordinates saved via `save_window_position` are atomically written and read back matching exact pixel coordinates.
- Unit test `test_first_boot_top_right_quadrant_default`: first boot loads top-right quadrant (`bounds.right() - width - 24`, `bounds.top() + 48`).
- Screen boundary clamping prevents windows from spawning off-screen on multi-monitor or resized displays.
- Screenshot `docs/linux_hud_fix/screenshots/globe_dragged_left.png` visually verified: moved from default quadrant to custom position on the left.
