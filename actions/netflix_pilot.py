"""
actions/netflix_pilot.py — Netflix Pilot Action Tool for ALFRED.

Auto-discovered by core/action_loader.py.
Handles browser Netflix automation: opening, searching, playing, browsing genres,
and resolving the conversational profile gate.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from core.pilots.netflix.actions import (
    NetflixActions,
    get_netflix_actions,
    match_profile_selection,
)
from core.pilots.netflix.detector import NetflixDetector, NetflixState

_LOGGER = logging.getLogger(__name__)


def netflix_pilot(
    parameters: dict,
    response: Any = None,
    player: Any = None,
    session_memory: Any = None,
    speak: Optional[Any] = None,
) -> str:
    """Execute Netflix Pilot commands."""
    params = parameters or {}
    action = params.get("action", "open").lower().strip()
    query = params.get("query", "").strip()
    title = params.get("title", "").strip() or query
    profile_req = params.get("profile", "").strip()

    actions = get_netflix_actions()
    if speak is not None:
        actions.speak_fn = speak

    # 1. Open Netflix
    if action in ("open", "launch", "start"):
        res = actions.open_netflix()
        if player and hasattr(player, "show_toast"):
            player.show_toast("[Netflix] Opened")
        return res

    # 2. Search
    if action in ("search", "find"):
        if not query:
            return "Please specify what you would like to search on Netflix, sir."
        res = actions.search_netflix(query)
        if player and hasattr(player, "show_toast"):
            player.show_toast(f"[Netflix] Searching: {query[:25]}")
        return res

    # 3. Play
    if action in ("play", "stream", "watch"):
        target_title = title or query
        if not target_title:
            return "Please specify what you would like to play on Netflix, sir."
        res = actions.play_netflix(target_title)
        if player and hasattr(player, "show_toast"):
            player.show_toast(f"[Netflix] Playing: {target_title[:25]}")
        return res

    # 4. Browse Genre
    if action in ("browse", "genre", "category"):
        target_genre = query or params.get("genre", "")
        if not target_genre:
            return "Please specify which genre you would like to browse on Netflix, sir."
        res = actions.browse_genre(target_genre)
        if player and hasattr(player, "show_toast"):
            player.show_toast(f"[Netflix] Browse: {target_genre[:25]}")
        return res

    # 5. Profile selection
    if action in ("select_profile", "profile", "choose_profile"):
        state, detected = actions.detector.inspect_state(force=True)
        if state != NetflixState.PROFILE_GATE:
            return "No Netflix profile gate is currently on screen, sir."
        matched = match_profile_selection(profile_req, detected)
        if not matched:
            return f"Could not find profile '{profile_req}', sir."
        ok = actions.select_profile(matched)
        if ok:
            confirm = f"Accessing {matched.name}, sir."
            if player and hasattr(player, "show_toast"):
                player.show_toast(f"[Netflix] Profile: {matched.name}")
            return confirm
        return "Could not select that profile, sir."

    return f"Unknown Netflix Pilot action: '{action}'"


TOOL = {
    "name": "netflix_pilot",
    "description": (
        "Controls Netflix in the web browser or desktop app. "
        "Use this tool for: 'open Netflix', 'search Netflix for <query>', 'play <movie/show> on Netflix', "
        "'browse <genre> on Netflix', or selecting profiles ('Who's watching?'). "
        "Routes to Netflix Pilot, never to Visual HUD or Spotify."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "open | search | play | browse | select_profile",
            },
            "query": {
                "type": "STRING",
                "description": "Search query or genre name (e.g. 'Interstellar', 'Sci-Fi')",
            },
            "title": {
                "type": "STRING",
                "description": "Movie or show title to play on Netflix (e.g. 'Inception')",
            },
            "profile": {
                "type": "STRING",
                "description": "Profile name or ordinal (e.g. 'Aditya', 'Kids', 'first')",
            },
        },
        "required": ["action"],
    },
    "handler": netflix_pilot,
}
