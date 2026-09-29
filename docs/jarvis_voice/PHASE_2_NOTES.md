# ALFRED-MK-V — Jarvis Voice Option: Phase 2 Notes

**Date:** 2026-09-29  
**Branch / Workspace:** ALFRED-MK-V  
**Knowledge Graph Nodes Referenced:**  
- `core_tts_capability` (`core/tts/capability.py`)
- `core_tts_jarvis_assets` (`core/tts/jarvis_assets.py`)
- `memory_config_manager` (`memory/config_manager.py`)
- `ui_customizeoverlay` (`ui.py`)

---

## Deliverables & Architecture Implemented

### 1. Capability Gate (`core/tts/capability.py`)
- Implemented robust runtime inspection for all capability states:
  - `PYTHON_VERSION`: Runtime check against `sys.version_info` ensuring `(3, 10) <= version < (3, 13)` as required by VoxCPM2.
  - `MISSING_DEPS`: Lazy checks for optional packages (`torch`, `soundfile`, `huggingface_hub`, `voxcpm`). ALFRED core imports and runs without any of these installed.
  - `NO_CUDA` / `LOW_VRAM`: Queries `torch.cuda.is_available()` and checks device memory against `JARVIS_MIN_VRAM_GB = 8.0`.
  - `CPU_ONLY`: Distinct capability state for CPU-only machines, gated behind settings toggle `JARVIS_ALLOW_CPU` (default `False`).
  - `NOT_DOWNLOADED`: Checks local file integrity for adapter weights, base model weights, and reference audio.
  - `OK`: All prerequisites satisfied.

### 2. Asset Manager & Verifier (`core/tts/jarvis_assets.py`)
- Pinned constants:
  - `JARVIS_REPO = "FuturePresentLabs/tts-jarvis"`
  - `JARVIS_REVISION = "v4-interface-2026-09-06"`
- Dynamic Base Model Resolution:
  - Inspects `inference_config.json` post-download to resolve `base_model` (`openbmb/VoxCPM2`) and `base_revision` (`32279effe8c19989596f05d353d1447f51d9e915`).
  - Base model is never hardcoded or tracking `main`.
- Validation checks:
  - `inference_config.json`
  - `adapter/lora_config.json`
  - Base model weights
  - Reference audio file

---

## Remote Release Audit & Reference Audio Finding

We audited the remote repository `FuturePresentLabs/tts-jarvis` at revision `v4-interface-2026-09-06` using `HfApi().list_repo_files`:
```
['.gitattributes', '.gitignore', 'LICENSE', 'README.md', 'SHA256SUMS',
 'adapter/lora_config.json', 'adapter/lora_weights.safetensors',
 'adapter/training_state.json', 'infer.py', 'inference_config.json']
```

### Key Observation:
1. No `.wav` file is bundled inside the snapshot release.
2. The model's `README.md` explicitly confirms:
   > *"The preferred voice depends on the reference recording as well as the adapter. Using a different recording changes the result. The enrollment recording is not bundled with the adapter. Supply reference audio you are authorized to use."*
3. The release's `inference_config.json` records:
   ```json
   "reference_sha256": "251ca6b8960f6672a8be32ade8ed95f5381d0d5e2376242ca290fe1ab8a7ea24"
   ```

### Ground Rule Compliance:
The project instructions mandate:
> *"Use the bundled one as `JARVIS_REFERENCE_WAV`; if none is bundled, stop and ask me for a reference clip rather than shipping a random voice."*

In strict adherence to this ground rule, execution has paused at this milestone to request the reference audio clip from the user.

---

## Verification & Test Results

1. **Unit Test Suite:** `tests/test_jarvis_voice_phase2.py`
   - `test_python_version_gating`: Passed (3.9 and 3.13 rejected, 3.12 accepted).
   - `test_missing_dependencies_state`: Passed (`MISSING_DEPS` reported safely).
   - `test_no_cuda_vs_cpu_only_states`: Passed (distinguishes `NO_CUDA` and explicit `CPU_ONLY`).
   - `test_low_vram_state`: Passed (< 8 GB VRAM flagged).
   - `test_not_downloaded_state`: Passed (missing weights caught).
   - `test_capability_ok_state`: Passed.
   - `test_constants_pinned`: Passed.
   - `test_asset_detection_on_empty_dir`: Passed.
   - `test_asset_detection_with_valid_files`: Passed.
   - Overall: 9/9 tests passed in 0.021s.
2. **Phase 1 Test Suite:** `tests/test_jarvis_voice_phase1.py`: 5/5 tests passed.
