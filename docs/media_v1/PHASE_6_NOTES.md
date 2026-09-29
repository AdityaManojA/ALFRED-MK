# Media Command v1 — Phase 6: Image Action and Routing

- Added the auto-discovered `show_image` tool. Its response exposes only `{shown, source}` to the chat brain.
- Local paths are attempted before web search. Openverse downloads are byte-capped and routed through the query-free cache before display.
- Added `core/imagery/intent.py` to reserve `show me the file …` for explicit local paths ahead of generic image matching.
