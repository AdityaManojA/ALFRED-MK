# ALFRED-MK-V: Streaming Providers — Netflix + Crunchyroll
## Phase 5 Implementation Notes: Voice Routing & Precedence

**Date:** 2026-10-07  
**Status:** Complete  

### Graphify / Code Nodes Updated
- `core_intents_router_intentrouter` (`core/intents/router.py`)
- `core_intents_router_intentrouter_route` (`core/intents/router.py`)
- `actions_streaming_pilot_streaming_pilot` (`actions/streaming_pilot.py`)
- `actions_streaming_pilot_get_active_streaming_session` (`actions/streaming_pilot.py`)
- `tests_test_streaming_routing_precedence` (`tests/test_streaming_routing_precedence.py`)

### Deliverables
1. **`core/intents/router.py`**:
   - Implemented strict 6-level voice routing precedence in `route(utterance, context)`:
     1. **Explicit provider:** `"play X on Netflix"`, `"open Crunchyroll"`, `"watch X on Crunchyroll"` routes directly to `streaming_pilot`.
     2. **Visual HUD transport:** Pause/resume/seek while Visual HUD video is actively playing (`context["is_hud_video_playing"] == True`) keeps precedence over any "play" route.
     3. **Provider-internal transport:** When a provider is `PLAYING` or active, transport commands (`pause`, `resume`, `skip intro`, `next episode`, `full screen`) route to `streaming_pilot` transport, NOT to Visual HUD and NOT to Sentry FOCUS pause.
     4. **YouTube / browser:** Unchanged, routes to `browser_control`.
     5. **Spotify:** Unchanged, gated strictly on Spotify readiness (if unready, returns `spotify_not_configured` with zero API calls).
     6. **Ambiguous 'play X':** Checks conversation context; if genuinely ambiguous, asks `"Music or video, sir?"` without guessing.
2. **`actions/streaming_pilot.py`**:
   - Universal action handler exposing `streaming_pilot` tool.
   - Enforces the strict **Readiness Gate** (Spotify rule):
     - `NOT_INSTALLED`: Reports not found and offers browser alternative.
     - `NOT_LOGGED_IN`: Reports unauthenticated state cleanly without opening search.
     - `DRM_UNSUPPORTED`: Explains Widevine CDM failure.
     - Makes zero navigation or search calls if not `READY`.
   - Tracks active streaming session state for transport precedence.
3. **Verification**:
   - `tests/test_streaming_routing_precedence.py` covers all 6 precedence cases.
   - 6/6 tests passed (0.001s).
   - Collision guard test suite (`tests/test_collision_guards.py`) passed (8/8 tests OK).
