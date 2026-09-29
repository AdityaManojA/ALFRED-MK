# ALFRED-MK-V — Jarvis Voice Option: Phase 1 Notes

**Date:** 2026-09-29  
**Branch / Workspace:** ALFRED-MK-V  
**Knowledge Graph Nodes Referenced:**  
- `core_tts_ttsplayer` (`core/tts/__init__.py`)
- `core_tts_edgettsengine` (`core/tts/engine_default.py`)
- `core_tts_kokorottsengine` (`core/tts/engine_default.py`)
- `core_tts_elevenlabsttsengine` (`core/tts/engine_default.py`)
- `core_local_ttt_localttsmanager` (`core/local_ttt.py`)
- `ui_customizeoverlay` (`ui.py`)
- `ui_mainwindow` (`ui.py`, `main.py`)
- `memory_config_manager` (`memory/config_manager.py`)

---

## Deliverables & Architecture Implemented

### 1. Minimal Engine Interface (`core/tts/engine_base.py`)
- Defined `TTSEngine` Abstract Base Class:
  - `name: str` (e.g. `"default"`, `"jarvis"`)
  - `is_available() -> Capability`
  - `warm_up() -> None`
  - `synthesize(text: str) -> tuple[np.ndarray, int]`
  - `speak(text: str) -> None`
  - `shutdown() -> None`
- Defined `Capability` Enum with states:
  - `OK` ("Available")
  - `MISSING_DEPS` ("Missing dependencies (pip install .[jarvis-voice])")
  - `NO_CUDA` ("Unsupported on this hardware (No CUDA GPU detected)")
  - `LOW_VRAM` ("Unsupported on this hardware (< 8 GB VRAM)")
  - `PYTHON_VERSION` ("Unsupported Python version (requires Python 3.10 - 3.12)")
  - `NOT_DOWNLOADED` ("Needs download (~5 GB)")
  - `CPU_ONLY` ("CPU only (Slow inference - toggle CPU to enable)")
  - `ERROR` ("Error")

### 2. Default Engine Wrapper (`core/tts/engine_default.py`)
- Wrapped legacy engines (`EdgeTTSEngine`, `KokoroTTSEngine`, `ElevenLabsTTSEngine`) behind `EngineDefault(TTSEngine)`.
- When Jarvis voice is OFF, `EngineDefault.speak(text)` invokes the concrete underlying engine's `.speak(text)` directly.
- **Guarantee:** Output latency, audio generation, and call sites are 100% byte-for-byte equivalent to existing behavior.
- Re-exported all legacy symbols in `core/tts/__init__.py` to maintain backwards compatibility for existing imports in `core/local_ttt.py` and elsewhere.

### 3. Settings Persistence (`memory/config_manager.py`)
- Added `VOICE_ENGINES = ("default", "jarvis")` and `DEFAULT_VOICE_ENGINE = "default"`.
- Added persistence helpers:
  - `get_voice_engine() -> str`
  - `save_voice_engine(engine: str) -> None`
  - `get_jarvis_allow_cpu() -> bool`
  - `save_jarvis_allow_cpu(enabled: bool) -> None`
- Supports reading and writing both root `voice_engine` and nested `voice.engine` in `config/api_keys.json` under atomic `_CONFIG_LOCK`.
- Invalid or unrecognized values automatically fall back to `"default"`.

### 4. Settings UI Plumbing (`ui.py`)
- Extended `CustomizeOverlay` with a dedicated "TTS SYNTHESIS ENGINE" section:
  - Selector buttons: `STANDARD / DEFAULT` and `JARVIS (VOXCPM2 LORA)`
  - Tactical status line (`_lbl_engine_status`) showing real-time capability (e.g. `● ACTIVE: Standard Voice (Jarvis: Missing dependencies...)`)
  - Verification button: `▶ PREVIEW VOICE` which synthesizes and speaks a fixed tactical phrase on a background worker thread (`"All systems nominal, sir. Tactical audio matrix online."`)
- **Safety Gate:** If `JARVIS` is selected while unavailable, the UI blocks activation, keeps `default` active, and displays the exact reason from `Capability` without corrupting the configuration or entering a broken state.

---

## Verification & Test Results

1. **Unit Test Suite:** `tests/test_jarvis_voice_phase1.py`
   - `test_engine_default_interface_compliance`: Passed.
   - `test_settings_persistence_and_restart_roundtrip`: Passed (tested restart cache invalidation and invalid value coercion).
   - `test_capability_honest_status_on_unmet_deps`: Passed (verified runtime inspection reports `MISSING_DEPS` without crashing when `voxcpm` is absent).
   - `test_ui_gate_prevents_selecting_unavailable_jarvis`: Passed (verified clicking Jarvis while unavailable preserves default and sets warning status).
   - `test_ui_allows_selecting_jarvis_when_capable`: Passed (verified switching to Jarvis when capable persists `"jarvis"`).
2. **Regression Verification:**
   - Ran `python -m unittest tests/test_config_manager.py`: 6/6 tests passed.
   - Ran `python -m unittest tests/test_hud_reactivity.py tests/test_ui_cleanup.py`: 15/15 tests passed.

Phase 1 acceptance criteria met completely.
