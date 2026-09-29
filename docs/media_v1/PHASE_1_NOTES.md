# Media Command v1 — Phase 1: MediaArbiter

## Changes

- Added `core/media/arbiter.py` with the application-owned singleton `MediaArbiter`, `AudioSource`, and privacy-safe `MediaState`.
- `MediaState` exposes only the requested booleans and counters; it carries no external-player, track, process, URL, or tab identity.
- State transitions are emitted no more than once per second (`STATE_SIGNAL_INTERVAL_S`).
- Wired `TronScoreBackgroundPlayer.playback_state_changed` to claim or release `AudioSource.APP_PLAYER` at the player’s existing state-change choke point.
- Wired `JarvisLive.set_speaking()` to claim or release `AudioSource.TTS`. `MainWindow` now applies arbiter `tts_ducking` to the local player.
- Replaced the previous fixed 50% speech duck with the Phase 1 `TTS_DUCK_LEVEL = 0.25` and a `DUCK_RAMP_MS = 300` interpolation.

## Graphify nodes used

- `ui_tronscorebackgroundplayer`, `ui_tronscorebackgroundplayer_on_local_playback_state_changed`, and `ui_mainwindow_apply_state`.
- `core_audio_ducker` (kept separate for its existing external speech-duck behavior).
- `main_jarvislive` / `JarvisLive.set_speaking` as the app-level TTS lifecycle.

## Verification

- `python -m py_compile core/media/__init__.py core/media/arbiter.py ui.py main.py` passed.
- Direct state-transition check passed: APP_PLAYER claim, TTS claim/release, and APP_PLAYER release produced the expected `MediaState` values.
- `pytest` could not run because neither `pytest` nor the project interpreter’s `pytest` module is installed in this environment.

## Open questions

None for Phase 2. External suppression remains deliberately unconnected until a backend can provide opaque handles and the watchdog policy.
