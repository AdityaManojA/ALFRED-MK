# ALFRED-MK-V — Media Command v1: Phase 0 Reconnaissance

Date: 2026-09-29

## Graphify evidence

This phase used the existing `graphify-out/graph.json`, `.graphify_analysis.json`, and `GRAPH_REPORT.md`; it did not regenerate the graph. The relevant graph nodes and communities were:

- `ui_tronscorebackgroundplayer`, `ui_tronscorebackgroundplayer_set_ducked`, and `ui_tronscorebackgroundplayer_on_local_playback_state_changed` (`ui.py:179-610`). `GRAPH_REPORT.md` community 55 identifies this as the in-app audio-core cluster.
- `core_hud_video_controller` / `HudVideoController`, `LocalUrlBackend`, and `HudVideoSurface` (`core/hud_video/controller.py:52-287`, `core/hud_video/backends/local_url.py:33-128`, `core/hud_video/surface.py:112-...`). `GRAPH_REPORT.md` community 69 records their controller/surface relationship.
- `core_audio_ducker`, `core_audio_ducker_duck_windows`, `core_audio_ducker_duck_linux`, and `core_audio_ducker_unduck_windows` (`core/audio_ducker.py:52-296`).
- `ui_mainwindow`, `ui_mainwindow_apply_state`, `ui_minimizedhudoverlay`, and `ui_mainwindow_init` (`ui.py:7860+`, `ui.py:11055-11131`, `ui.py:3752+`). `GRAPH_REPORT.md` lists `MainWindow` as the bridge between HUD, audio core, overlays, and video.
- `memory_config_manager` and `memory_config_manager_patch_config` (`memory/config_manager.py:8-477`), the existing atomic configuration path.

## 1. Existing in-app player

`TronScoreBackgroundPlayer` in `ui.py:179-610` is the music player. It owns the local `QMediaPlayer` and `QAudioOutput`, creates them in `load_track()` (`ui.py:311-349`), and loops the current local track. Its local-state choke point is `_on_local_playback_state_changed()` (`ui.py:452-458`), which emits `playback_state_changed(bool)` after the Qt player changes state.

The player exposes `play()`, `pause()`, `pause_core()`, `resume_core()`, `next_track()`, `prev_track()`, `is_playing()`, and `stop()` (`ui.py:484-610`). The UI-level entry points are `MainWindow.pause_audio_core()`, `resume_audio_core()`, and `get_audio_core_status()` (`ui.py:11077-11131`), with the tool action in `actions/audio_core.py:24-171`.

Spotify is a separate logical source of the same card, controlled through the Spotify Web API in `actions/spotify_control.py`; it is not local desktop Spotify session control. `set_spotify_playback()` switches the audio card to that source and pauses the local score. HUD state is reflected through `playback_state_changed`, `track_changed`, and the tactical audio card. There is no seek method in the audio-core player today.

The separate HUD video path is `HudVideoController` plus `LocalUrlBackend`, also based on `QMediaPlayer`/`QAudioOutput`, but it starts muted and is not the music path. It is initialized by `MainWindow._init_hud_video()` (`ui.py:8206-8256`).

## 2. External-player awareness

`core/audio_ducker.py` is the only existing external-media integration. On Windows it uses `pycaw` to reduce the volume of an allowlist of process sessions; on Linux it uses `pulsectl`; macOS has no implementation. It preserves original per-process volume by PID and excludes the current process. It does not enumerate opaque player handles, inspect playback state, pause sessions, resume sessions, watch for manual overrides, or use SMTC/MPRIS/AppleScript.

Phase 2 should reuse its self-process and best-effort volume restoration ideas only for the fallback. It must not extend this module into the new policy owner, because its global PID-to-volume state does not satisfy the requested private session ownership or pause/resume semantics.

## 3. Voice and tool routing

The primary chat/tool choke point is `JarvisLive._dispatch_tool()` in `main.py:1801+`, with normal action dispatch continuing through the loaded action handlers. `actions/audio_core.py` serves requests for “audio core”, “tron music”, “background score”, and “ambient music”; it accepts pause/resume/play/stop/volume/next/previous/restore operations.

`core/hud_video/intent.py:61-121` recognizes a video request only when a play verb (`play`, `watch`, `show`, `put`, `stream`, `load`, `pull up`, `bring up`, `open`) is paired with a locus phrase such as “in the HUD” or “on screen.” Its transport detector also claims broad commands including “pause”, “resume”, “stop player”, “mute”, “louder”, and “quieter” while video is active. New image routing must take precedence over the video route for `show me …`, and explicit image-file paths must take precedence over both image search and video routing.

There is no existing image-display tool registration. The new `show_image` tool belongs beside the existing auto-discovered action/tool pattern, then needs a deliberately small response contract for the chat brain.

## 4. HUD component tree and styling

`MainWindow` owns the full HUD and constructs the HUD-video stack in `_init_hud_video()`. The video surface supplies the closest existing overlay/card pattern: themed stylesheet, glow/scan presentation, a cached media widget, and controller signals. `HudCanvas` is the main custom-painted HUD surface. `MinimizedHudOverlay` (`ui.py:3752+`) is a separate translucent top-level transcript window, created once by `MainWindow`; it already has a header bar, status button, close control, drag handling, and state-update path.

Theme color and chrome values are centralized in `core/ui/themes/` and applied through `ThemeChrome` / `apply_theme()`. Existing phase notes identify the palette and overlay lifecycle; the image panel should use that API and not duplicate the legacy hardcoded color dictionary in `ui.py`.

## 5. Fetching and persistence

Network code is request-specific today: `requests` is used by action modules and TTS, `urllib` appears in lightweight tools, and HUD video resolves remotely in a worker thread. There is no generic image source or image-cache abstraction. `core/cache.py` is the existing small disk-cache module, while `memory/config_manager.py` provides the application’s locked, atomic JSON update path for `config/api_keys.json` and plugin namespaces.

The image cache should be a separate byte-only LRU under `data/image_cache/`, as requested. It must use a SHA-256-derived key and must not route query strings through the logger, settings, or cache metadata.

## 6. TTS and ducking

Default TTS is `core/tts/engine_default.py:TTSPlayer` over `sounddevice`; the local live fallback in `main.py:_speak_local()` uses Windows SAPI. The audio core already performs in-app ducking: `MainWindow._apply_state()` calls `TronScoreBackgroundPlayer.set_ducked(state == "SPEAKING")`, which fades the local score to 50% of its base volume. This is distinct from `core/audio_ducker.py`, which lowers external application volume during speech.

Phase 1 should centralize the local-player duck state through the arbiter and preserve the current callback paths during migration. The required `0.25` duck level and `300 ms` ramp are a behaviour change from today’s 0.5 target and 20 ms incremental fade, so they need dedicated tests.

## 7. Platform target

The active workspace is Windows, and the repository’s existing external-audio code has its most complete support there (`pycaw`). Phase 2 should implement the Windows SMTC backend first, with a guarded `pycaw` mute fallback. Linux and macOS should receive clean, import-safe stubs in the same phase; their MPRIS and AppleScript implementations can be developed after the shared interface is stable.

## Proposed layout

```text
core/media/
  __init__.py
  arbiter.py
  suppress/
    __init__.py
    base.py
    win.py
    mac.py
    linux.py

core/imagery/
  __init__.py
  cache.py
  sources/
    __init__.py
    base.py
    local.py
    web.py

core/ui/
  image_deck.py
```

`MediaArbiter` should be owned by application startup and injected into the audio core, TTS path, and HUD status listeners. `ImageDeckPanel` should be a focused Qt panel in `core/ui/`, constructed and retained by `MainWindow`, with source and cache code staying UI-independent.

## Phase 0 verification

- Existing graph artifacts were queried and read; no graph rebuild was run.
- No application source files were changed in this phase.
- Source inspection verified QMediaPlayer/QAudioOutput for the music and HUD-video paths, existing local/external duck paths, the voice/tool choke point, and the Windows-first external-media capability.
- Open question: none blocks Phase 1. The new `MediaArbiter` can be added without changing codec support or the viseme path.
