"""
Update Daily Briefing Preferences Action for ALFRED Mark-LIV.
Permanently updates and saves briefing preferences to long-term memory.
"""
from __future__ import annotations

from typing import Optional

from memory.memory_manager import update_memory, load_memory
from core.cache import get_cache


def update_daily_briefing(
    parameters: dict,
    player=None,
    speak=None,
    session_memory=None,
) -> str:
    """Permanently saves daily briefing preferences into long-term memory."""
    preferences = str(parameters.get("preferences", "")).strip()
    city = str(parameters.get("city", "")).strip()
    topics = parameters.get("topics", [])
    if isinstance(topics, list) and topics:
        topics_str = ", ".join(str(t).strip() for t in topics if str(t).strip())
        if topics_str and topics_str not in preferences:
            preferences = f"{preferences} (Topics: {topics_str})" if preferences else topics_str

    if not preferences and not city:
        return "No specific briefing preferences or city provided to update."

    memory_update: dict[str, dict] = {}
    if preferences:
        memory_update.setdefault("preferences", {})["briefing_preference"] = {"value": preferences}
    if city:
        memory_update.setdefault("identity", {})["city"] = {"value": city}

    update_memory(memory_update)

    # ── Cache Invalidation Hook ────────────────────────────────────────────────
    # Immediately purge stale cached weather forecasts and briefing news
    cache = get_cache()
    if city:
        cache.invalidate_prefix("weather:")
    if preferences:
        cache.invalidate_prefix("daily_brief:")
        cache.invalidate_prefix("web_news:")

    msg = "Daily briefing preferences successfully and permanently saved to memory."
    if preferences:
        msg += f" Briefing focus: {preferences}."
    if city:
        msg += f" Weather location: {city}."

    if player:
        try:
            player.write_log(f"🧠 [Memory] Updated Daily Briefing (Cache Invalidated): {preferences or city}")
        except Exception:
            pass

    return msg


TOOL = {
    "name": "update_daily_briefing",
    "description": (
        "Permanently records and updates the user's daily briefing preferences, topics, or location in long-term memory. "
        "DO NOT call this tool when the user only says 'update my daily briefing' without providing the details — first ask them what changes they would like to make. "
        "Call this tool once the user specifies what changes, topics, news categories, or location they want in their daily briefing."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "preferences": {
                "type": "STRING",
                "description": "The user's requested briefing preferences, topics, or focus areas in English (e.g. 'tech news, AI advancements, and cricket updates')."
            },
            "city": {
                "type": "STRING",
                "description": "Optional city or location specified for the briefing weather (e.g. 'Thrissur', 'New York')."
            },
            "topics": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "Optional list of specific topics or categories."
            }
        },
        "required": ["preferences"]
    },
    "handler": update_daily_briefing,
    "behavior": "BLOCKING",
    "scheduling": "WHEN_IDLE"
}
