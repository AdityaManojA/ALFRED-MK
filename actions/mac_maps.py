"""Apple Maps: directions and place search."""
from core.mac import require_mac

require_mac()

from core.mac import apps                   # noqa: E402
from core.mac.tooling import S, tool        # noqa: E402


@tool
def mac_maps(p, **_):
    a = str(p.get("action", "directions")).lower().strip()
    if a == "directions":
        dest = str(p.get("place") or "").strip()
        if not dest:
            return "Where to?"
        return apps.maps(dest, str(p.get("origin") or ""), str(p.get("mode") or "driving"))
    if a == "search":
        return apps.maps_search(str(p.get("place") or ""))
    return "Unknown action. Use directions or search."


TOOL = {
    "name": "mac_maps",
    "description": "Open Apple Maps with directions to a place (driving, walking, transit, cycling) or search for places nearby.",
    "parameters": {"type": "OBJECT", "properties": {
        "action": S("What to do.", ["directions", "search"]),
        "place": S("Destination or what to search for, e.g. 'nearest pharmacy'."),
        "origin": S("directions: start point (default: current location)."),
        "mode": S("directions: driving, walking, transit or cycling."),
    }, "required": ["action", "place"]},
    "handler": mac_maps,
}
