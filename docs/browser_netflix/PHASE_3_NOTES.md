# Phase 3 Notes: Profile Gate Handling & Dialog Flow

## 1. Summary of Changes
Implemented interactive conversational handling of the Netflix "Who's watching?" profile selection gate using single-utterance `AnswerWindow` without requiring a wake word.

### Graphify Entities Referenced:
- **`core/sentry/answer_window.py`** [Community 80 / Node `AnswerWindow`]
- **`core/pilots/netflix/detector.py`** [Node `NetflixDetector`, `ProfileSlot`]
- **`core/pilots/netflix/actions.py`** [Node `NetflixActions`, `handle_profile_gate`]

---

## 2. Profile Selection Workflow
1. **Gate Detection:**
   When Netflix is opened or navigates to `PROFILE_GATE`, ALFRED detects the gate anchor (`"Who's watching?"`) and parses the available profile cards sorted horizontally (slots 1 to N).
2. **Conversational Question:**
   ALFRED asks: *"Which profile shall I select, sir?"* via `AnswerWindow(timeout_s=6.0)`.
3. **No-Wake-Word Single Utterance:**
   The mic is un-gated immediately, capturing the user's spoken reply (e.g., *"Aditya"*, *"second"*, *"Kids"*, *"profile 1"*).
4. **Fuzzy & Ordinal Parser:**
   - Ordinal numbers (*"first"*, *"1"*, *"second"*, *"2"*, etc.) map directly to slot indices.
   - Profile names are matched via exact match, substring, or fuzzy similarity (`difflib`).
5. **Targeting:**
   Profile is clicked via coordinate click on the avatar center, falling back to keyboard `Tab` sequences + `Enter`.
6. **Confirmation:**
   ALFRED confirms: *"Accessing [Profile], sir."*
7. **Not Logged In Guard:**
   If `NetflixState.NOT_LOGGED_IN` is detected, ALFRED informs: *"Netflix is not logged in on this browser, sir."* and does not attempt credential entry.

---

## 3. Verification & Test Results
- Unit tests in `tests/test_netflix_actions.py`:
  - `test_match_profile_selection_by_name`: PASSED
  - `test_match_profile_selection_by_slot_number`: PASSED
  - `test_match_profile_selection_fuzzy`: PASSED
  - `test_handle_profile_gate_flow`: PASSED
  - `test_open_netflix_not_logged_in_flow`: PASSED
