# ALFRED-MK-V — Thematic HUD Overhaul: Phase 0 Reconnaissance Notes

**Date:** 2026-09-29  
**Branch / Workspace:** ALFRED-MK-V  
**Knowledge Graph Nodes Referenced:**  
- `ui_apply_ui_accent` (`ui.py:L887`)
- `ui_current_palette` (`ui.py:L955`)
- `ui_retheme_all_widgets` (`ui.py:L960`)
- `ui_subjectdossiercard` (`ui.py:L2820`)
- `ui_crtreconwidget` (`ui.py:L2600`)
- `ui_biometricfingerprintwidget` (`ui.py:L2658`)
- `ui_wireframeposewidget` (`ui.py:L2746`)
- `ui_minimizedhudoverlay` (`ui.py:L3739`)
- `ui_customizeoverlay` (`ui.py:L5358`)
- `ui_mainwindow` (`ui.py:L7830`)
- `memory_config_manager` (`memory/config_manager.py`)

---

## 1. Theme Definition, Selection Persistence, and Apply Path

- **Theme Storage & Definition:** Currently, themes are stored in `ui.py` (lines 633–725) in a hardcoded dictionary named `CRT_THEMES`. Color tokens are assigned to class `C` (lines 729–779). An internal module-level variable `_ACTIVE_THEME_ID` tracks the current theme ID (`"dossier"` by default).
- **Persistence:** Persisted in `config/api_keys.json` under the key `"ui_color"` via `memory/config_manager.py` (`_patch_config`). The configuration stores the primary accent hex string (e.g. `"#8e9bff"`, `"#a8ff3e"`, `"#ff0037"`). On startup, `MainWindow.__init__` reads `cfg.get("ui_color")` and invokes the apply function.
- **Single Apply Path:**
  1. `apply_ui_accent(accent_hex: str) -> bool` (`ui.py:L887`, node `ui_apply_ui_accent`): Takes the hex code, matches or hue-shifts CRT tokens on class `C`, and updates `_ACTIVE_THEME_ID`.
  2. `current_palette() -> dict[str, str]` (`ui.py:L955`, node `ui_current_palette`): Grabs a snapshot of the current `_HUE_LINKED` color values on class `C`.
  3. `retheme_all_widgets(old: dict, new: dict)` (`ui.py:L960`, node `ui_retheme_all_widgets`): Traverses `QApplication.instance().allWidgets()`, performs in-place string replacement of old hex values with new hex values in every widget's stylesheet, and calls `w.update()`.

---

## 2. Current Theme IDs & Current Behavior

There are currently **3 theme definitions** in `CRT_THEMES`:
1. `"dossier"`: Display name `"DEFAULT BATCAVE"`, Primary accent `"#8e9bff"`.
2. `"vector"`: Display name `"BANE MODE"`, Primary accent `"#a8ff3e"`.
3. `"beyond"`: Display name `"BATMAN BEYOND [NEO-GOTHAM]"`, Primary accent `"#ff0037"`.

**What each actually changes today:**
- **Palette ONLY.** Switching between these 3 themes changes the 23 color keys on class `C` (`BG`, `PANEL`, `PANEL2`, `BORDER`, `BORDER_B`, `BORDER_A`, `PRI`, `PRI_DIM`, `PRI_GHO`, `ACC`, `ACC2`, `GREEN`, `RED`, `TEXT`, `WHITE`, `DARK`, etc.) and updates Qt stylesheets across all widgets.
- **Zero text or chrome changes:** Every label, dossier row, header, threat assessment, mental state, status prompt, and card title remains completely static and hardcoded.

---

## 3. Top-Right Identity & Status Block

- **Class Name:** `SubjectDossierCard` (`ui.py:L2820-2900`, node `ui_subjectdossiercard`).
- **Layout Placement:** Mounted at the top of the right sidebar in `MainWindow._build_right_panel` (`ui.py:L8837`).
- **Fields & Binding Status:**
  - `Header Title`: `"SUBJECT A-34"` (hardcoded at L2867)
  - `Header Deco`: `"[■■■■■]"` (hardcoded at L2869)
  - `NAME`: Bound to `self._asst_name` (set via `set_name()`)
  - `INCEPT DATE`: `"03/05/2026"` (hardcoded)
  - `FUNCTION`: `"TACTICAL PERSONAL ASSISTANT"` (hardcoded)
  - `MENTAL STATE`: `"OPERATIONAL // ACTIVE"` (hardcoded)
  - `LAST KNOWN LOC`: `"WAYNE MANOR // LOCALHOST"` (hardcoded)
  - `THREAT ASSESSMENT`: `"★★★"` (hardcoded)
  - `SPECIAL SKILLS`: `"[AI]  [SYS]  [SEC]  [AUDIO]"` (hardcoded)

All identity fields except assistant name are hardcoded strings inside `paintEvent`.

---

## 4. Other Chrome Candidates for Thematic Binding

The following sites should participate in thematic contextual skinning:

| UI Site | File & Line | Graphify Node | Current Text / Purpose |
|---|---|---|---|
| Main Window Title | `ui.py:L7846, L10377` | `ui_mainwindow` | `f"{_display} — {APP_VERSION}"` |
| Recon Scanner Header | `ui.py:L2621` | `ui_crtreconwidget` | `"● ● ●  RECON FEED // OPTICAL"` |
| Biometric Box Header & Badge | `ui.py:L2718, L2743` | `ui_biometricfingerprintwidget` | `"BIO-SCAN // FINGERPRINT"`, `"VERIFIED // ALPHA-1"` |
| Pose Widget Header & Readout | `ui.py:L2785, L2817` | `ui_wireframeposewidget` | `"TELEMETRY // POSE TRACK"`, `"TARGET ACQUIRED: LOCAL"` |
| Left Telemetry Header | `ui.py:L8785` | `ui_mainwindow` | `"SYS TELEMETRY"` |
| Right Tab Buttons | `ui.py:L8842, L8849` | `ui_mainwindow` | `"[ ◈ ]  TELEMETRY"`, `"[ ▤ ]  INTEL // NOTES"` |
| Directives Overlay Button | `ui.py:L8621` | `ui_mainwindow` | `"[ ▤ ]  DIRECTIVES ARCHIVE"` |
| Memory Archives Button | `ui.py:L9104` | `ui_mainwindow` | `"[ ☵ ]  WAYNE SECURE ARCHIVES"` |
| Capabilities Overlay Header | `ui.py:L6022` | `ui_customizeoverlay` | `"📋  DIRECTIVES & CAPABILITIES ARCHIVE"` |
| Memory Overlay Header | `ui.py:L6692` | `ui_customizeoverlay` | `"🧠  NEURAL SYNAPSE ARCHIVE"` |
| Minimized HUD Window Title | `ui.py:L3764` | `ui_minimizedhudoverlay` | `"ALFRED MK-IV // ACTIVITY"` |
| Minimized HUD Placeholder | `ui.py:L3855` | `ui_minimizedhudoverlay` | `"Awaiting ALFRED response…"` |
| Minimized HUD Header | `ui.py:L3872` | `ui_minimizedhudoverlay` | `f"{self._assistant_name.upper()} // ACTIVE"` |

---

## 5. Theme Preview & Apply Lifecycle

- **Live Preview:** A live theme preview **already exists** in `CustomizeOverlay` (`ui.py:L5578-5615`, node `ui_customizeoverlay`). Clicking any theme card calls `self._set_color(s_hex, update_wheel=True, preview=True)`, which emits `on_preview(hex_color)` into `MainWindow._preview_ui_color`.
- **Apply vs Cancel:**
  - While previewing, `apply_ui_accent` updates class `C` and `retheme_all_widgets` live-repaints all open widgets.
  - If the user clicks **DISCARD** (`_cancel()`), the overlay restores `_initial_color`.
  - If the user clicks **SAVE** (`_save()`), `MainWindow._apply_name_update` commits `ui_color` into `config/api_keys.json`.
- **Restart Behavior:** On application launch, `MainWindow.__init__` reads `ui_color` from `config/api_keys.json` and runs `apply_ui_accent(ui_color)`, cleanly restoring the saved theme.

---

## 6. Existing Assets in the Repository

- **Icons:**
  - `Icons/baticon_Default.ico`, `Icons/baticon_Default.png`
  - `Icons/baticon_Beyond.ico`, `Icons/baticon_Beyond.png`
  - `Icons/baticon_Arlham_Asylum.png`
  - `Icons/baticon_White.png`
- **Screenshots:**
  - `Screenies/Default_theme.png`
  - `Screenies/Bane_theme.png`
  - `Screenies/Batman_beyond_Theme.png`

---

## Proposed Architecture: `core/ui/themes/`

We will organize the theme system into a clean, modular architecture:

```
core/ui/themes/
├── __init__.py           # Exports get_theme, list_themes, apply_theme, ThemeDefinition, ThemeChrome
├── schema.py             # ThemeDefinition dataclass, PaletteDefinition, IdentityDefinition, ChromeDefinition
├── registry.py           # In-memory theme registry with lookups by id and display_name
├── apply.py              # Unified apply path updating class C, ThemeChrome, and retheming widgets
└── catalog.py            # Concrete theme catalog: Default, Bane, Batman Beyond + 5 new interactive skins
```

`ThemeChrome` will provide thread-safe, fast access to current theme strings so widgets can read `ThemeChrome.identity` and `ThemeChrome.chrome` with zero per-frame dictionary lookups or string construction.
