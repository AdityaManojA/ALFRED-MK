# Phase 2 — Volume Ducking Logic (Bug 1)

## Root Cause Analysis
External media volume ducking previously lacked explicit named configuration constants (`DUCK_VOLUME_PCT = 30`), did not guard against capturing already-muted (`0.0`) sessions (which would then restore the app to muted permanently), and lacked convenient formal context managers (`AudioDuckContext` / `ducked_audio`) with guaranteed `try...finally` teardown for tasks and speech synthesis.

## Graphify Nodes Referenced
- `duck_media_apps() [src=core/audio_ducker.py]`
- `unduck_media_apps() [src=core/audio_ducker.py]`
- `is_ducked() [src=core/audio_ducker.py]`
- `_duck_windows() [src=core/audio_ducker.py]`
- `_unduck_windows() [src=core/audio_ducker.py]`
- `_duck_linux() [src=core/audio_ducker.py]`
- `_unduck_linux() [src=core/audio_ducker.py]`
- `_duck_macos() [src=core/audio_ducker.py]`
- `_unduck_macos() [src=core/audio_ducker.py]`
- `test_audio_ducker.py [src=tests/test_audio_ducker.py]`
- `test_audio_duck_restore_lifecycle.py [src=tests/test_audio_duck_restore_lifecycle.py]`

## Changes Made
1. **Named Constants defined at top of file (`core/audio_ducker.py`)**:
   - `DUCK_VOLUME_PCT: int = 30`
   - `DEFAULT_DUCK_FACTOR: float = DUCK_VOLUME_PCT / 100.0  # 0.3`
   - `SAFE_RESTORE_VOLUME_PCT: int = 50`
   - `SAFE_RESTORE_VOLUME_FACTOR: float = SAFE_RESTORE_VOLUME_PCT / 100.0  # 0.5`
2. **Stateful Volume Safeguard**:
   - Added checks across Windows (`pycaw`), Linux (`pulsectl`), and macOS (`osascript`):
     `if cur_vol <= 0.0: cur_vol = SAFE_RESTORE_VOLUME_FACTOR` (or `SAFE_RESTORE_VOLUME_PCT` on macOS).
   - Also guarded in unducking: if the recorded volume was somehow `0`, it restores to `SAFE_RESTORE_VOLUME_FACTOR` (`0.50`), preventing permanent mute lock-in.
3. **Guaranteed Restoration**:
   - Implemented `AudioDuckContext` class (`__enter__` and `__exit__`).
   - Implemented `@contextmanager def ducked_audio(...)` with `try...finally`.
   - Registered `atexit.register(lambda: unduck_media_apps(sync=True))` so interpreter termination guarantees app restoration.
4. **Unit Tests**:
   - Added `test_zero_original_volume_fallbacks_to_fifty_percent` in `tests/test_audio_ducker.py`.
   - Added `test_duck_audio_context_guarantees_restoration_on_exception` in `tests/test_audio_ducker.py`.
   - All 12 unit tests in `test_audio_ducker.py` and `test_audio_duck_restore_lifecycle.py` pass.

## Verification
- Unit test suite: `py -3.12 -m unittest tests/test_audio_ducker.py tests/test_audio_duck_restore_lifecycle.py` -> 12 tests OK (0.116s).
