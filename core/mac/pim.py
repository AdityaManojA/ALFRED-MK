"""Calendar and Reminders through EventKit (the same store Calendar.app,
Reminders.app, iCloud and the iPhone see). Much faster and more reliable than
scripting the apps, and it works when they are closed.

The first call asks macOS for Calendar / Reminders access on ALFRED's behalf.
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta

from core.mac.osa import OSAError

_store = None
_lock = threading.Lock()
_granted: dict[int, bool] = {}


def _ek():
    import EventKit
    return EventKit


def store():
    global _store
    with _lock:
        if _store is None:
            _store = _ek().EKEventStore.alloc().init()
        return _store


def _ensure_access(entity: int) -> None:
    """entity: 0 = events, 1 = reminders. Blocks for the permission prompt."""
    ek = _ek()
    if _granted.get(entity):
        return
    status = ek.EKEventStore.authorizationStatusForEntityType_(entity)
    # 3 = fullAccess (authorized), 4 = writeOnly
    if status == 3:
        _granted[entity] = True
        return
    if status in (1, 2):
        what = "Calendars" if entity == 0 else "Reminders"
        raise OSAError(f"ALFRED isn't allowed to use {what}. Turn it on in System Settings → "
                       f"Privacy & Security → {what} → ALFRED.")
    done = threading.Event()
    result = {}

    def handler(granted, error):
        result["ok"] = bool(granted)
        done.set()

    s = store()
    if entity == 0:
        s.requestFullAccessToEventsWithCompletion_(handler)
    else:
        s.requestFullAccessToRemindersWithCompletion_(handler)
    done.wait(120)
    if not result.get("ok"):
        what = "Calendars" if entity == 0 else "Reminders"
        raise OSAError(f"Access to {what} was not granted.")
    _granted[entity] = True
    s.reset()


def _nsdate(dt: datetime):
    from Foundation import NSDate
    return NSDate.dateWithTimeIntervalSince1970_(dt.timestamp())


def _pydate(nsd) -> datetime | None:
    return datetime.fromtimestamp(nsd.timeIntervalSince1970()) if nsd is not None else None


def _fmt(dt: datetime | None, all_day: bool = False) -> str:
    if dt is None:
        return ""
    return dt.strftime("%a %d %b") if all_day else dt.strftime("%a %d %b %H:%M")


# ── Calendar ─────────────────────────────────────────────────────────────────

def calendars() -> list[str]:
    _ensure_access(0)
    return sorted({c.title() for c in store().calendarsForEntityType_(0)})


def _calendar_named(name: str | None, entity: int):
    s = store()
    if name:
        for c in s.calendarsForEntityType_(entity):
            if c.title().lower() == name.lower():
                return c
        for c in s.calendarsForEntityType_(entity):
            if name.lower() in c.title().lower():
                return c
    return s.defaultCalendarForNewEvents() if entity == 0 else s.defaultCalendarForNewReminders()


def events(start: datetime, end: datetime, query: str = "", calendar: str | None = None) -> list[dict]:
    _ensure_access(0)
    s = store()
    cals = [_calendar_named(calendar, 0)] if calendar else None
    pred = s.predicateForEventsWithStartDate_endDate_calendars_(_nsdate(start), _nsdate(end), cals)
    out = []
    for e in s.eventsMatchingPredicate_(pred) or []:
        title = e.title() or "(no title)"
        if query and query.lower() not in f"{title} {e.location() or ''} {e.notes() or ''}".lower():
            continue
        st, en, ad = _pydate(e.startDate()), _pydate(e.endDate()), bool(e.isAllDay())
        out.append({"title": title, "start": _fmt(st, ad), "end": _fmt(en, ad), "all_day": ad,
                    "start_iso": st.isoformat(timespec="minutes") if st else None,
                    "location": e.location() or "", "calendar": e.calendar().title() if e.calendar() else "",
                    "id": e.eventIdentifier()})
    out.sort(key=lambda d: d["start_iso"] or "")
    return out


def add_event(title: str, start: datetime, end: datetime | None = None, all_day: bool = False,
              location: str = "", notes: str = "", calendar: str | None = None,
              alert_minutes: int | None = None) -> dict:
    _ensure_access(0)
    ek = _ek()
    s = store()
    e = ek.EKEvent.eventWithEventStore_(s)
    e.setTitle_(title)
    if all_day:
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        end = end or start + timedelta(days=1)
    e.setStartDate_(_nsdate(start))
    e.setEndDate_(_nsdate(end or start + timedelta(hours=1)))
    e.setAllDay_(bool(all_day))
    if location:
        e.setLocation_(location)
    if notes:
        e.setNotes_(notes)
    e.setCalendar_(_calendar_named(calendar, 0))
    if alert_minutes is not None:
        e.addAlarm_(ek.EKAlarm.alarmWithRelativeOffset_(-60 * float(alert_minutes)))
    ok, err = s.saveEvent_span_commit_error_(e, 0, True, None)
    if not ok:
        raise OSAError(f"Calendar refused the event: {err.localizedDescription() if err else 'unknown error'}")
    return {"title": title, "start": _fmt(start, all_day), "end": _fmt(end or start + timedelta(hours=1), all_day),
            "calendar": e.calendar().title(), "id": e.eventIdentifier()}


def delete_event(event_id: str) -> str:
    _ensure_access(0)
    s = store()
    e = s.eventWithIdentifier_(event_id)
    if e is None:
        raise OSAError("That event no longer exists.")
    title = e.title()
    ok, err = s.removeEvent_span_commit_error_(e, 0, True, None)
    if not ok:
        raise OSAError(f"Could not delete it: {err.localizedDescription() if err else 'unknown error'}")
    return f"Deleted “{title}”."


# ── Reminders ────────────────────────────────────────────────────────────────

def reminder_lists() -> list[str]:
    _ensure_access(1)
    return sorted({c.title() for c in store().calendarsForEntityType_(1)})


def _fetch(pred) -> list:
    done = threading.Event()
    box = {}

    def handler(items):
        box["items"] = list(items or [])
        done.set()

    store().fetchRemindersMatchingPredicate_completion_(pred, handler)
    done.wait(30)
    return box.get("items", [])


def reminders(list_name: str | None = None, include_completed: bool = False, query: str = "") -> list[dict]:
    _ensure_access(1)
    s = store()
    cals = [_calendar_named(list_name, 1)] if list_name else None
    if include_completed:
        pred = s.predicateForRemindersInCalendars_(cals)
    else:
        pred = s.predicateForIncompleteRemindersWithDueDateStarting_ending_calendars_(None, None, cals)
    out = []
    for r in _fetch(pred):
        title = r.title() or ""
        if query and query.lower() not in f"{title} {r.notes() or ''}".lower():
            continue
        due = None
        comps = r.dueDateComponents()
        if comps is not None:
            from Foundation import NSCalendar
            d = NSCalendar.currentCalendar().dateFromComponents_(comps)
            due = _pydate(d)
        out.append({"title": title, "due": _fmt(due) if due else "", "due_iso": due.isoformat(timespec="minutes") if due else None,
                    "list": r.calendar().title() if r.calendar() else "", "completed": bool(r.isCompleted()),
                    "priority": int(r.priority()), "id": r.calendarItemIdentifier()})
    out.sort(key=lambda d: (d["due_iso"] is None, d["due_iso"] or "", d["title"].lower()))
    return out


def add_reminder(title: str, due: datetime | None = None, list_name: str | None = None,
                 notes: str = "", priority: int = 0) -> dict:
    _ensure_access(1)
    ek = _ek()
    from Foundation import NSCalendar
    s = store()
    r = ek.EKReminder.reminderWithEventStore_(s)
    r.setTitle_(title)
    r.setCalendar_(_calendar_named(list_name, 1))
    if notes:
        r.setNotes_(notes)
    if priority:
        r.setPriority_(int(priority))
    if due is not None:
        units = (1 << 2) | (1 << 3) | (1 << 4) | (1 << 5) | (1 << 6)   # year month day hour minute
        r.setDueDateComponents_(NSCalendar.currentCalendar().components_fromDate_(units, _nsdate(due)))
        r.addAlarm_(ek.EKAlarm.alarmWithAbsoluteDate_(_nsdate(due)))
    ok, err = s.saveReminder_commit_error_(r, True, None)
    if not ok:
        raise OSAError(f"Reminders refused it: {err.localizedDescription() if err else 'unknown error'}")
    return {"title": title, "due": _fmt(due) if due else "", "list": r.calendar().title()}


def _reminder_by_id(rid: str):
    return store().calendarItemWithIdentifier_(rid)


def complete_reminder(rid: str) -> str:
    _ensure_access(1)
    r = _reminder_by_id(rid)
    if r is None:
        raise OSAError("That reminder no longer exists.")
    r.setCompleted_(True)
    ok, err = store().saveReminder_commit_error_(r, True, None)
    if not ok:
        raise OSAError(f"Could not update it: {err.localizedDescription() if err else 'unknown error'}")
    return f"Marked “{r.title()}” as done."


def delete_reminder(rid: str) -> str:
    _ensure_access(1)
    r = _reminder_by_id(rid)
    if r is None:
        raise OSAError("That reminder no longer exists.")
    title = r.title()
    ok, err = store().removeReminder_commit_error_(r, True, None)
    if not ok:
        raise OSAError(f"Could not delete it: {err.localizedDescription() if err else 'unknown error'}")
    return f"Deleted “{title}”."
