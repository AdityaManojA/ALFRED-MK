# Remote Uplink Popup: Batcomputer-Grade UI Overhaul Notes
Date: 2026-09-29

## 1. Graphify Nodes & Code Locations
- `ui_remotekeyoverlay` (`ui.py:L6983`): RemoteKeyOverlay tactical pairing popup.
- `ui_mainwindow_open_remote` (`ui.py:L9562`): MainWindow trigger for remote overlay.
- `ui_hudoverlay` (`ui.py:L6208`): Base class for floating HUD panels.
- `ui_class_c` (`ui.py:L727`): Palette and chromatic tokens.
- `ui_apply_ui_accent` (`ui.py:L885`): Live theme applicator (Dossier, Bane, Batman Beyond, custom).
- `ui_retheme_all_widgets` (`ui.py:L958`): Live palette mapper for all active widgets.
- `tests_test_remote_key_overlay` (`tests/test_remote_key_overlay.py`): Test suite.

---

## 2. Investigation Checklist & Preserved Capabilities

All fields, actions, and security contracts have been preserved and enhanced:
1. **QR Code**:
   - Fixed size (176×176), high-contrast black modules on solid white for dependable optical camera scanning across all lighting conditions.
   - Housed inside a dark CRT chassis (`QFrame#qrChassis`) with precision corner brackets and subtle theme-linked glow.
   - QR modules are intentionally kept untinted.
2. **LAN Coordinates**:
   - Styled tactical row with clickable hyperlink (`setOpenExternalLinks(True)` and `LinksAccessibleByMouse`).
   - Copy button `⎘` with brief `COPIED ✓` visual flash (`UPLINK_COPY_FLASH_MS = 1400ms`).
3. **Localhost Dashboard Link**:
   - Styled tactical row with direct browser loopback link and copy affordance.
4. **Manual Entry Coordinates**:
   - Plain host:port coordinates (`IP:PORT`) formatted for manual typing on devices without auto-login tokens.
5. **Access Credential**:
   - Monospaced credential pill (`QFrame#keyChassis`) with copy affordance and high-contrast letter-spacing.
6. **Primary Action**:
   - `↗ OPEN IN BROWSER` angular tactical button.
7. **Secondary Action**:
   - `NEW KEY` tactical button (regenerates session key via backend without losing connection).
8. **Dismiss Controls**:
   - `DISMISS` ghost button + top-right corner bracket `✕` close button.
9. **Telemetry Handshake**:
   - `mark_connected()` slot transitions to green verified state (`UPLINK ACTIVE`, `✓`, `SECURE HANDSHAKE VERIFIED`).

---

## 3. Design & Architecture Details

- **Chassis & Visual Language**:
  - Subclassed `_HudOverlay` (inheriting ghosting prevention upon hide/close).
  - Frameless translucent dark obsidian backing (`C.BG` with alpha 246).
  - 4-px horizontal CRT scanline texture rendered in `paintEvent` without per-frame allocations.
  - Precision angular corner brackets (12px length, 1.5px width) drawn in `C.PRI` theme accent.
  - Draggable via header strip (0–48px region).
- **Named Constants**:
  ```python
  UPLINK_OVERLAY_W: int = 500
  UPLINK_OVERLAY_H: int = 620
  UPLINK_QR_SIZE: int = 176
  UPLINK_CORNER_BRACKET_LEN: int = 12
  UPLINK_CORNER_BRACKET_WIDTH: float = 1.5
  UPLINK_COPY_FLASH_MS: int = 1400
  ```
- **Live Theme Retinting**:
  - Palette tokens consumed: `C.BG`, `C.PANEL2`, `C.BORDER`, `C.BORDER_A`, `C.BORDER_B`, `C.PRI`, `C.PRI_DIM`, `C.PRI_GHO`, `C.ACC`, `C.GREEN`, `C.RED`, `C.TEXT`, `C.TEXT_MED`, `C.TEXT_DIM`.
  - When switching themes (Default Dossier → Bane → Batman Beyond), `_apply_theme_styles()` and `retheme_all_widgets()` retint all buttons, frames, labels, and corner brackets immediately.

---

## 4. Verification Matrix

| Environment / Verification Check | Status | Details |
| :--- | :--- | :--- |
| **All 5 pairing values populated** | **PASS** | QR, LAN URL, Localhost URL, Manual Host:Port, Access Key |
| **Hyperlinks accessible & open external** | **PASS** | Verified mouse click and external browser routing |
| **Tactical copy buttons & flash feedback** | **PASS** | Copies exact string to clipboard; shows `COPIED ✓` for 1.4s |
| **`↗ OPEN IN BROWSER` trigger** | **PASS** | Opens default web browser with auto-login token |
| **`NEW KEY` refresh contract** | **PASS** | Regenerates token, updates QR and text fields seamlessly |
| **Live theme retinting** | **PASS** | Retints to active theme palette while QR stays high-contrast |
| **Windows 10/11 Live Check** | **PASS** | Verified on Windows host |
| **Linux (X11 & Wayland) Live Check** | **NOT RUN / BLOCKED** | No Linux display server in local sandbox environment |
| **macOS Live Check** | **NOT RUN / BLOCKED** | No Darwin host in local sandbox environment |
