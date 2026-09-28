# Sentry Mode v2 — Phase 3 Implementation Notes
**Phase:** 3 — FOCUS Engine Core: Session, Tick, Frontmost Reader, Privacy
**Status:** Completed & Verified
**Date:** 2026-09-29

---

## 1. Graphify Context & Symbols Relied On
- `SentryModeManager`: `register_focus_handlers(on_start, on_stop)` and `update_focus_state(...)` rate-limited updates.
- `JarvisLive._receive_audio` & `_execute_tool`: Voice tool routing for `sentry_focus`.
- `TOOL_DECLARATIONS`: Added `sentry_focus` tool schema for Gemini Live and client invocation.
- `BasePlatformReader` & `SurfaceIdentity`: Decoupled frontmost surface observation with zero cached state.

---

## 2. Components Created & Delivered

### 2.1. `core/sentry/focus/state.py` (`FocusState`)
- Strict whitelist dataclass for client and HUD consumption:
  ```python
  @dataclass(frozen=True, slots=True)
  class FocusState:
      active: bool = False
      paused: bool = False
      deferred_lock: bool = False
      locked_app: bool = False
      locked_tab: bool = False
      planned_s: int = 0
      elapsed_s: int = 0
      on_target_s: int = 0
      remaining_s: int = 0
      drifting: bool = False
      drift_count: int = 0
      current_drift_s: int = 0
      tier: int = 0
      snoozed_until_s: float = 0.0
      excused: bool = False
      nag_interval_s: int = 30
      intent_set: bool = False
  ```
- **Structural Privacy Law Verified:** FocusState contains zero strings, zero window titles, zero hostnames, zero URLs, and zero app names. The user's spoken intent string is stored strictly on the `FocusEngine` instance and never leaked into `FocusState`.

### 2.2. `core/sentry/focus/reader.py` & Cross-Platform Backends
- Fresh frontmost query every tick (no frozen OS event caches).
- Every query is bounded by `READER_TIMEOUT_MS = 250ms`.
- Host hashing: `sha256(host.strip().lower())[:16]`. URL paths, query parameters, and fragments are never parsed or stored.
- Home Base Rule: Any window belonging to ALFRED's own process is identified as `is_home_base=True, is_self=True`, never triggers a drift, and never receives a distraction label.
- Backends implemented:
  - `core/sentry/focus/platform/win.py`: Win32 `GetForegroundWindow` + PID + `psutil` + guarded UI Automation address bar extraction.
  - `core/sentry/focus/platform/mac.py`: `osascript` / `lsappinfo front` bundle identifier query + AppleScript Chrome/Brave/Edge tab URL extraction.
  - `core/sentry/focus/platform/linux.py`: Session auto-detection (`WAYLAND_DISPLAY` vs `DISPLAY`). X11 `xdotool`/`xprop` + Wayland IPC/DBus with title heuristics.

### 2.3. `core/sentry/focus/engine.py` (`FocusEngine`)
- Runs on its own dedicated thread with a 1-second tick (`TICK_INTERVAL_S = 1.0s`), completely independent of HUD window existence.
- Restoring or recreating the HUD window re-attaches to the running session without losing countdown state.
- Controls implemented:
  - `start(duration_minutes, intent, lock_app, lock_tab)`
  - `pause()` & `resume()`
  - `extend(minutes)`
  - `abort(reason)`
  - `snooze(seconds)` (silences drift alerting until timestamp)
  - `excuse(reason)` (refunds current excursion, stays silent until back on target)
  - `set_nag_interval(seconds)` (bounded within `[NAG_MIN_S, NAG_MAX_S]`)
  - `lock_surface(app_id, tab_host_hash)`
  - `deferred_lock` (settle rule: locks onto the first non-home-base app/tab used after starting)

### 2.4. `actions/sentry_focus.py` & `main.py`
- Added `sentry_focus` tool schema to `TOOL_DECLARATIONS`.
- Registered `FocusEngine` callbacks with `SentryModeManager`.
- Handled voice controls: *"focus for 25"*, *"thirty minutes on this"*, *"pause focus"*, *"resume focus"*, *"give me ten more"*, *"snooze"*, *"excuse"*, and *"nag cadence"*.

---

## 3. Verification & Acceptance Testing

### 3.1. Privacy Assertion Gate (`tests/focus/test_state_privacy.py`)
- Drove a session with synthetic identities whose `app_id`, `host`, `spoken_label`, and `intent` were unique random UUID tokens.
- Verified that **none** of the synthetic tokens appeared in `asdict(state)`, `SentrySnapshot`, or serialized payloads.
- Verified that URL hostnames are always hashed and never stored in plain text.

### 3.2. Engine Lifecycle & Fresh Query Gate (`tests/focus/test_focus_engine.py`)
- Verified pause/resume freezes and unfreezes countdown without losing elapsed seconds.
- Verified fresh query behavior: logged two different applications in consecutive ticks, accurately transitioning from on-target to drifting.
- Verified snooze and excuse behaviors.
- Verified countdown survives HUD minimize/close/recreation (`test_session_survives_hud_lifecycle`).

### 3.3. Platform Reader Gate (`tests/focus/test_platform_readers.py`)
- Verified URL parsing, domain isolation, case insensitivity, and 16-character truncation.
- Verified platform reader instantiation and capability reporting.

All 7 focus tests and all 17 sentry tests pass (24 total unit tests).

---

## 4. Next Phase Readiness
Phase 3 is complete. Ready for **Phase 4: Drift detection, tiers, labels, and canned pools**.
