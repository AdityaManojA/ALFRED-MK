# Sentry Mode v2 — Phase 4 Implementation Notes
**Phase:** 4 — Drift Detection, Tiers, Labels, and Canned Dialogue Pools
**Status:** Completed & Verified
**Date:** 2026-09-29

---

## 1. Graphify Context & Symbols Relied On
- `FocusEngine.tick()`: Expanded to evaluate `DRIFT_GRACE_MS` grace window before engaging drift state.
- `FocusEngine._speak_fn`: Transient single-tick conduit for spoken callouts with zero persistence.
- `resolve_distraction_label` & `SurfaceIdentity`: Label extraction decoupled from core state tracking.

---

## 2. Components Created & Delivered

### 2.1. `core/sentry/focus/labels.py` (`resolve_distraction_label`)
- `NAME_DISTRACTIONS: bool = True` global switch at the top of the file; toggling False drops down to nameless pools.
- `HOST_LABEL_MAP`: Distraction domain translation for major sites (YouTube, Instagram, X/Twitter, Reddit, TikTok, Netflix, Twitch, Facebook, LinkedIn, Gmail, Discord, Amazon, Hulu, Disney+, Pinterest).
- Unmapped browser sites: Extracted bare registrable domain (`foobar-docs.org`).
- Desktop apps: Extracted application display name or capitalized executable name.
- **Home Base Invariant:** ALFRED HUD is never labelled (returns `""`).

### 2.2. `core/sentry/focus/lines.py` (Dialogue Pools)
- **Four lines per tier**, each with `{label}` and `{intent}` placeholders where appropriate:
  - `FIRST_CALLOUT`: Dual-attribution callouts naming both stated intent and distraction (e.g. *"Sir — {label} does not look like '{intent}' to me."*).
  - `TIER1` (Subtle): Gentle reminders (*"Sir, {label} can wait."*, *"A brief detour into {label}, sir?"*).
  - `TIER2` (Firm): Direct reminders (*"Twice into {label}, sir. It is starting to look deliberate."*, *"Sir, {label} is consuming the session."*).
  - `TIER3` (Blunt): Urgent callouts (*"Third time in {label}, sir. The detours are becoming the project."*, *"Sir, {label} has completely derailed this session. Return to target."*).
  - `NAMELESS`: Fallback pool when `NAME_DISTRACTIONS` is disabled (*"Sir, you have drifted from your task."*).
  - `DRILL_SERGEANT`: High-urgency drill sergeant pool selectable by voice (*"Drop the {label}, sir! Get back to work immediately!"*).

### 2.3. Grace Window & Escalation Engine (`core/sentry/focus/engine.py`)
- **Grace Window (`DRIFT_GRACE_MS = 800`):** Brief excursions under 800ms (such as switching tabs or checking a notification) are filtered out without triggering drift state or speech.
- **Consecutive Drift Escalation:**
  - 1st excursion: Tier 1
  - 2nd excursion: Tier 2
  - 3rd+ excursion: Tier 3
- **Nag Cadence:** Repeating drift alerts occur every `nag_interval_s` while an excursion persists.
- **Drill Sergeant Mode:** Enabled/disabled via `set_drill_sergeant(True/False)` or voice tool action.

---

## 3. Privacy Law & Acceptance Verification

### 3.1. Strict Label Privacy Gate (`tests/focus/test_label_privacy.py`)
- Drove an excursion with a random nonsense label (e.g., `zq-vortex-8813...`).
- Confirmed that the label was spoken aloud in the verbal callout.
- Confirmed that the label appeared **nowhere else**: absent from `FocusState`, absent from `asdict(state)`, absent from `SentrySnapshot`, and absent from any files or logs.

### 3.2. Acceptance Scenario Verification
Verified callouts across all three target categories:
1. **Mapped Site (`youtube.com`):** `"Sir, YouTube can wait."`
2. **Unmapped Site (`foobar-docs.org`):** `"A brief detour into foobar-docs.org, sir?"`
3. **Desktop Application (`Steam`):** `"A brief detour into Steam, sir?"`
4. **Drill Sergeant Mode:** `"Drop the YouTube, sir! Get back to work immediately!"`
5. **Nameless Mode (`NAME_DISTRACTIONS = False`):** `"Sir, you have drifted from your task."`

### 3.3. Test Suite Status
All 12 focus tests and all 17 sentry tests pass (29 total unit tests).

---

## 4. Next Phase Readiness
Phase 4 is complete. Ready for **Phase 5: Deferred lock, settle rule, voice routing ahead of screen lock, card trap**.
