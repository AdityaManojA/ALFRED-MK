"""
core/streaming/preferences.py — Ask-Once Surface Memory and Persistence.

Persists streaming provider preferences under `streaming.<provider>.surface`
in `config/api_keys.json` via `memory.config_manager`. Reuses silently;
re-asks only if a surface disappears, capability degrades, or user explicitly overrides.
"""
from __future__ import annotations

import logging
from typing import Callable, List, Optional, Tuple

from core.streaming.provider import CapabilityClass, StreamingProvider, Surface
from memory.config_manager import _update_config, load_api_keys

_LOGGER = logging.getLogger(__name__)

CRUNCHYROLL_DEFAULT_AUDIO: str = "sub"


def get_preferred_surface(provider_id: str) -> Optional[str]:
    """Retrieve saved surface ID for a provider (e.g. 'chrome', 'netflix_native')."""
    cfg = load_api_keys()
    streaming_cfg = cfg.get("streaming", {})
    if isinstance(streaming_cfg, dict):
        p_cfg = streaming_cfg.get(provider_id.lower().strip(), {})
        if isinstance(p_cfg, dict):
            val = p_cfg.get("surface")
            if val and isinstance(val, str):
                return val.strip()
    return None


def set_preferred_surface(provider_id: str, surface_id: str) -> None:
    """Persist `streaming.<provider>.surface = <surface_id>`."""
    pid = provider_id.lower().strip()
    sid = surface_id.strip()

    def _mutator(data: dict) -> None:
        if "streaming" not in data or not isinstance(data["streaming"], dict):
            data["streaming"] = {}
        if pid not in data["streaming"] or not isinstance(data["streaming"][pid], dict):
            data["streaming"][pid] = {}
        data["streaming"][pid]["surface"] = sid

    _update_config(_mutator)
    _LOGGER.info("[StreamingPref] Saved preferred surface: streaming.%s.surface = %s", pid, sid)


def forget_preferred_surface(provider_id: str) -> bool:
    """Clear saved surface preference for a provider."""
    pid = provider_id.lower().strip()
    removed = [False]

    def _mutator(data: dict) -> None:
        if "streaming" in data and isinstance(data["streaming"], dict):
            if pid in data["streaming"] and isinstance(data["streaming"][pid], dict):
                if "surface" in data["streaming"][pid]:
                    del data["streaming"][pid]["surface"]
                    removed[0] = True

    _update_config(_mutator)
    if removed[0]:
        _LOGGER.info("[StreamingPref] Cleared preferred surface for %s", pid)
    return removed[0]


def get_audio_preference(provider_id: str = "crunchyroll") -> str:
    """Retrieve remembered audio language preference (e.g. 'sub' or 'dub')."""
    cfg = load_api_keys()
    streaming_cfg = cfg.get("streaming", {})
    if isinstance(streaming_cfg, dict):
        p_cfg = streaming_cfg.get(provider_id.lower().strip(), {})
        if isinstance(p_cfg, dict):
            pref = p_cfg.get("audio_pref")
            if pref in ("sub", "dub"):
                return pref
    return CRUNCHYROLL_DEFAULT_AUDIO


def set_audio_preference(provider_id: str, audio_pref: str) -> None:
    """Persist audio preference ('sub' or 'dub') for a provider."""
    pid = provider_id.lower().strip()
    pref = audio_pref.lower().strip()
    if pref not in ("sub", "dub"):
        pref = CRUNCHYROLL_DEFAULT_AUDIO

    def _mutator(data: dict) -> None:
        if "streaming" not in data or not isinstance(data["streaming"], dict):
            data["streaming"] = {}
        if pid not in data["streaming"] or not isinstance(data["streaming"][pid], dict):
            data["streaming"][pid] = {}
        data["streaming"][pid]["audio_pref"] = pref

    _update_config(_mutator)
    _LOGGER.info("[StreamingPref] Saved audio preference: streaming.%s.audio_pref = %s", pid, pref)


def format_surface_choice_prompt(provider_display_name: str, surfaces: List[Surface]) -> str:
    """
    Format a concise, honest spoken prompt describing real options and limits.
    Example:
    'Netflix is available in Chrome and as a desktop app, sir. The desktop app plays
    but I cannot drive it past launch. Chrome gives me full control. Which?'
    """
    if not surfaces:
        return f"I could not detect any installed surfaces for {provider_display_name}, sir."

    names = [s.display_name for s in surfaces]
    if len(names) == 1:
        options_text = names[0]
    elif len(names) == 2:
        options_text = f"{names[0]} and {names[1]}"
    else:
        options_text = f"{', '.join(names[:-1])}, and {names[-1]}"

    # Add honest capability description
    launch_only = [s.display_name for s in surfaces if s.capability == CapabilityClass.LAUNCH_ONLY]
    full_ctrl   = [s.display_name for s in surfaces if s.capability == CapabilityClass.FULL]

    details = []
    if launch_only:
        details.append(f"{launch_only[0]} plays but I cannot drive it past launch")
    if full_ctrl:
        details.append(f"{full_ctrl[0]} gives me full control")

    detail_sentence = ". ".join(details)
    if detail_sentence:
        detail_sentence = f" {detail_sentence}."

    return f"{provider_display_name} is available in {options_text}, sir.{detail_sentence} Which shall I use?"


def resolve_surface(
    provider: StreamingProvider,
    explicit_override: Optional[str] = None,
    prompt_fn: Optional[Callable[[str, List[Surface]], Optional[str]]] = None,
) -> Tuple[Optional[Surface], bool]:
    """
    Resolve the surface to use for a provider request.

    Returns:
        (resolved_surface, should_persist_after_success)
    """
    surfaces = provider.discover_surfaces()
    # Filter out completely unavailable surfaces
    valid_surfaces = [s for s in surfaces if s.capability != CapabilityClass.UNAVAILABLE]
    if not valid_surfaces:
        return None, False

    # 1. Handle explicit user override (e.g. "open Netflix in Edge")
    if explicit_override:
        req = explicit_override.strip().lower()
        for s in valid_surfaces:
            if s.id.lower() == req or req in s.display_name.lower():
                # Explicit override chosen: will persist AFTER successful open/play
                return s, True

    # 2. Check saved preference
    saved_id = get_preferred_surface(provider.id)
    if saved_id:
        for s in valid_surfaces:
            if s.id.lower() == saved_id.lower():
                # Reused silently
                return s, False

    # 3. If only one valid surface exists, use it and remember
    if len(valid_surfaces) == 1:
        chosen = valid_surfaces[0]
        set_preferred_surface(provider.id, chosen.id)
        return chosen, False

    # 4. Ask once
    if prompt_fn:
        prompt_text = format_surface_choice_prompt(provider.display_name, valid_surfaces)
        user_reply = prompt_fn(prompt_text, valid_surfaces)
        if user_reply:
            reply_low = user_reply.strip().lower()
            for s in valid_surfaces:
                if s.id.lower() in reply_low or s.display_name.lower() in reply_low:
                    set_preferred_surface(provider.id, s.id)
                    return s, False
        # Prompt timed out or was cancelled: cancel, do not make a default guess
        return None, False

    # Default fallback: pick first FULL surface, or first valid
    fallback = next((s for s in valid_surfaces if s.capability == CapabilityClass.FULL), valid_surfaces[0])
    set_preferred_surface(provider.id, fallback.id)
    return fallback, False
