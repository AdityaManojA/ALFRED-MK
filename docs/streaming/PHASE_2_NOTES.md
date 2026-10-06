# ALFRED-MK-V: Streaming Providers — Netflix + Crunchyroll
## Phase 2 Implementation Notes: Surface Discovery & Ask-Once Memory

**Date:** 2026-10-07  
**Status:** Complete  

### Graphify / Code Nodes Introduced
- `core_streaming_discovery_discover_installed_browsers` (`core/streaming/discovery.py`)
- `core_streaming_discovery_discover_netflix_native_app` (`core/streaming/discovery.py`)
- `core_streaming_discovery_discover_crunchyroll_native_app` (`core/streaming/discovery.py`)
- `core_streaming_preferences_get_preferred_surface` (`core/streaming/preferences.py`)
- `core_streaming_preferences_set_preferred_surface` (`core/streaming/preferences.py`)
- `core_streaming_preferences_forget_preferred_surface` (`core/streaming/preferences.py`)
- `core_streaming_preferences_resolve_surface` (`core/streaming/preferences.py`)
- `core_streaming_preferences_get_audio_preference` (`core/streaming/preferences.py`)
- `core_streaming_preferences_set_audio_preference` (`core/streaming/preferences.py`)
- `tests_test_streaming_preferences` (`tests/test_streaming_preferences.py`)

### Deliverables
1. **`core/streaming/discovery.py`**:
   - Inspects host OS for real, confirmed-present browsers and native desktop apps.
   - Windows: Reads `App Paths` and `StartMenuInternet` in registry, and queries `Get-AppxPackage 4DF9E0F8.Netflix`.
   - Never fabricates uninstalled applications.
2. **`core/streaming/preferences.py`**:
   - Persists preferences under `streaming.<provider>.surface` and `streaming.crunchyroll.audio_pref` directly in `config/api_keys.json` using `memory/config_manager.py`.
   - Asks once if no preference exists, detailing real capability limits (e.g. `LAUNCH_ONLY` vs `FULL`).
   - Reuses saved choice silently.
   - Re-asks automatically if a preferred surface disappears from the machine.
   - Supports explicit voice/settings overrides (`"open in Edge"`), updating saved preference after execution succeeds.
   - Exposes `forget_preferred_surface(provider_id)`.
3. **Verification**:
   - `tests/test_streaming_preferences.py` verifies:
     - Ask-once fires and persists.
     - Silent reuse on subsequent calls.
     - Re-asking when preferred surface is removed.
     - Explicit override prioritization.
     - Forget preference functionality.
     - Audio preference ('sub' vs 'dub') persistence.
     - Truthful capability prompt formatting.
   - 6/6 tests passed (0.005s).
