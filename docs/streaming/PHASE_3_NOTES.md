# ALFRED-MK-V: Streaming Providers — Netflix + Crunchyroll
## Phase 3 Implementation Notes: Netflix Provider

**Date:** 2026-10-07  
**Status:** Complete  

### Graphify / Code Nodes Introduced
- `core_streaming_providers_netflix_netflixprovider` (`core/streaming/providers/netflix.py`)
- `tests_test_netflix_provider` (`tests/test_netflix_provider.py`)

### Deliverables
1. **`core/streaming/providers/netflix.py`**:
   - Conforms fully to `StreamingProvider` interface.
   - Discovers confirmed-present surfaces (Windows Store App + installed browsers).
   - `readiness()` evaluates authentication state via OCR tokens (`LOGIN` state maps to `NOT_LOGGED_IN`).
   - `open()` launches native app via Windows shell AUMID (`4DF9E0F8.Netflix_mcm4njqhnhss8!Netflix.App`) or opens default/specified browser to `netflix.com/browse`.
   - `list_profiles()` and `select_profile()`:
     - Extracts ProfileCards from spatial bounding boxes.
     - Fuzzy matches user speech or slot numbers ("first", "second").
     - **PIN Protection:** Checks for PIN modal or profile lock tokens. Halts immediately with `"That profile is locked, sir — you'll need to enter the PIN."` and yields control back to user without attempting to type anything.
   - `search()` and `play()`:
     - Navigates to query search URL.
     - Play triggers watch URL or automated Enter on frontmost session.
2. **Verification**:
   - `tests/test_netflix_provider.py` verifies surface discovery, readiness gating, profile card extraction, fuzzy selection, PIN lock halt without typing, and search/play execution.
   - 7/7 tests passed (6.851s).
