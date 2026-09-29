# Media Command v1 — Phase 7: Status and Settings

- Added `get_media_settings()` and `save_media_settings()` to the existing locked configuration manager. Persisted fields are `resume_external_on_stop`, `speak_on_suppress`, and `local_image_roots` only.
- Reused the HUD’s existing audio-status pill for `EXCLUSIVE`, `SHARED`, and `READY`, driven only by the throttled `MediaState` signal.
- No external player, browser, track, tab, URL, or search-query data enters configuration or status text.
