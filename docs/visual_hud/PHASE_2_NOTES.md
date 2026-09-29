# Phase 2 Notes: Single-Flight Deduplication & Debounce (P2)

## 1. Summary of Changes
- **Single-Flight Concurrency Control (`_SingleFlightManager`)**:
  - Implemented in `actions/hud_video.py` with thread-safe lock:
    - `RESOLVE_DEBOUNCE_MS = 800`
    - `SAME_TARGET_TTL_S = 30`
    - `STT_GATE_AFTER_PLAY_S = 2.0`
    - `SPEAK_RESOLVE = False`
  - Normalizes target strings (`normalize(target)`) by stripping punctuation and consolidating whitespace.
  - Returns terminal output if an identical query is currently in-flight or was requested within `RESOLVE_DEBOUNCE_MS` (`"Visual HUD is already preparing {target}."`).
  - Increments generation token (`_active_token`) when a new/different target is received, immediately canceling any prior in-flight yt-dlp workers before they touch controller or Qt player.
- **Terminal Tool Outputs (Preventing Model Tool Loop)**:
  - Eliminated non-terminal `"Resolving: X"` output.
  - Returns immediate, definitive confirmations:
    - `"Playing {target} on the Visual HUD."`
    - `"Visual HUD is already preparing {target}."`
- **Terse ALFRED Persona**:
  - `SPEAK_RESOLVE = False`: Disabled unneeded spoken confirmations (`VIDEO_ACK_LINES`) during resolve.
  - Updates toast notification directly in the HUD interface. Spoken speech is reserved strictly for fatal errors.

---

## 2. Graphify Nodes & Edges Referenced
- `$graphify-root$_actions_hud_video_singleflightmanager` (`_SingleFlightManager` in `actions/hud_video.py`): Concurrency manager.
- `$graphify-root$_actions_hud_video_hud_video` (`actions/hud_video.py:hud_video`): Action entry point with debounce checks.

---

## 3. Test Verification
- `tests/hud_video/test_dedupe_singleflight.py`: 2/2 tests passed.
  - `test_20_duplicate_plays_starts_one_resolve`: 20 rapid duplicate requests launch exactly 1 worker thread and return terminal responses.
  - `test_different_target_cancels_previous_resolve`: Different target invalidates prior token and triggers fresh resolve.
- All existing tests continue to pass.
