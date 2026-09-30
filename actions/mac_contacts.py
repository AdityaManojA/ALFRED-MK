"""Look people up in Contacts."""
from core.mac import require_mac

require_mac()

from core.mac import apps                   # noqa: E402
from core.mac.tooling import S, tool        # noqa: E402


@tool
def mac_contacts(p, **_):
    name = str(p.get("name") or "").strip()
    if not name:
        return "Who should I look up?"
    hits = apps.find_contacts(name)
    return {"matches": hits} if hits else f"No contact matches “{name}”."


TOOL = {
    "name": "mac_contacts",
    "description": "Find a person in the user's Contacts and return their phone numbers and email addresses.",
    "parameters": {"type": "OBJECT", "properties": {
        "name": S("Name (or part of it) to look up."),
    }, "required": ["name"]},
    "handler": mac_contacts,
}
