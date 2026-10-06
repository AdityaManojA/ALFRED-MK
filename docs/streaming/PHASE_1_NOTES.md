# ALFRED-MK-V: Streaming Providers — Netflix + Crunchyroll
## Phase 1 Implementation Notes: Provider Abstraction

**Date:** 2026-10-07  
**Status:** Complete  

### Graphify / Code Nodes Introduced
- `core_streaming_provider_streamingprovider` (`core/streaming/provider.py`)
- `core_streaming_provider_surface` (`core/streaming/provider.py`)
- `core_streaming_provider_title` (`core/streaming/provider.py`)
- `core_streaming_provider_profilecard` (`core/streaming/provider.py`)
- `core_streaming_provider_result` (`core/streaming/provider.py`)
- `core_streaming_registry_providerregistry` (`core/streaming/registry.py`)
- `core_streaming_registry_get_selector` (`core/streaming/registry.py`)
- `tests_test_streaming_provider_interface` (`tests/test_streaming_provider_interface.py`)

### Deliverables
1. **`core/streaming/provider.py`**:
   - Named configuration constants (`PROVIDER_NAV_TIMEOUT_S = 20.0`, `PROVIDER_SEARCH_TIMEOUT_S = 10.0`, `PROVIDER_STATE_POLL_MS = 500`, `PROVIDER_STATE_RETRIES = 3`).
   - Strongly-typed enums: `SurfaceKind`, `CapabilityClass` (FULL, NAV_ONLY, LAUNCH_ONLY, UNAVAILABLE), `Readiness`, `ProviderState`.
   - Immutable data carriers: `Surface`, `Title`, `ProfileCard`, `Result`.
   - `StreamingProvider(ABC)` base class declaring the 8 core lifecycle methods.
2. **`core/streaming/selectors.json`**:
   - External JSON file with primary and ordered fallback CSS/text selectors for Netflix and Crunchyroll across all UI states (login, profiles, home, search, player).
3. **`core/streaming/registry.py`**:
   - Lazy registry resolving `id -> provider`.
   - Thunk factories ensure `playwright` is never imported at boot time.
   - `get_selector()` helper with primary/fallback resolution.
4. **Verification**:
   - `tests/test_streaming_provider_interface.py` verifies full interface conformance, lazy registry resolution, selector loading, and that `playwright` is not imported.
   - 4/4 tests passed (0.001s).
