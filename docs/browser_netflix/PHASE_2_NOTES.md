# Phase 2 Notes: Netflix State Detection Engine

## 1. Summary of Changes
Implemented `core/pilots/netflix/detector.py` providing on-demand snapshot inspection of Netflix web surfaces (`netflix.com`) and native desktop applications.

### Graphify Entities Referenced:
- **`actions/screen_find.py`** [Community 80 / Node `get_rapid_ocr`]
- **`actions/screen_processor.py`** [Community 80 / Node `capture_screen`]
- **`core/sentry/focus/reader.py`** [Community 80 / Node `SurfaceIdentity`]

---

## 2. State Detection Design & Architecture
- **State Enum (`NetflixState`):**
  - `NOT_LOGGED_IN`: Landing/membership screen detected (`Sign In`, `Unlimited movies`, `Get Started`).
  - `PROFILE_GATE`: "Who's watching?" profile selection gate detected.
  - `BROWSE_HOME`: Standard browse home grid / billboard surface active (`Home`, `TV Shows`, `Movies`, `My List`).
  - `PLAYING`: Video player surface active (`Skip Intro`, `Episodes & Info`, `Audio & Subtitles`, `Back to Browse`).
  - `UNKNOWN`: Fallback.

- **Zero Continuous Polling (0 Hz):**
  - The detector only runs on-demand when invoked directly or on initial navigation.
  - If Netflix is not the frontmost window (`is_netflix_frontmost() == False`), `inspect_state()` returns `NetflixState.UNKNOWN` immediately without triggering screen captures or OCR sessions.

- **Profile Slot Extraction:**
  - On `PROFILE_GATE`, detected profile labels are horizontally sorted from left to right (slot 1 to N).
  - Center coordinates are calculated in normalized coordinates `(norm_x, norm_y)` for instant keyboard / coordinate targeting.

- **Privacy Compliance:**
  - Only anchor tokens and ephemeral layout coordinates are inspected in-memory.
  - Zero watching history, email addresses, or credentials are read, saved, or logged.

---

## 3. Verification & Test Results
- Unit test suite `tests/test_netflix_detector.py`:
  - `test_profile_gate_detection_and_slot_extraction`: PASSED
  - `test_not_logged_in_detection`: PASSED
  - `test_browse_home_detection`: PASSED
  - `test_playing_state_detection`: PASSED
  - `test_unknown_state_fallback`: PASSED
  - `test_zero_polling_when_not_frontmost`: PASSED
- Benchmark check: Detection latency per check is < 0.005s for token evaluation, well under the 1.5s target.
