"""
actions/streaming_pilot.py — Universal Streaming Pilot Tool for ALFRED.

Dispatches to StreamingProviders (Netflix, Crunchyroll, etc.) behind the unified
abstraction. Enforces the strict Readiness Gate (Spotify rule):
If not READY, makes zero navigation or search calls, explains why, and offers alternatives.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from core.streaming.preferences import (
    forget_preferred_surface,
    get_audio_preference,
    resolve_surface,
    set_audio_preference,
)
from core.streaming.provider import (
    CapabilityClass,
    ProviderState,
    Readiness,
    Result,
    Surface,
    Title,
)
from core.streaming.registry import get_provider_registry

_LOGGER = logging.getLogger(__name__)

# Active session tracking
_ACTIVE_PROVIDER_ID: Optional[str] = None
_ACTIVE_SURFACE: Optional[Surface] = None
_ACTIVE_STATE: ProviderState = ProviderState.HOME


def get_active_streaming_session() -> tuple[Optional[str], Optional[Surface], ProviderState]:
    """Return active provider id, surface, and state for transport precedence checks."""
    return _ACTIVE_PROVIDER_ID, _ACTIVE_SURFACE, _ACTIVE_STATE


def set_active_streaming_session(provider_id: Optional[str], surface: Optional[Surface], state: ProviderState) -> None:
    """Update active streaming provider state."""
    global _ACTIVE_PROVIDER_ID, _ACTIVE_SURFACE, _ACTIVE_STATE
    _ACTIVE_PROVIDER_ID = provider_id
    _ACTIVE_SURFACE = surface
    _ACTIVE_STATE = state


def streaming_pilot(
    parameters: dict,
    response: Any = None,
    player: Any = None,
    session_memory: Any = None,
    speak: Optional[Any] = None,
) -> str:
    """Execute unified Streaming Pilot commands for Netflix and Crunchyroll."""
    params = parameters or {}
    provider_id = (params.get("provider") or "netflix").lower().strip()
    action = (params.get("action") or "open").lower().strip()
    query = (params.get("query") or "").strip()
    title = (params.get("title") or "").strip() or query
    profile_req = (params.get("profile") or "").strip()
    surface_override = (params.get("surface") or "").strip()
    audio_pref = (params.get("audio_pref") or "").strip()

    registry = get_provider_registry()
    provider = registry.get(provider_id)
    if not provider:
        return f"Unknown streaming provider '{provider_id}', sir."

    # Helper to update active session and notify HUD status
    def _sync_status(p_id: Optional[str], surf: Optional[Surface], st: ProviderState) -> None:
        """Record the active streaming session and mirror it to the player UI if supported."""
        set_active_streaming_session(p_id, surf, st)
        if player and hasattr(player, "set_streaming_status"):
            surf_str = getattr(surf, "id", "web") if surf else ""
            st_val = st.value if hasattr(st, "value") else str(st)
            player.set_streaming_status(p_id or "", surf_str, st_val)

    # 1. Forget Surface Preference
    if action in ("forget_surface", "forget_browser"):
        ok = forget_preferred_surface(provider.id)
        if ok:
            return f"I have forgotten your preferred surface for {provider.display_name}, sir."
        return f"No preferred surface was saved for {provider.display_name}, sir."

    # 2. Surface Resolution (Ask-Once Memory via One-Shot Prompt)
    def _prompt_surface_choice(prompt_text: str, _: Any = None) -> Optional[str]:
        """Ask the user via the active answer window and return the reply, or None."""
        try:
            from core.registry import get as reg_get
            ans_win = reg_get("active_answer_window")
            if ans_win and hasattr(ans_win, "request_answer_sync"):
                reply = ans_win.request_answer_sync(prompt_speech=prompt_text)
                return reply if reply else None
        except Exception:
            pass
        return None

    surface, should_update_pref = resolve_surface(
        provider,
        explicit_override=surface_override,
        prompt_fn=_prompt_surface_choice,
    )
    if not surface:
        return f"I could not detect any installed browser or app for {provider.display_name}, sir. Please install Chrome, Edge, or the native app."

    # 3. Readiness Gate (Hard Gate: Zero calls if not READY)
    readiness = provider.readiness(surface)
    if readiness == Readiness.NOT_INSTALLED:
        return f"{provider.display_name} is not installed on this machine, sir. Would you like me to open it in a browser?"
    elif readiness == Readiness.NOT_LOGGED_IN:
        return f"{provider.display_name} is not logged in on {surface.display_name}, sir. Please log in first."
    elif readiness == Readiness.DRM_UNSUPPORTED:
        return f"{provider.display_name} playback cannot decode protected DRM on {surface.display_name}, sir. Please use your standard browser."
    elif readiness == Readiness.UNAVAILABLE:
        return f"{provider.display_name} is currently unavailable on this surface, sir."

    # 4. Action Execution
    if action in ("open", "launch", "start"):
        res = provider.open(surface)
        if res.ok:
            _sync_status(provider.id, surface, ProviderState.HOME)
            if should_update_pref:
                from core.streaming.preferences import set_preferred_surface
                set_preferred_surface(provider.id, surface.id)
            if player and hasattr(player, "show_toast"):
                player.show_toast(f"[{provider.display_name}] Opened ({surface.display_name})")
        return res.message

    elif action in ("search", "find"):
        if not query:
            return f"Please specify what you would like to search on {provider.display_name}, sir."
        results = provider.search(surface, query)
        if player and hasattr(player, "show_toast"):
            player.show_toast(f"[{provider.display_name}] Searching: {query[:25]}")
        if results:
            return f"Found '{results[0].name}' on {provider.display_name}, sir."
        return f"No results found for '{query}' on {provider.display_name}, sir."

    elif action in ("play", "stream", "watch"):
        target_name = title or query
        if not target_name:
            return f"Please specify what you would like to play on {provider.display_name}, sir."
        # Create candidate title
        t = Title(
            id=target_name.lower().replace(" ", "-"),
            name=target_name,
            audio_type=audio_pref if audio_pref in ("sub", "dub") else None,
        )
        res = provider.play(surface, t)
        if res.ok:
            _sync_status(provider.id, surface, ProviderState.PLAYING)
            if should_update_pref:
                from core.streaming.preferences import set_preferred_surface
                set_preferred_surface(provider.id, surface.id)
            if player and hasattr(player, "show_toast"):
                player.show_toast(f"[{provider.display_name}] Playing: {target_name[:25]}")
        return res.message

    elif action in ("select_profile", "profile", "choose_profile"):
        target_label = profile_req
        if not target_label:
            profiles = provider.list_profiles(surface)
            if not profiles:
                return f"No profiles detected for {provider.display_name}, sir."
            labels = ", ".join(p.label for p in profiles)
            # Try asking once via answer window
            chosen_reply = _prompt_surface_choice(f"Available profiles are: {labels}. Which shall I select, sir?")
            if not chosen_reply:
                return f"Available profiles are: {labels}. Which shall I select, sir?"
            target_label = chosen_reply.strip()

        res = provider.select_profile(surface, target_label)
        if res.ok:
            _sync_status(provider.id, surface, ProviderState.HOME)
            if player and hasattr(player, "show_toast"):
                player.show_toast(f"[{provider.display_name}] Profile selected")
        return res.message

    elif action == "skip_intro":
        if hasattr(provider, "skip_intro"):
            res = provider.skip_intro(surface)
            return res.message
        return "Skip intro is not supported by this provider, sir."

    elif action in ("pause", "resume", "stop"):
        try:
            import pyautogui
            pyautogui.FAILSAFE = False
            pyautogui.press("space")
            if action == "pause":
                _sync_status(provider.id, surface, ProviderState.PAUSED)
            elif action == "resume":
                _sync_status(provider.id, surface, ProviderState.PLAYING)
            elif action == "stop":
                _sync_status(None, None, ProviderState.HOME)
            return f"{action.capitalize()}d playback, sir."
        except Exception:
            return "Could not send playback command, sir."

    elif action == "next_episode":
        if hasattr(provider, "next_episode"):
            res = provider.next_episode(surface)
            return res.message
        try:
            import pyautogui
            pyautogui.FAILSAFE = False
            pyautogui.hotkey("shift", "n")
            return "Advancing to next episode, sir."
        except Exception:
            return "Could not advance to next episode, sir."

    return f"Unknown streaming action: '{action}'"


TOOL = {
    "name": "streaming_pilot",
    "description": (
        "Controls streaming providers (Netflix, Crunchyroll) across native desktop apps and browsers. "
        "Supports open, search, play, profile selection, skip intro, and playback transport. "
        "Strictly respects user preference and readiness gates."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "provider": {
                "type": "STRING",
                "description": "netflix | crunchyroll",
            },
            "action": {
                "type": "STRING",
                "description": "open | search | play | select_profile | skip_intro | pause | resume | next_episode | forget_surface",
            },
            "query": {
                "type": "STRING",
                "description": "Search term or title",
            },
            "title": {
                "type": "STRING",
                "description": "Movie, anime, or show title",
            },
            "profile": {
                "type": "STRING",
                "description": "Profile name to select",
            },
            "surface": {
                "type": "STRING",
                "description": "Explicit surface override (e.g. 'chrome', 'edge', 'app')",
            },
            "audio_pref": {
                "type": "STRING",
                "description": "sub | dub (for Crunchyroll)",
            },
        },
        "required": ["provider", "action"],
    },
    "handler": streaming_pilot,
}
