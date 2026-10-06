# Linux HUD Visibility & Drag Fix: Verification Matrix (ALFRED-MK-V)

Date: 2026-10-07  
Platform: Cross-Platform (Linux X11/Wayland, Windows 11 host)  

## Verification Checklist

| Check | Result | Evidence / Details |
|---|---|---|
| Display Server Detection (`is_wayland()`) | PASS | Tested with `QGuiApplication.platformName() == "wayland"` and `"xcb"` in `tests/test_linux_hud_drag.py`. |
| Tiling Window Manager Detection (`is_tiling_wm()`) | PASS | Detects `i3`, `sway`, `hyprland`, `bspwm`, `dwm`, `awesome`, `qtile`. |
| Wayland Drag Native Delegation (`startSystemMove()`) | PASS | Exceeding `DRAG_THRESHOLD_PX` (5px) calls `windowHandle().startSystemMove()` and skips client-side `widget.move()`. |
| X11 / Win32 / macOS Drag Math (`widget.move()`) | PASS | Exceeding 5px applies delta offset `widget.move()`. Accidental jitter under 5px is ignored. |
| Mini HUD Visibility (Linux Compositors) | PASS | Configured with `Window | FramelessWindowHint | WindowStaysOnTopHint` (`Dialog` on tiling WMs). Excluded `Tool` flag. Links transient parent `windowHandle().setTransientParent()` on minimize. |
| Globe Position Initialization (Top-Right Default) | PASS | First boot without saved state calculates top-right quadrant (`bounds.right() - width - 24`, `bounds.top() + 48`). |
| Position Persistence (`data/ui_state.json`) | PASS | Position saved on mouse release, hide, close, and shutdown. Restored on subsequent boots. Clamped to desktop available geometry. |
| Dual-Write Legacy Compatibility | PASS | Dual-writes to `config/bat_globe_pos.json` and `config/hud_overlay_pos.json` for backwards compatibility. |
| Visual Inspection — Globe Dragged Left | PASS | Screenshot: `docs/linux_hud_fix/screenshots/globe_dragged_left.png`. 520x520 high-DPI capture; complete vector wireframe, zero element clipping. |
| Visual Inspection — Mini HUD Dragged Bottom-Right | PASS | Screenshot: `docs/linux_hud_fix/screenshots/mini_hud_dragged_bottom_right.png`. 840x460 high-DPI capture; glowing border, controls strip, header font, zero clipping. |
| Idle CPU & Overhead | PASS | Drag handler is reactive to mouse events only; adds zero background threads or timers. |

---

## Test Execution Summary
All 27 relevant HUD and drag tests passing:
- `tests/test_linux_hud_drag.py` (9 tests)
- `tests/test_bat_globe_orb.py` (5 tests)
- `tests/test_minimized_hud_overlay.py` (5 tests)
- `tests/test_minimized_hud_linux.py` (8 tests)
