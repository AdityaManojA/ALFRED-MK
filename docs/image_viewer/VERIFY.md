# Image Viewer v2 Live Verification Checklist

This document details the live verification procedure for the ALFRED Image Viewer v2 (LAZY + FIT + FETCH).

---

## 1. Clean Boot with No Viewer
- [ ] Launch ALFRED: `python main.py`
- [ ] Verify HUD initializes with no traceback and no crash at `set_media_arbiter`.
- [ ] Confirm no image viewer window appears on screen at startup.
- [ ] Confirm `core.registry.lookup("image_viewer")` is `None` (verified by `tests/test_lazy_viewer.py::test_clean_boot_constructs_no_viewer`).
- [ ] Verify idle CPU is ~0% and no memory allocated for image buffers before first use.

---

## 2. Fetch and Fit for Multiple Aspect Ratios
- [ ] **Landscape**: Issue voice command *"show me a reference image of a Tesla Cybertruck"*.
  - [ ] ALFRED displays toast: `Reference image: <host>` with no voice announcement.
  - [ ] Window opens cleanly centered on HUD display.
  - [ ] Image fits within 85% screen bounds (`VIEWER_MAX_SCREEN_FRAC = 0.85`) with exact aspect ratio preserved and no cropping.
  - [ ] Bottom caption strip displays `◈  <HOST>` and image resolution `W × H px`.
- [ ] **Portrait**: Issue command *"show me a reference image of the Eiffel Tower"*.
  - [ ] Image scales to available vertical geometry.
  - [ ] No vertical overflow off-screen.
- [ ] **Square / Small**: Issue command displaying a square image.
  - [ ] Fits at native resolution without blurring or over-expansion.
  - [ ] Meets minimum dimension `VIEWER_MIN_PX = 240`.
- [ ] **High-DPI / 8K**:
  - [ ] Display scales accurately via `QPixmap.setDevicePixelRatio`.
  - [ ] High-resolution images are downscaled at decode time without UI stutter.

---

## 3. Candidate Cycling and Dismissal
- [ ] **Cycle Next**: Say *"another one"* or *"next"*, or click `[❯]` or press `[N]`.
  - [ ] Viewer transitions to next candidate image without window flicker.
  - [ ] Caption counter updates: `◈  <HOST>  [2/N]`.
- [ ] **Cycle Previous**: Say *"previous image"* or click `[❮]` or press `[P]`.
  - [ ] Viewer returns to candidate 1 (`[1/N]`).
- [ ] **Close Viewer**:
  - [ ] Press `[Esc]`, click `[✕]`, or say *"close the image"*.
  - [ ] Viewer window hides immediately.
  - [ ] Canvas pixmap and decoded image bytes are freed immediately (`_canvas.clear()`).
  - [ ] Memory drops back to idle baseline.
- [ ] **No Auto-Restore**: Restart ALFRED; verify closed viewer does not auto-open on next boot.

---

## 4. Layering & Airspace Separation
- [ ] Open the Image Viewer with an image.
- [ ] Click Settings cog / open Settings dialog.
  - [ ] Settings modal (`Z_SETTINGS_MODAL = 40`) appears strictly above the image viewer (`Z_IMAGE_VIEWER = 15`).
- [ ] Trigger an alert or toast notification.
  - [ ] Dropdown card and toast (`Z_DROPDOWN_CARD_TOAST = 30`) render in front of the image viewer.
- [ ] Click and drag viewer header to reposition; verify smooth translation.

---

## 5. Visual HUD Coexistence
- [ ] Start video playback in Visual HUD (e.g. *"watch Dune trailer in the app"*).
- [ ] While video is playing, request a reference image: *"show me a reference image of Mars"*.
  - [ ] Video playback continues smoothly without pausing, muting, or interruption.
  - [ ] Image viewer window sits comfortably alongside or above HUD background.
  - [ ] Voice commands for video transport (*"pause"*, *"resume"*, *"close the visual hud"*) route strictly to the video player, not the image viewer.
- [ ] Closing either player does not affect the state of the other.

---

## 6. Failure & Privacy Enforcement
- [ ] **Query Failure**: Request a nonsensical subject: *"show me a reference image of xyz999nonexistent"*.
  - [ ] ALFRED speaks: *"Couldn't find one, sir."*
  - [ ] No empty or blank window is shown.
- [ ] **Privacy Audit**:
  - [ ] Inspect log output (`tail -f`).
  - [ ] Confirm only domain hosts (e.g. `api.openverse.org`, `upload.wikimedia.org`) appear.
  - [ ] Confirm no signed tokens, URL paths, query parameters, or personal file directory names leak into logs, window titles, or state.

---

## 7. Performance & Resource Footprint
- [ ] **Pre-paint allocations**: Verify zero allocations in `paintEvent` (all pens, brushes, fonts, and pixmaps prescaled on resize/load).
- [ ] **Idle CPU / RAM**:
  - [ ] Pre-use: 0% CPU, 0 MB viewer overhead.
  - [ ] In-use: Smooth 60 FPS repaint during window drag.
  - [ ] Post-close: Memory freed, 0% CPU.
