# Media Command v1 — Phase 2: External Player Suppression

## Graphify nodes used

- `core_audio_ducker`, `core_audio_ducker_duck_windows`, and `core_audio_ducker_unduck_windows` showed the existing Windows session and self-process safeguards.
- `ui_tronscorebackgroundplayer` and `main_jarvislive_set_speaking` supplied the app-player and spoken-status integration points.

## Changes

- Added the opaque-handle `Suppressor` interface under `core/media/suppress/`.
- Added a Windows-first implementation: SMTC is attempted through optional `winsdk`; `pycaw` provides a process-session mute/restore fallback and excludes ALFRED’s PID.
- Added import-safe Linux and macOS stubs behind the same interface.
- Extended `MediaArbiter` with a daemon watchdog that starts only while the in-app player holds `APP_PLAYER`, sweeps immediately and then every `SUPPRESS_SWEEP_S = 3`, and stops on release.
- The arbiter retains only opaque in-memory handles. Client-visible state remains booleans and a count.
- A repeated external restart within `EXTERNAL_OVERRIDE_WINDOW_S = 20` marks that opaque handle overridden, stops suppressing it, and emits the requested one-time spoken line.
- Added `winsdk` as a Windows-only optional dependency for SMTC support.

## Verification

- Added a fake-suppressor test covering app-player claim, immediate sweep, and privacy-safe suppressed count.
- Live SMTC/Spotify verification is pending a Windows desktop session with an active external media player.
