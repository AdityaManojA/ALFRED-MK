# Phase 5 Notes: Tactical Controls Integration

## Graphify Citations
- Modified node: `ui.py:MainWindow`
- Tactical Controls Drawer: `MainWindow._build_quick_drawer()`
- Setup API Button: `self._setup_api_btn` wired to `_open_api_setup()` and `_refresh_setup_api_btn()`
- Indicator status: dynamically displays configured backend counts `[ ◈ ] SETUP API BACKENDS (X/3)` via `get_configured_backends_count()`.

## Implementation Summary
1. **Drawer Button & Styling**:
   - `_setup_api_btn` added in `_build_quick_drawer()` using `_BTN_STYLE_PRI`, tech mono font, tooltip, and matching tactical button theme.
2. **Lazy-Instantiation**:
   - `_open_api_setup()` instantiates `SetupApiModal` on first click, connects `config_saved` signal to `_on_api_setup_saved()`, and reuses the instance on subsequent clicks.
3. **Status Indicator**:
   - Indicator text refreshes dynamically on boot and on every save signal emitted by `SetupApiModal`.
