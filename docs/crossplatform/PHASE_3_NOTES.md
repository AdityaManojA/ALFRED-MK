# ALFRED-MK-V: Cross-Platform Parity (macOS + Linux)
## Phase 3 Implementation Notes: Minimised HUD Parity

**Corpus & Graph References:**
- `ui.py` (`MinimizedHudOverlay`, lines 3883–4185)
- `config/hud_overlay_pos.json` (Position persistence)

---

## 1. Window Flags & Always-On-Top Parity

- **Window Flags:**
  ```python
  Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
  ```
- **macOS:** Frameless translucent window stays visible and draggable over standard desktop workspaces.
- **Linux:** X11 & Wayland compositors recognize `WindowStaysOnTopHint`. Tiling window managers (i3, sway, bspwm) can float the mini HUD using standard WM rules:
  ```text
  for_window [class="alfred" instance="minimizedHudOverlay"] floating enable
  ```

---

## 2. Geometry Clamping & Multi-Monitor Support

- Positions are clamped strictly within `QScreen.availableGeometry()`.
- DPI scaling (`devicePixelRatio`) and multi-monitor setups correctly resolve via `QApplication.screenAt(position)` or primary screen fallback.
- Minimised controls (Sentry menu, FOCUS timer, MON status) and transcript stream operate identically across all three platforms.
