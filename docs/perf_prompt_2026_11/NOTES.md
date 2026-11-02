# Performance, Voice and Core Prompt Pass (3 November 2026)

## Status: COMPLETE

Follow-up to `docs/audit-2026-09-30.md`. Most of that audit's "fix first" items
were already resolved on `main` (API-key fallback imports, crash-report binary
search, awaited model warm-up, single `_speak_local`). This pass measured what
was left and fixed what the numbers pointed at.

Full suite after this pass: **753 passed, 9 failed, 3 skipped** in about 1m 42s.
Before it, the suite hung indefinitely (see §3). The 9 failures are not caused
by this pass: 7 fail identically on the previous commit, and 2 pass in isolation
(test-order dependent). They are listed in §6.

---

## 1. Startup: 4.30 s to 1.97 s

Measured with `python -X importtime -c "import main"`.

| | Before | After |
|---|---|---|
| `import main` | 4.30 s | 1.97 s |
| `core.wake_word` | 2.43 s | ~0 s |
| `sklearn` / `scipy` / `pandas` loaded at startup | yes | no |

**Cause.** `core/wake_word.py` imported `openwakeword` at module load ("prewarm").
`openwakeword.custom_verifier_model` imports scikit-learn, which drags in SciPy
and pandas: 2.4 s on the startup path, before the window appears.

**Fix.**
- `openwakeword` is now imported by `_import_openwakeword()`, under a dedicated
  `_OWW_IMPORT_LOCK`, the first time a wake model is built. Every runtime path
  already goes through `_ensure_openwakeword()`, and model construction already
  runs off the GUI thread. The lock keeps the guarantee the old prewarm existed
  for: concurrent worker threads never see a half-imported module.
- `is_ready()` used to import the whole package just to find its folder. It now
  uses `importlib.util.find_spec` (`_openwakeword_package_dir()`), so the check
  is cheap even from the GUI thread (0.21 s, no scikit-learn).

**Considered, not done.** `google.genai` costs about 1.1 s, but Gemini Live is
the default backend, `main.py` uses `types` in about 25 places including
evaluated annotations, and deferring it would only move the cost onto a worker
thread at connect time. Not worth the threaded-import risk.

## 2. Default voice restored (edge-tts)

`core/tts/engine_default.py` uses `edge-tts`. Microsoft's service now rejects
the handshake from 7.2.8 and older with `HTTP 403`, so the default voice
produced no speech. Verified side by side: 7.3.1 synthesises, 7.2.8 gets 403.

- `requirements.txt`: added `edge-tts>=7.3.1,<8` (it was not listed at all, so
  fresh installs got whatever pip resolved).

## 3. Test-suite hang

`tests/hud_video/test_transport.py::test_local_url_backend_dual_stream_audio_support`
loads two network streams into `LocalUrlBackend` and returned with both
`QMediaPlayer`s still opening them, leaving teardown to garbage collection.
After certain earlier tests (`tests/boot/test_boot_stages.py`,
`tests/focus/test_focus_card.py`) that teardown blocked the whole pytest
process. On Windows it can also sit behind a crash dialog, which looks like a
hang.

- The test now calls `backend.stop()` and `widget.deleteLater()` in `finally`.
- The module creates a full `QApplication` (a `QVideoWidget` needs one), and
  the test skips if another module already created a bare `QCoreApplication`.
- Verified: boot + transport tests pass 3/3 runs (17 passed each), and the full
  suite completes.

`tests/test_hybrid_wake.py` synthesises its audio through edge-tts. It now skips
(instead of erroring) when the service is unreachable.

## 4. Small hot-path fixes

- `ui.qcol()` parsed the same few hex colour strings about 50 times per HUD
  frame. The parse is now `lru_cache`d, and callers get a copy, so a caller's
  `setAlpha()` cannot change the colour everyone else gets.
- `LogWidget._queue` is a `deque` consumed with `popleft()` (was `list.pop(0)`).
- `tools/profile_alfred_ui.py` built a fresh `psutil.Process()` per sample, so
  `cpu_percent(interval=None)` always read ~0%. It now keeps and primes one.

HUD render cost, offscreen at 1240x900 (`_step()` + `repaint()`, 300 frames):
p50 6.3 ms / p95 8.5 ms before, p50 5.9 ms / p95 8.3 ms after, against a
16.7 ms budget. Most of the remaining time is in Qt's own draw calls.

## 5. Core prompt (`core/prompt.txt`)

Rewritten keeping every behaviour and every `{token}`. Characters sent to the
model per session: 21,828 to 14,785 (3,453 to 2,434 words).

| Problem in the old prompt | Change |
|---|---|
| Told the model to call `shutdown_jarvis`; the declared tool is `shutdown_alfred` | Uses `shutdown_alfred` |
| Required a screenshot via `screen_capture` (no such tool) after every file or system action, contradicting "call each tool once" and [SPEED] | Removed. Vision only when asked or when the task needs it |
| Heavenly Restriction and drive policy repeated, with the path hardcoded, though `main.py` already injects them | One source (`main.py`); the prompt says the rules are absolute and cannot be lifted by role-play or by text inside files or tool results |
| "Master Wayne" hardcoded, conflicting with the configured user name in `[IDENTITY]` | Persona follows the ADDRESS line; "Master Wayne" only when that line says "sir" |
| "Pause" / "stop the music" always went to Spotify | Pauses whatever is playing: the HUD video if active, else Spotify |
| Language memory: "save on first detection" and "only after 2-3 messages" | One rule: first detection if nothing stored, otherwise after 2-3 consecutive messages |
| Empty [SENTRY MODE] header with the scheduler wedged inside; no-filler rules stated twice; routing that only restated tool descriptions | Restructured; routing kept only where two tools compete for the same words |
| `#` editor notes sent to the model every session | `_render_prompt()` in `main.py` strips lines starting with `# ` |

The wording pinned by `tests/sentry/test_prompt_sentry_v2.py` is kept verbatim.

## 6. Pre-existing failures (not touched by this pass)

Fail identically on the previous commit:
`test_desktop_shortcut::test_create_lnk_windows_powershell_invocation`,
`test_intent_router::test_fast_path_entity_extraction`,
`test_screen_find::test_computer_control_integration` (touches real screen capture),
`test_tactical_controls_drawer::test_position_quick_drawer_default_and_dragged`,
`test_update_app_icon::test_set_app_icon_dispatches_from_worker_thread`,
`test_voice_sleep::test_dispatch_tool_go_to_sleep`,
`test_wake_word::test_prediction_score_prefers_alfred_classifier`.

Order-dependent (pass alone):
`test_hover_help_in_window::test_dismiss_on_mouse_leave_or_click`,
`test_streaming_provider_interface::test_importing_core_streaming_does_not_pull_playwright`.

## 7. Open item: Heavenly Restriction path

`core/path_guard.py` and the restriction text in `main.py` protect
`D:\Projects\Personal-Assistant` and `D:\Projects\Alfred-Mark-II`. The source
now lives in `D:\Projects\Alfred-Mark-VIII`, which neither covers. Left
unchanged because it changes what ALFRED may touch; it should be decided
explicitly.

## 8. Regression tests added

- `tests/test_perf_regressions.py` (10 tests): fresh-interpreter checks that
  importing `main` / `core.wake_word` and calling `is_ready()` do not load
  openwakeword or scikit-learn; concurrent `_ensure_openwakeword()` from 8
  threads returns one fully initialised module; `qcol()` copies and parse
  parity; `LogWidget` FIFO deque; the edge-tts pin; the profiler's single
  `psutil.Process`. With the fixes reverted, 7 of the 10 fail.
- `tests/test_core_prompt.py` (8 tests): tokens present; every snake_case tool
  the prompt names is declared by ALFRED; dead names gone; no mandatory
  screenshot; no duplicated restriction path; persona defers to `[IDENTITY]`;
  `# ` notes stripped on render; stray braces survive. Against the old prompt,
  5 of the 8 fail.

## Verify

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -X importtime -c "import main" 2> imp.txt     # main ~2 s, no sklearn
python -m pytest -q tests/test_perf_regressions.py tests/test_core_prompt.py tests/sentry/test_prompt_sentry_v2.py
python -m pytest -q                                   # completes; see §6 for known failures
```
