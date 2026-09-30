# Phase 5 Notes: Voice Routing & Collision Guard

## 1. Summary of Changes
Implemented strict precedence, intent routing, and cross-tool collision guards between Browser Controller, Netflix Pilot, Visual HUD (`hud_video`), and Spotify (`spotify_control`).

### Graphify Entities Referenced:
- **`actions/hud_video.py`** [Community 80 / Node `hud_video`]
- **`actions/spotify_control.py`** [Community 120 / Node `spotify_control`]
- **`actions/netflix_pilot.py`** [Node `netflix_pilot`]
- **`core/hud_video/destination.py`** [Node `parse_explicit_destination`]
- **`core/hud_video/intent.py`** [Node `classify_hud_intent`]
- **`actions/computer_settings.py`** [Node `_detect_action`]

---

## 2. Intent Routing & Collision Table

| Spoken Phrase | Route | Collision Guarded Against |
| :--- | :--- | :--- |
| *"play Inception on Netflix"* | **Netflix Pilot** (`netflix_pilot`) | Intercepted in both `hud_video` and `spotify_control` via `\b(on\|in)\s+netflix\b` |
| *"play Inception trailer"* | **Visual HUD** (`hud_video`) | Diverted from `spotify_control` when query contains `trailer/teaser/clip` |
| *"play Inception soundtrack"* | **Spotify** (`spotify_control`) | Stays in Spotify; not intercepted by video or browser |
| *"close tab"*, *"shut this tab"* | **Browser Controller** (`close_active_tab`) | Explicitly prevented from colliding with `close_window` and Visual HUD `stop` |
| *"close the visual hud"* | **Visual HUD** (`action="stop"`) | Strictly targets HUD video player without affecting browser tabs |

---

## 3. HUD Status Line Toast
- `[Browser] Tab closed` displayed upon tab closure.
- `[Netflix] Profile: <Name>` displayed upon profile selection.
- `[Netflix] Searching: <Query>` / `[Netflix] Playing: <Title>` displayed during pilot navigation.

---

## 4. Verification & Test Results
- Unit test suite `tests/test_collision_guards.py`:
  - `test_play_on_netflix_routes_away_from_hud_video`: PASSED
  - `test_play_on_netflix_routes_away_from_spotify`: PASSED
  - `test_play_trailer_diverts_from_spotify_to_hud_video`: PASSED
  - `test_play_soundtrack_stays_on_spotify`: PASSED
  - `test_close_tab_never_collides_with_close_window`: PASSED
  - `test_close_tab_never_collides_with_hud_close`: PASSED
  - `test_close_visual_hud_intent`: PASSED
  - `test_netflix_pilot_tool_actions`: PASSED
