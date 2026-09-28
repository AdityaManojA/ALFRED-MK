# UI Cleanup Implementation Notes

## Summary of Changes

### 1. Keep Directive Archives on Main Screen
- **Tactical Controls Drawer Cleanup:** Removed the "TACTICAL DIRECTIVES" navigation button and redundant panels from the Tactical Controls quick-access drawer (`_quick_drawer` in `MainWindow`).
- **Main Screen Top-Bar Button:** Preserved direct access to Directive Archives via `_directives_btn` on ALFRED's main screen header row (`[ ☵ ] DIRECTIVES ARCHIVE`).
- **Capability Cards & Theming:** Restyled `CapabilitiesOverlay` to utilize native CRT Batcomputer theme tokens (`C.PANEL_BG`, `C.BORDER_B`, `C.BORDER_A`, `C.PRI`, `C.TEXT_MED`, `C.WHITE`), added real-time filtering with empty-state indicators (`_empty_lbl`), keyboard Esc key dismissal, and descriptive hover help.

### 2. Descriptive Long-Hover Help across Settings
- **Single Reusable Mechanism:** Introduced `TacticalHoverHelpManager` (`QObject` singleton) managing a single centralized `QTimer` with named constant `HOVER_HELP_DELAY_MS = 600`.
- **Comprehensive Coverage:** Attached plain-language hover help across all interactive settings in Tactical Controls (`_quick_drawer`), Reconfigure Batcomputer (`CustomizeOverlay`), Directive Archives (`CapabilitiesOverlay`), Main Screen top bar / right panel / input row, and Intel Notes terminal.
- **Dismissal & Accessibility:** Help automatically dismisses on pointer exit (`Leave`), window resize, tab change, modal close, mouse click, and is accessible on keyboard focus (`FocusIn` / `FocusOut`).

### 3. Single Theme Selector in Reconfigure Batcomputer
- **Deduplication:** Eliminated the duplicate theme preset cards near the top of `CustomizeOverlay`, leaving a single authentic theme selector in "AUTHENTIC CRT THEMES // CHROMATICS".
- **Emoji Removal:** Removed emoji prefixes (`"DEFAULT BATCAVE"`, `"BANE MODE"`, `"BATMAN BEYOND"`), preserving theme IDs (`dossier`, `vector`, `beyond`), RGB/HSV chromatic palette calculations, live previews, and persistence.

### 4. Plugins Settings UI Removal & Automatic Activation
- **Settings UI Removal:** Removed the Plugins tab (`PLUGIN MANAGER`) and Module Parameters button from Tactical Controls (`_quick_drawer`).
- **Automatic Activation:** Configured `config_manager.get_plugin_enabled()` to return `True` for all valid and compatible plugins by default.
- **Legacy Migration:** Added `config_manager.migrate_legacy_plugin_settings()` to safely retire old `plugins_enabled` disable flags on plugin discovery without deleting unrelated user configuration.
- **Failure Isolation:** Plugin discovery isolates failing/broken plugins into `PluginRecord(valid=False, error=...)` without preventing ALFRED or other plugins from starting.

---

## Graphify Node & Edge IDs Referenced

- `ui_capabilitiesoverlay` (Widget for directive archive display)
- `ui_customizeoverlay` (Reconfiguration matrix overlay)
- `ui_mainwindow_open_directives` (Handler for opening capabilities overlay)
- `ui_mainwindow_build_quick_drawer` (Tactical controls floating panel)
- `ui_tacticalhoverhelpmanager` (Single-timer hover tooltip manager)
- `core_plugin_loader_discover_plugins` (Plugin discovery and registry builder)
- `core_plugin_loader_pluginregistry_list_for_ui` (Plugin list generator)
- `memory_config_manager_get_plugin_enabled` (Plugin activation lookup)
- `memory_config_manager_migrate_legacy_plugin_settings` (Plugin configuration migration)
- `memory_config_manager_save_ui_accent` (Theme palette persistence)

---

## Verification & Test Results

- **Unit Tests:**
  - `tests/test_ui_cleanup.py`: 6/6 tests passing (capabilities search & empty states, absence of directives/plugins from quick drawer, hover help 600ms delayed trigger/dismiss/focus, single emoji-free theme selector, plugin auto-activation & legacy migration, failure isolation).
  - `tests/test_plugin_loader.py`: 3/3 tests passing.
  - `tests/test_hud_reactivity.py`: 8/8 tests passing.
  - `tests/test_minimized_hud_overlay.py`: 6/6 tests passing.
  - `tests/test_config_manager.py`: 6/6 tests passing.
- **Combined Test Run:** `python -m unittest tests.test_ui_cleanup tests.test_plugin_loader tests.test_hud_reactivity tests.test_minimized_hud_overlay tests.test_config_manager` -> 29/29 tests passing.
