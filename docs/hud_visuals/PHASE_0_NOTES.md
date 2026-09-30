# ALFRED-MK-V: HUD Visuals v1 — Phase 0 Reconnaissance Notes

## 1. Graphify Nodes & Code Locations
- **HUD Canvas & Centerpiece**: `HudCanvas` ([ui.py:1320](file:///d:/Projects/Alfred-Mark-V/ui.py#L1320)), `HudCanvas.paintEvent` ([ui.py:2608](file:///d:/Projects/Alfred-Mark-V/ui.py#L2608)), `_paint_3d_vector_globe` ([ui.py:2058](file:///d:/Projects/Alfred-Mark-V/ui.py#L2058)), `_paint_globe_waveforms` ([ui.py:2251](file:///d:/Projects/Alfred-Mark-V/ui.py#L2251)).
- **Left Panel Scanner Widgets (Current Slots)**:
  - Slot 1: `CRTReconWidget` ([ui.py:2703](file:///d:/Projects/Alfred-Mark-V/ui.py#L2703)) — Height: 132px.
  - Slot 2: `BiometricFingerprintWidget` ([ui.py:2783](file:///d:/Projects/Alfred-Mark-V/ui.py#L2783)) — Height: 115px.
  - Slot 3: `WireframePoseWidget` ([ui.py:2872](file:///d:/Projects/Alfred-Mark-V/ui.py#L2872)) — Height: 98px.
  - Container: `_build_left_panel` ([ui.py:9050](file:///d:/Projects/Alfred-Mark-V/ui.py#L9050)) with fixed width `_LEFT_W = 280px`.
- **Theming System**:
  - Catalog: `core.ui.themes.catalog` (`DEFAULT_BATCAVE`, `BANE_MODE`, `BATMAN_BEYOND`, `JOKER`, `RIDDLER`, `MR_FREEZE`, `TWO_FACE`, `CATWOMAN`, `ARKHAM`, `WATCHTOWER`).
  - Schema: `core.ui.themes.schema.PaletteDefinition` (tokens: `bg`, `panel`, `panel2`, `panel_bg`, `border`, `border_b`, `border_a`, `pri`, `pri_dim`, `pri_gho`, `acc`, `acc2`, `green`, `green_d`, `red`, `muted`, `muted_c`, `text`, `text_dim`, `text_med`, `text_bright`, `white`, `dark`, `bar_bg`).
  - Runtime apply & notifications: `core.ui.themes.apply.ThemeChrome`, `ThemeChrome.add_listener()`, `apply_theme()`.
- **System Metrics & Data Sources**:
  - `actions/system_monitor.py` (`get_system_status()`, `watch_process_tree()`).
  - `core/sentry/state.py` (`SentrySnapshot`, `FocusState`, `MonitorState`).

---

## 2. Reconnaissance Findings

### 1. Slots Structure & Current Layout
Currently in `ui.py` (`_build_left_panel`), three separate standalone `QWidget` classes (`CRTReconWidget`, `BiometricFingerprintWidget`, `WireframePoseWidget`) are stacked vertically in a `QVBoxLayout` inside a `QScrollArea`.
- In HUD Visuals v1, we unify these three scanner slots with a dedicated slot container / manager host (`SlotHostWidget`) where:
  - **Slot 1 (Recon)**: 132px height.
  - **Slot 2 (Gauge)**: 115px height.
  - **Slot 3 (Figure)**: 98px height.
  - **Developer Data Grid (2×2)**: Located directly underneath Slot 3, ahead of the MetricBars or replacing the static labels.
- Each slot dynamically binds an active `SlotVisual` from `core/hud/visuals/registry.py` matching the current theme ID (`dossier`, `vector`, `beyond`, `joker`, `riddler`, `mr_freeze`, `harvey_two_face`, `catwoman`, `arkham`, `watchtower`).

### 2. Themes & Palette Constants
There are 10 distinct themes registered in `core/ui/themes/catalog.py`:
1. `dossier` (Default Batcave — #8e9bff)
2. `vector` (Bane Mode — #a8ff3e)
3. `beyond` (Batman Beyond — #ff0037)
4. `joker` (Joker — #b537f2)
5. `riddler` (Riddler — #00e676)
6. `mr_freeze` (Mr. Freeze — #00f5d4)
7. `harvey_two_face` (Harvey Two-Face — #e0a96d)
8. `catwoman` (Catwoman — #9d4edd)
9. `arkham` (Arkham Asylum — #588157)
10. `watchtower` (Watchtower Omni — #00b4d8)

Theme changes notify all registered listeners via `ThemeChrome.add_listener()`.

### 3. HUD Tick & Timing Architecture
- In `HudCanvas`, animation steps are governed by `_step()`, driven by a 16ms timer (`QTimer(self).start(16)`), with rendering throttled by `_paint_tick` (idle frames throttle to ~20 Hz / ~17 FPS).
- All visuals must use `dt = now - last_t` derived from `time.monotonic()` to maintain FPS-independent motion.
- Zero per-frame allocations: all pens, brushes, precomputed trig tables, vectors, and bounding boxes are built in `prepare(palette, rect)`.

### 4. Central Visualizer Reskinning
- The centerpiece globe in `HudCanvas` is painted by `_paint_3d_vector_globe` and `_paint_globe_waveforms`.
- The viseme/avatar path (`_visemes`, `_vis_open`, `_vis_wide`, `_vis_close`, `_vis_level`) modulates the amplitude and harmonic shape.
- Reskinning hooks into the rendering parameters (ring geometries, color ramps, particle styles, pulse dynamics) via `CentralSkin` in `core/hud/visuals/central.py` **without altering the phoneme/viseme schedule or lip-sync arithmetic**.

### 5. Developer Data Grid (2×2)
- **GIT**: Branch + dirty status (`main • 3 modified` / `clean` / `no repo`) polled via subprocess every 15s (`GIT_TIMEOUT_S = 2`).
- **PORTS**: Active listening localhost ports (`11434 · 8000 · 1234`) polled every 20s via `psutil.net_connections('inet')` / cross-platform backend.
- **TOP PROC**: Top non-system process by CPU/Memory (`chrome.exe • 1.4 GB`) polled every 5s via cached sampler.
- **SESSION**: Elapsed time + tokens (`02:14:07 • 48.2k tok`) updated at 1s intervals.
- All background grid sampling runs on a single background worker thread, updating cached display strings so the GUI repaints only on value divergence.

### 6. Mono Fonts & Text Helpers
- Uses `mono_font(size, weight, letter_spacing)` and `tech_font(size, weight, letter_spacing)` defined in `ui.py`.
- Pre-cached QFont objects stored in `prepare()` to satisfy zero-allocation paint rules.

---

## 3. Proposed Module Layout
```
core/hud/
├── visuals/
│   ├── __init__.py
│   ├── base.py          # SlotVisual ABC, Signals dataclass, guard, precomputed trig table (TRIG_STEPS=512)
│   ├── registry.py      # (theme_id, slot) -> SlotVisual class resolution + fallback
│   ├── primitives.py    # Wireframe3D, RadarSweep, BarArray, WaveTrace, SilhouetteInterp
│   ├── central.py       # CentralSkin definitions & color/geometry adapters for reactor globe
│   └── slots/
│       ├── __init__.py
│       ├── batcave.py   # Default Batcave slot set (Radar, Audio Spectrum, Batwing)
│       ├── catwoman.py  # Sonar Grid, Lockpick Waveform, Feline Silhouette
│       ├── bane.py      # Venom Chamber, Dosage Regulator, Mask Schematic
│       ├── beyond.py    # Retinal HUD, ICE Intrusion, Chrome Avatar
│       ├── freeze.py    # Cryo Core, Thermal Column, Coolant Loop
│       ├── joker.py     # Card Scatter, Laugh Waveform, Grinning Mask
│       ├── two_face.py  # Split Mirror, Silver Dollar, Bisected Figure
│       ├── arkham.py    # Cell Floorplan, EEG Brainwave, Vitals Silhouette
│       └── watchtower.py# Arc Flux Ring, Power Output, Holo-Man Diagnostic
└── datagrid/
    ├── __init__.py
    ├── grid.py          # 2×2 Developer Data Grid widget
    └── providers.py     # Off-thread shared worker for Git, Ports, Top Proc, Session tokens
```
