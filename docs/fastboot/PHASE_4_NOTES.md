# Phase 4 Notes — Boot Decomposition into Declared Stages

## Status: COMPLETE

### 1. Architecture & Design
1. **Declarative Boot Stages (`core/boot/stages.py`)**:
   - Implemented `BootStage` model:
     - `name: str`
     - `init_fn: Callable[[BootContext], Any]`
     - `dependencies: list[str]` (DAG prerequisites)
     - `is_critical: bool` (Fail-safe: critical failures abort boot with `BootFailureError`; non-critical fail-open)
     - `thread_affinity: str` (`"main"` for Qt GUI thread, `"worker"` for background pool)
     - `timeout_s: float` (default `BOOT_STAGE_TIMEOUT_DEFAULT_S = 10.0`)
   - `BOOT_TOTAL_BUDGET_S = 30.0`

2. **Topological Pipeline & Parallel Execution (`core/boot/loader.py`)**:
   - `BootPipeline`:
     - Computes topological batches using in-degree reduction.
     - Validates all declared prerequisites and detects cyclic dependencies.
     - Executes independent stages in parallel within each batch using `ThreadPoolExecutor(max_workers=4)`.
     - Preserves GUI thread safety by running `"main"` affinity stages synchronously on the caller thread.
   - `BootContext`:
     - Thread-safe key-value store for cross-stage outputs.
     - Records per-stage execution status, timing (ms), and any exceptions.

3. **Standard Pipeline Stages (`build_standard_boot_pipeline`)**:
   - `config_secrets` (Worker, Critical): Loads local configuration and preferences.
   - `audio_stream` (Worker, Critical): Initializes `SharedAudioStream` and `AudioGate`.
   - `tool_registry` (Worker, Non-critical): Auto-discovers actions and plugins in parallel without blocking UI.
   - `wakeword` (Worker, Non-critical): Warms wake-word detector.
   - `background_audio` (Worker, Non-critical): Prepares background player.

### 2. Verification
- `py -3.12 -m unittest tests/boot/test_boot_stages.py`: 8/8 PASS in 4.365s.
- Verified cycle detection, missing dependency detection, parallel worker execution, fail-open on non-critical stages, and standard pipeline integration.
