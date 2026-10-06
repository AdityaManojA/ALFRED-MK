# ALFRED-MK-V: Streaming Providers — Netflix + Crunchyroll
## Phase 4 Implementation Notes: Crunchyroll Provider

**Date:** 2026-10-07  
**Status:** Complete  

### Graphify / Code Nodes Introduced
- `core_streaming_providers_crunchyroll_crunchyrollprovider` (`core/streaming/providers/crunchyroll.py`)
- `core_streaming_providers_crunchyroll_parse_query_episode_specs` (`core/streaming/providers/crunchyroll.py`)
- `tests_test_crunchyroll_provider` (`tests/test_crunchyroll_provider.py`)

### Deliverables
1. **`core/streaming/providers/crunchyroll.py`**:
   - Conforms to `StreamingProvider` interface.
   - Discovers installed host browsers (Chrome, Edge, Brave, etc.).
   - `parse_query_episode_specs()` resolves series name, season number, episode number, and sub/dub specifiers from natural language queries.
   - Remembers audio language preference (`sub` default vs `dub` override) per-user in `streaming.crunchyroll.audio_pref`.
   - **Premium Lock Gating:** Detects `is_premium_locked == True` and immediately yields `"That one needs Premium, sir."` without navigating or attempting playback.
   - Handles episode number formatting and skip intro transport hotkey.
2. **Verification**:
   - `tests/test_crunchyroll_provider.py` verifies query parsing, audio preference updating, Premium lock rejection, and playback execution.
   - 4/4 tests passed (3.091s).
