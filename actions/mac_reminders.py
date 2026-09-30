"""Apple Reminders (syncs to iPhone/Watch) via EventKit."""
from core.mac import require_mac

require_mac()

from core.mac import pim                                        # noqa: E402
from core.mac.timeparse import parse_datetime, speak_time       # noqa: E402
from core.mac.tooling import B, N, S, needs_confirm, tool       # noqa: E402


def _one(p) -> dict | str:
    if p.get("reminder_id"):
        return {"id": p["reminder_id"], "title": "that reminder"}
    q = str(p.get("query") or p.get("title") or "").strip()
    if not q:
        return "Which reminder?"
    hits = pim.reminders(p.get("list_name"), query=q)
    if not hits:
        return f"No open reminder matches “{q}”."
    exact = [h for h in hits if h["title"].lower() == q.lower()]
    if len(exact) == 1:
        return exact[0]
    if len(hits) > 1:
        return {"ambiguous": True, "matches": hits[:10], "note": "Ask which one, then pass its reminder_id."}
    return hits[0]


@tool
def mac_reminders(p, **_):
    a = str(p.get("action", "list")).lower().strip()
    if a == "lists":
        return {"lists": pim.reminder_lists()}
    if a == "list":
        items = pim.reminders(p.get("list_name"), include_completed=bool(p.get("include_completed")),
                              query=str(p.get("query") or ""))
        return {"count": len(items), "reminders": [{k: v for k, v in r.items() if k != "due_iso"} for r in items[:50]]}
    if a == "add":
        title = str(p.get("title") or "").strip()
        if not title:
            return "What should the reminder say?"
        due = parse_datetime(p.get("due")) if p.get("due") else None
        if p.get("due") and due is None:
            return f"I couldn't understand the time “{p.get('due')}”."
        r = pim.add_reminder(title, due, p.get("list_name"), str(p.get("notes") or ""),
                             int(p.get("priority") or 0))
        if due:
            r["when"] = speak_time(due)
        return {"added": r}
    if a in ("complete", "delete"):
        target = _one(p)
        if isinstance(target, str) or target.get("ambiguous"):
            return target
        if a == "complete":
            return pim.complete_reminder(target["id"])
        if not p.get("confirm"):
            return needs_confirm(f"Delete the reminder “{target['title']}”?")
        return pim.delete_reminder(target["id"])
    return "Unknown action. Use list, add, complete, delete or lists."


TOOL = {
    "name": "mac_reminders",
    "description": ("Apple Reminders (syncs to iPhone): list open reminders, add one with an optional due time "
                    "(it alerts on all devices), mark done, delete (confirm first), list reminder lists."),
    "parameters": {"type": "OBJECT", "properties": {
        "action": S("What to do.", ["list", "add", "complete", "delete", "lists"]),
        "title": S("add: the reminder text."),
        "due": S("add: when — ISO local time (2026-10-01T18:00) or 'tomorrow 6pm', 'in 2 hours'."),
        "list_name": S("Reminders list (default list if omitted)."),
        "notes": S("add: extra notes."),
        "priority": N("add: 1 high, 5 medium, 9 low."),
        "query": S("list/complete/delete: words in the reminder."),
        "reminder_id": S("complete/delete: exact id from a previous list."),
        "include_completed": B("list: include finished ones."),
        "confirm": B("delete: only true after the user agreed."),
    }, "required": ["action"]},
    "handler": mac_reminders,
}
