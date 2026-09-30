"""Calendar events (iCloud / Google / Exchange — whatever Calendar.app syncs) via EventKit."""
from core.mac import require_mac

require_mac()

from datetime import datetime, timedelta               # noqa: E402

from core.mac import pim                               # noqa: E402
from core.mac.timeparse import parse_datetime, parse_duration, speak_time   # noqa: E402
from core.mac.tooling import B, N, S, needs_confirm, tool                   # noqa: E402


def _range(p) -> tuple[datetime, datetime]:
    now = datetime.now()
    day0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    when = str(p.get("range") or "").lower().strip()
    start = parse_datetime(p.get("start"), prefer_future=False) if p.get("start") else None
    end = parse_datetime(p.get("end"), prefer_future=False) if p.get("end") else None
    if start and not end:
        s0 = start.replace(hour=0, minute=0) if start.hour == 0 and start.minute == 0 else start
        return s0, s0.replace(hour=0, minute=0) + timedelta(days=1)
    if start and end:
        return start, end
    if when in ("", "today"):
        return now if when == "" else day0, day0 + timedelta(days=1)
    if when == "tomorrow":
        return day0 + timedelta(days=1), day0 + timedelta(days=2)
    if when in ("week", "this week", "next 7 days"):
        return now, day0 + timedelta(days=7)
    if when in ("next week",):
        return day0 + timedelta(days=7 - now.weekday()), day0 + timedelta(days=14 - now.weekday())
    if when in ("month", "this month", "next 30 days"):
        return now, day0 + timedelta(days=30)
    d = parse_datetime(when, prefer_future=True)
    if d:
        d0 = d.replace(hour=0, minute=0, second=0, microsecond=0)
        return d0, d0 + timedelta(days=1)
    return now, day0 + timedelta(days=1)


@tool
def mac_calendar(p, **_):
    a = str(p.get("action", "list")).lower().strip()
    if a == "calendars":
        return {"calendars": pim.calendars()}
    if a in ("list", "search"):
        start, end = _range(p)
        if a == "search" and not p.get("range") and not p.get("start"):
            start, end = datetime.now() - timedelta(days=30), datetime.now() + timedelta(days=90)
        evs = pim.events(start, end, query=str(p.get("query") or ""), calendar=p.get("calendar"))
        return {"from": start.strftime("%a %d %b %H:%M"), "to": end.strftime("%a %d %b %H:%M"),
                "count": len(evs), "events": [{k: v for k, v in e.items() if k != "start_iso"} for e in evs[:40]]}
    if a == "create":
        title = str(p.get("title") or "").strip()
        start = parse_datetime(p.get("start"))
        if not title or not start:
            return "I need a title and a start time for the event."
        end = parse_datetime(p.get("end"), now=start) if p.get("end") else None
        if end is None and p.get("duration"):
            secs = parse_duration(str(p.get("duration")))
            end = start + timedelta(seconds=secs) if secs else None
        ev = pim.add_event(title, start, end, all_day=bool(p.get("all_day")),
                           location=str(p.get("location") or ""), notes=str(p.get("notes") or ""),
                           calendar=p.get("calendar"),
                           alert_minutes=int(p["alert_minutes"]) if p.get("alert_minutes") not in (None, "") else None)
        ev["when"] = speak_time(start)
        return {"created": ev}
    if a == "delete":
        if p.get("event_id"):
            if not p.get("confirm"):
                return needs_confirm("Delete that event?")
            return pim.delete_event(str(p["event_id"]))
        start, end = _range(p)
        if not p.get("range") and not p.get("start"):
            start, end = datetime.now() - timedelta(days=1), datetime.now() + timedelta(days=60)
        evs = pim.events(start, end, query=str(p.get("query") or ""))
        if not evs:
            return "No matching event found."
        if len(evs) > 1:
            return {"ambiguous": True, "matches": evs[:10],
                    "note": "Ask which one, then call delete with its event_id."}
        ev = evs[0]
        if not p.get("confirm"):
            return needs_confirm(f"Delete “{ev['title']}” on {ev['start']}?")
        return pim.delete_event(ev["id"])
    return "Unknown action. Use list, search, create, delete or calendars."


TOOL = {
    "name": "mac_calendar",
    "description": ("The user's calendar (everything synced to Calendar.app): what's on today/tomorrow/this week or a date, "
                    "search events, create events with location/alert, delete events (confirm first)."),
    "parameters": {"type": "OBJECT", "properties": {
        "action": S("What to do.", ["list", "search", "create", "delete", "calendars"]),
        "range": S("list/search: today, tomorrow, week, next week, month, or a date like 'friday' / '2026-10-03'."),
        "start": S("Event start (create) or range start: ISO local time like 2026-10-01T15:00, or 'tomorrow 3pm'."),
        "end": S("Event end or range end (same formats)."),
        "duration": S("create: length if no end, e.g. '30 minutes', '2 hours'. Default 1 hour."),
        "title": S("create: event title."),
        "location": S("create: where."),
        "notes": S("create: notes."),
        "calendar": S("Calendar name (default calendar if omitted)."),
        "all_day": B("create: all-day event."),
        "alert_minutes": N("create: alert this many minutes before."),
        "query": S("search/delete: words in the title, location or notes."),
        "event_id": S("delete: exact id from a previous list."),
        "confirm": B("delete: only true after the user agreed."),
    }, "required": ["action"]},
    "handler": mac_calendar,
}
