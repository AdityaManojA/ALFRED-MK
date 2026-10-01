# Phase 8 Notes — Speculative Prefetch & Resource Pre-warming

## Status: COMPLETE

### 1. Architecture & Design
1. **Speculative Intent Pre-warming (`core/intents/fastpath.py`)**:
   - `SpeculativePrefetcher` monitors speculative partial transcript tokens from Shadow Whisper or early user input.
   - Triggers background pre-warming of read-only dependencies before the full model turn completes:
     - `time_date`: System clock and formatted date strings.
     - `system`: CPU, RAM, and Battery telemetry snapshots.
     - `app_path`: Binary filesystem path resolution for common executable targets via `shutil.which`.
     - `dns`: Hostname resolution and DNS socket warming.

2. **Absolute Purity & Zero Side Effects**:
   - Speculative prefetch execution is strictly constrained to idempotent read operations.
   - Purity tests verify that no environment variables, file system records, processes, or UI states are altered during speculative pre-warming.

3. **Bounded In-Memory Cache with TTL**:
   - Prefetched records are stored with a 10.0-second TTL (`PREFETCH_TTL_S = 10.0`) in a bounded LRU cache (`MAX_PREFETCH_ENTRIES = 64`).
   - Expired entries are automatically evicted upon retrieval.
   - Worker pool is strictly throttled to 2 threads (`PREFETCH_MAX_WORKERS = 2`) to eliminate core contention with the real-time audio pipeline.

### 2. Verification
- `py -3.12 -m unittest tests/intents/test_speculative_prefetch.py`: 4/4 PASS in 0.368s.
- Verified purity invariants, TTL expiration, async thread-pool dispatch, and partial text pattern matching.
