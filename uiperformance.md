# App Performance Plan

## Summary
Improve perceived speed first: settings/configure clicks should open instantly, then fill in heavier content without freezing the UI. Keep the current design and behavior intact.

## Key Changes
- Add lightweight timing logs around app startup, drawer open, settings open, plugin settings open, config reads, icon scans, and pixmap scaling.
- Cache config data instead of rereading `config/api_keys.json` repeatedly on every UI action.
- Reuse settings overlays after first creation instead of rebuilding all widgets every click.
- Defer expensive settings sections with `QTimer.singleShot(0, ...)` so the overlay appears before hydration work begins.
- Cache available app icons and scaled pixmaps; invalidate only when icon files change.
- Cache plugin settings schemas from `core/plugin_loader.py`; refresh only when plugin enable/config state changes.
- Move slow probes and background checks behind Qt signals so worker threads never touch UI widgets directly.
- Lazy-load non-visible panels and optional UI sections only when first opened.

## Test Plan
- Verify settings/configure opens immediately on first and repeated clicks.
- Confirm saved settings still appear correctly after cache refresh.
- Test plugin settings after enabling/disabling plugins.
- Test icon change, theme preview, save, and cancel behavior.
- Run existing unit tests plus a manual 10-click open/close responsiveness check.

## Assumptions
- No visual redesign.
- No new heavy dependencies.
- Performance priority is UI responsiveness, not voice latency or startup time.


