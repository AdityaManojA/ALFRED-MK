# ALFRED-MK-V — Thematic HUD Overhaul: Phase 1 Notes

**Date:** 2026-09-29  
**Branch / Workspace:** ALFRED-MK-V  
**Knowledge Graph Nodes Referenced:**
- `ui_apply_ui_accent` (`ui.py:L887`)
- `ui_current_palette` (`ui.py:L955`)
- `ui_retheme_all_widgets` (`ui.py:L960`)
- `core.ui.themes.schema` (`core/ui/themes/schema.py`)
- `core.ui.themes.registry` (`core/ui/themes/registry.py`)
- `core.ui.themes.apply` (`core/ui/themes/apply.py`)
- `core.ui.themes.catalog` (`core/ui/themes/catalog.py`)

---

## 1. Objectives & Implementation

Phase 1 established structured, typed, single-source-of-truth theme definitions replacing loose ad-hoc color dictionary lookups and hardcoded UI copy.

### 1.1 Architecture Created: `core/ui/themes/`
```
core/ui/themes/
├── __init__.py           # Unified exports: ThemeDefinition, ThemeRegistry, ThemeChrome, apply_theme, get_theme, list_themes
├── schema.py             # Strongly typed dataclasses: PaletteDefinition (24 tokens), IdentityDefinition, ChromeDefinition
├── registry.py           # In-memory ThemeRegistry singleton with ID/hex index, emoji-free validation, and legacy alias support
├── apply.py              # Thread-safe ThemeChrome provider + apply_theme() pipeline
└── catalog.py            # Complete definitions for all classic and interactive themes
```

### 1.2 Schema Definition (`core/ui/themes/schema.py`)
- **`PaletteDefinition`**: 1:1 typed mapping to ALFRED's CRT palette tokens on class `C` (`BG`, `PANEL`, `PANEL2`, `PANEL_BG`, `BORDER`, `BORDER_B`, `BORDER_A`, `PRI`, `PRI_DIM`, `PRI_GHO`, `ACC`, `ACC2`, `GREEN`, `GREEN_D`, `RED`, `MUTED`, `MUTED_C`, `TEXT`, `TEXT_DIM`, `TEXT_MED`, `TEXT_BRIGHT`, `WHITE`, `DARK`, `BAR_BG`).
- **`IdentityDefinition`**: Structured top-right dossier fields (`subject_label`, `subject_value_mode`, `codename`, `incept_date`, `function_line`, `mental_state`, `location_line`, `threat_header`, `threat_levels`, `special_skills`, `clearance_label`, `affiliation_line`).
- **`ChromeDefinition`**: Flavour framing copy for peripheral widgets, scanner titles, headers, empty states, and tabs (`status_prefix`, `ready_line`, `idle_line`, `empty_archive`, `focus_locked_line`, `monitor_active_line`, `telemetry_header`, `tab_telemetry`, `tab_intel`, `bio_scan_header`, `pose_track_header`, `window_title_suffix`, `mini_hud_placeholder`).
- **`SpeechFlavour`**: Voice persona flavour toggle (guaranteed OFF by default, address form defaults to "sir").
- **`ThemeDefinition`**: Top-level immutable container uniting `id`, `display_name`, `tagline`, `hex`, `palette`, `identity`, `chrome`, and `speech_flavour`.

### 1.3 Registry & Validation (`core/ui/themes/registry.py`)
- Strictly enforces non-empty, emoji-free display names via regex pattern `_EMOJI_PATTERN`.
- Maintains O(1) indices by `id` (e.g. `"dossier"`, `"vector"`, `"beyond"`) and by primary accent `hex`.
- Built-in `LEGACY_ALIASES` mapping (`#a8ff3e` → `vector`, `#ff0037` → `beyond`, `#8e9bff` → `dossier`) ensures 100% backward compatibility for existing `config/api_keys.json` files.
- `get(id_or_hex)` safely falls back to `DEFAULT_BATCAVE` when an unrecognized string is supplied.

### 1.4 Central Provider (`core/ui/themes/apply.py`)
- `ThemeChrome`: Thread-safe singleton providing `ThemeChrome.identity()` and `ThemeChrome.chrome()` accessors. Widgets query cached dataclass properties with zero dictionary lookup or string build overhead.
- Supports lifecycle listeners via `ThemeChrome.add_listener()` / `remove_listener()`.

---

## 2. Verification
- All 10 themes verified with `test_catalog_completeness_and_uniqueness`.
- Emoji-free display names confirmed by regex validator.
- Safe fallback verified for unknown theme IDs.
