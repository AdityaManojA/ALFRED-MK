"""Run the user's Shortcuts — the bridge to Focus modes, HomeKit, Clock and anything Siri can do."""
from core.mac import require_mac

require_mac()

from core.mac import apps                   # noqa: E402
from core.mac.tooling import S, tool        # noqa: E402


@tool
def mac_shortcuts(p, **_):
    a = str(p.get("action", "list")).lower().strip()
    if a == "list":
        names = apps.shortcuts_list()
        return {"shortcuts": names} if names else "The user has no shortcuts yet."
    if a == "run":
        name = str(p.get("name") or "").strip()
        if not name:
            return "Which shortcut?"
        return apps.shortcut_run(name, str(p.get("input") or ""))
    return "Unknown action. Use list or run."


TOOL = {
    "name": "mac_shortcuts",
    "description": ("List or run the user's Shortcuts (Shortcuts.app) — use for Focus / Do Not Disturb, HomeKit scenes, "
                    "Clock app alarms, and any automation the user built."),
    "parameters": {"type": "OBJECT", "properties": {
        "action": S("What to do.", ["list", "run"]),
        "name": S("run: shortcut name (partial match is fine)."),
        "input": S("run: optional text passed to the shortcut."),
    }, "required": ["action"]},
    "handler": mac_shortcuts,
}
