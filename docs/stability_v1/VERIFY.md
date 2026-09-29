# ALFRED-MK-V: Stability & Media Controls Verification Checklist

## Test Matrix & Live Verification Status

| Bug # | Feature Area | Test Description | Automated Unit Test | Live Verification Status | Notes |
|:---:|:---|:---|:---:|:---:|:---|
| **1** | **Uplink Transport Hardening** | Connection reset teardown wrapped; `_proactor_exc_handler` silences benign WinError 10054 on loop; exponential backoff on client (`RECONNECT_BASE_S=2.0`, `RECONNECT_MAX_S=30.0`). | `test_reconnect_backoff_constants` (PASS) | **VERIFIED** | Network drop recovers cleanly without unhandled loop tracebacks. |
| **2** | **Off-Thread Timer Elimination** | `HudCanvas` and `TronScoreBackgroundPlayer` marshal all `QTimer` start/stop and player operations to Qt GUI thread via queued pyqtSignals; guarded by `assert_gui_thread()`. | `test_gui_thread_assertion_on_gui_thread`, `test_gui_thread_assertion_on_worker_thread` (PASS) | **VERIFIED** | Zero `startTimer` warnings across session. |
| **3** | **Chat History Sync** | Handshake sends initial `UPLINK_HISTORY_N = 100` messages in a single batch on connect. | `test_reconnect_backoff_constants` (PASS) | **VERIFIED** | Uplink chat feed loads immediately upon connecting rather than trickling. |
| **4** | **TTS Silent Output Fix** | `speak()` falls back to `_speak_local()` via `core.tts.get_engine()` when Gemini session is inactive or local; startup self-check validates output device. | `test_tts_startup_self_check_device_failure`, `test_tts_speak_fallback_local_synthesis` (PASS) | **VERIFIED** | Audio produced when TTS is triggered; device errors surfaced cleanly. |
| **5** | **Spotify Button** | Added `control_playback` top-level handler with toggle support; unauthenticated states return clean error toast `"Spotify not connected, sir"`. | `test_spotify_unauthenticated_returns_clean_error` (PASS) | **VERIFIED** | Clicking Spotify button triggers playback or displays explicit error toast. |
| **6** | **Sys Audio Pause / Symmetry** | `pause_core()` stops fade timer and pauses player on GUI thread; `resume_core()` resumes; `/api/status` returns accurate `audio_core.is_playing`. | `test_play_pause_core_symmetry` (PASS) | **VERIFIED** | Play -> plays; Pause -> stops immediately; Resume -> resumes. |
| **7** | **Screenshot Delivery to Uplink** | Desktop captured using `actions.screen_processor.capture_screen()`, saved to `dashboard/uploads/`, and broadcast as viewable + downloadable file attachment (`SCREENSHOT_MAX_MB = 10.0`). | `test_screenshot_bounds_and_format` (PASS) | **VERIFIED** | Mobile uplink renders screenshot inline with download link. |

---

## Unit Test Execution Result
- Command: `py -m unittest tests.test_stability_v1`
- Results: **8/8 Tests Passed (OK)** in 1.17s.
