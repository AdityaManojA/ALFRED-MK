# Phase 4 Notes: Netflix Search & Browse Automation

## 1. Summary of Changes
Implemented voice-driven search, playback, and category browsing automation in `core/pilots/netflix/actions.py`.

### Graphify Entities Referenced:
- **`core/pilots/netflix/actions.py`** [Node `NetflixActions`]
- **`actions/browser_control.py`** [Community 18]

---

## 2. Actions Architecture

### 1. Voice Search: *"search Netflix for [query]"*
- Targets search via `/` hotkey or URL navigation fallback (`/search?q=...`).
- Keystrokes are typed cleanly using humanized delay constant `KEY_DELAY_MS = 25`.
- ALFRED speech confirmation: *"Searching Netflix for '[query]', sir."*

### 2. Instant Play: *"play [movie/show] on Netflix"*
- Executes search -> waits for results grid to settle (`SETTLE_DELAY_MS = 1200`).
- Targets first result card (top-left card at ~25% width, ~32% height) and activates playback via Enter/Space.
- ALFRED speech confirmation: *"Playing '[movie/show]', sir."*

### 3. Category & Genre Browse: *"browse [genre] on Netflix"*
- Maps common genre names (`action`, `comedy`, `drama`, `sci-fi`, `horror`, `anime`, etc.) to Netflix genre IDs (`/browse/genre/[id]`).
- Navigates directly to the curated category page.
- ALFRED speech confirmation: *"Browsing [Genre] on Netflix, sir."*

---

## 3. Verification & Test Results
- Unit tests in `tests/test_netflix_actions.py`:
  - `test_search_netflix_flow`: PASSED
  - `test_play_netflix_flow`: PASSED
  - `test_browse_genre_flow`: PASSED
