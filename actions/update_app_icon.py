"""
Update App Icon Action for ALFRED Mark-LIV.
Switches the application window, taskbar, and chassis insignia in realtime on voice/chat command.
"""
from __future__ import annotations

from pathlib import Path


def update_app_icon(
    parameters: dict,
    player=None,
    speak=None,
    session_memory=None,
) -> str:
    """Updates the main application icon and taskbar badge in realtime."""
    icon_name = str(parameters.get("icon_name", "")).strip()
    if not icon_name:
        return "Please specify which icon to switch to (e.g. 'Batman Beyond', 'Arkham Asylum', 'White Bat', 'Classic Bat', or 'Stealth')."

    # Delegate to player / UI
    ok = False
    if player and hasattr(player, "set_app_icon"):
        ok = player.set_app_icon(icon_name)
    elif player and hasattr(player, "_win") and hasattr(player._win, "set_app_icon"):
        ok = player._win.set_app_icon(icon_name)
    else:
        from memory.config_manager import save_app_icon
        save_app_icon(icon_name)
        ok = True

    if ok:
        return f"Application icon and chassis insignia successfully updated in realtime to '{icon_name}'."
    else:
        return (
            f"Could not find an icon matching '{icon_name}'. "
            "Available insignias: Arkham Asylum, Batman Beyond, Classic Bat, White Knight Bat, Stealth."
        )


TOOL = {
    "name": "update_app_icon",
    "description": (
        "Updates and switches the main application's window, taskbar, and chassis icon in realtime. "
        "Trigger when user says 'change app icon', 'switch icon to Batman Beyond', 'update icon to Arkham Asylum', "
        "'change chassis badge to white bat', or asks to update the application insignia."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "icon_name": {
                "type": "STRING",
                "description": "Name or keyword of the icon to apply: 'Arkham Asylum', 'Batman Beyond', 'Classic Bat', 'White Bat', 'Stealth / Transparent', or 'Wayne Crest'."
            }
        },
        "required": ["icon_name"]
    },
    "handler": update_app_icon,
    "behavior": "BLOCKING",
    "scheduling": "WHEN_IDLE"
}
