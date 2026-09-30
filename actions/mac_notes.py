"""Apple Notes: create, search, read, append."""
from core.mac import require_mac

require_mac()

from core.mac import apps                   # noqa: E402
from core.mac.tooling import S, tool        # noqa: E402


def _find(p) -> dict | str:
    if p.get("note_id"):
        return {"id": p["note_id"], "title": ""}
    q = str(p.get("query") or p.get("title") or "").strip()
    if not q:
        return "Which note?"
    hits = apps.note_search(q, limit=5)
    if not hits:
        return f"No note titled like “{q}”."
    return hits[0]


@tool
def mac_notes(p, **_):
    a = str(p.get("action", "")).lower().strip()
    if a == "create":
        title = str(p.get("title") or "").strip() or "Note"
        return apps.note_create(title, str(p.get("text") or ""), p.get("folder"))
    if a == "search":
        return {"notes": apps.note_search(str(p.get("query") or ""), limit=15)}
    if a == "read":
        n = _find(p)
        if isinstance(n, str):
            return n
        return {"title": n["title"], "text": apps.note_read(n["id"])}
    if a == "append":
        n = _find(p)
        if isinstance(n, str):
            return n
        return apps.note_append(n["id"], str(p.get("text") or ""))
    return "Unknown action. Use create, search, read or append."


TOOL = {
    "name": "mac_notes",
    "description": "Apple Notes: create a note, search notes by title, read one aloud, or append text to one.",
    "parameters": {"type": "OBJECT", "properties": {
        "action": S("What to do.", ["create", "search", "read", "append"]),
        "title": S("create: note title; read/append: title to look for."),
        "text": S("create: body; append: text to add."),
        "query": S("search/read/append: words in the note title."),
        "folder": S("create: Notes folder name (optional)."),
        "note_id": S("read/append: exact id from search."),
    }, "required": ["action"]},
    "handler": mac_notes,
}
