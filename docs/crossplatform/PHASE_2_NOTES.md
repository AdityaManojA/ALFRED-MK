# ALFRED-MK-V: Cross-Platform Parity (macOS + Linux)
## Phase 2 Implementation Notes: Visual HUD Parity

**Corpus & Graph References:**
- `core/hud_video/surface.py` (`HudVideoSurface`)
- `core/hud_video/layering.py` (`raise_overlay`, `Z_VISUAL_HUD`, `Z_SETTINGS_MODAL`)
- `core/hud_video/transport.py` (`VideoState`, `VideoStatus`)

---

## 1. Multimedia Decode & Compatibility Matrix

- **macOS:** AVFoundation backend natively decodes VP9, H.264, and Opus audio in WebM containers without supplementary codecs.
- **Linux:** Requires GStreamer plugins (`gstreamer1.0-plugins-good`, `gstreamer1.0-plugins-bad`, `gstreamer1.0-libav`). 
  - Added GStreamer verification and graceful error dispatch reporting on Linux if multimedia pipeline encounters unsupported codec formats.

---

## 2. Window Layering & Compositor Independence

- Child widget structure inside `HudVideoSurface` guarantees that controls, headers, toasts, and overlays paint cleanly above `QVideoWidget` across Windows DWM, macOS Quartz Compositor, and Linux Wayland/X11 Compositors.
- Translucency flags (`WA_TranslucentBackground`) are cleanly scoped to floating top-level Tool windows (`_HudOverlay`), preventing black box render clipping over hardware-accelerated video surfaces.
