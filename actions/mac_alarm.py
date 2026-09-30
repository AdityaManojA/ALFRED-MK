"""Alarms and timers.

Alarms go into the Clock app when the user has the "ALFRED Set Alarm" shortcut
(Clock's alarm store only accepts Apple-entitled processes, and Shortcuts is
one). Otherwise — and for timers, repeating alarms and alarms more than a day
out — alfredd keeps them, so they ring even while the agent sleeps or is closed.
"""
from core.mac import require_mac

require_mac()

import time                                                     # noqa: E402
from datetime import datetime, timedelta                        # noqa: E402

import subprocess                                               # noqa: E402

from core.mac import apps                                       # noqa: E402
from core.mac.daemon_client import get_client                   # noqa: E402
from core.mac.osa import OSAError                               # noqa: E402
from core.mac.timeparse import parse_datetime, parse_days, parse_duration, speak_time   # noqa: E402
from core.mac.tooling import B, N, S, needs_confirm, tool       # noqa: E402

_DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
CLOCK_SET = "ALFRED Set Alarm"      # Shortcut: Clock ▸ Create Alarm, time = Shortcut Input
CLOCK_LIST = "ALFRED List Alarms"   # Shortcut: Clock ▸ Get All Alarms (optional)
_CLOCK_HOWTO = ("To have alarms appear in the Clock app, create a shortcut named “ALFRED Set Alarm” in "
                "Shortcuts with one action — Clock ▸ Create Alarm, its time set to Shortcut Input.")


def _shortcuts() -> set[str]:
    try:
        return set(apps.shortcuts_list())
    except Exception:
        return set()


def _ask(msg: dict) -> dict:
    c = get_client()
    r = c.request(msg, timeout=5) if c else None
    if r is None:
        raise RuntimeError("ALFRED's background listener isn't running, so alarms can't be kept. "
                           "Reopen ALFRED.app (or run mac/build.sh) and try again.")
    if not r.get("ok", True):
        raise RuntimeError(r.get("error", "the listener refused"))
    return r


def _describe(a: dict) -> dict:
    when = datetime.fromtimestamp(a["fire_at"])
    d = {"id": a["id"], "kind": a["kind"], "label": a.get("label", ""), "rings": speak_time(when)}
    if a.get("days"):
        days = a["days"]
        d["repeats"] = ("every day" if len(days) == 7 else "weekdays" if days == [1, 2, 3, 4, 5]
                        else "weekends" if days == [6, 7] else ", ".join(_DAY_NAMES[i - 1] for i in days))
    if a["kind"] == "timer":
        left = int(a["fire_at"] - time.time())
        d["remaining"] = f"{left // 60} min {left % 60} s" if left > 0 else "now"
    return d


def _match(alarms: list, q: str) -> list:
    ql = q.lower().strip()
    return [a for a in alarms if ql in a.get("label", "").lower() or ql == a["id"]
            or ql in _describe(a)["rings"].lower()]


@tool
def mac_alarm(p, **_):
    a = str(p.get("action", "")).lower().strip()
    if a == "set_alarm":
        days = parse_days(p.get("repeat") or "")
        when = parse_datetime(p.get("time"))
        if when is None:
            return f"I couldn't understand the time “{p.get('time')}”."
        if days:
            # Next matching weekday at that time.
            probe = when if when > datetime.now() else when + timedelta(days=1)
            for _ in range(8):
                if probe.isoweekday() in days and probe > datetime.now():
                    break
                probe += timedelta(days=1)
            when = probe
        where = str(p.get("where") or "").lower()
        have = _shortcuts()
        in_a_day = not days and timedelta(0) < when - datetime.now() <= timedelta(hours=24)
        if where != "alfred" and CLOCK_SET in have and in_a_day:
            # Clock alarms have no date: "6:00 AM" means the next 6:00 AM.
            apps.shortcut_run(CLOCK_SET, when.strftime("%-I:%M %p"))
            return {"set_in": "Clock app", "time": when.strftime("%-I:%M %p"), "rings": speak_time(when)}
        note = None
        if CLOCK_SET not in have:
            note = "Saved as an ALFRED alarm (it rings from ALFRED, not the Clock app). " + _CLOCK_HOWTO
        elif not in_a_day and where != "alfred":
            note = ("The Clock app only takes one-off alarms within the next 24 hours from me, "
                    "so this one is an ALFRED alarm.")
        # Asking twice ("set an alarm for 6" … "set an alarm for 6am") must not ring twice.
        for existing in _ask({"type": "alarm_list"}).get("alarms", []):
            if (existing["kind"] == "alarm" and abs(existing["fire_at"] - when.timestamp()) < 60
                    and sorted(existing.get("days", [])) == days):
                out = {"already_set": _describe(existing), "set_in": "ALFRED"}
                if note:
                    out["note"] = note
                return out
        r = _ask({"type": "alarm_add", "kind": "alarm", "label": str(p.get("label") or ""),
                  "fire_at": when.timestamp(), "hour": when.hour, "minute": when.minute, "days": days})
        out = {"set": _describe(r["alarm"]), "set_in": "ALFRED"}
        if note:
            out["note"] = note
        return out
    if a == "set_timer":
        secs = parse_duration(str(p.get("duration") or ""))
        if not secs or secs <= 0:
            return f"I couldn't understand the duration “{p.get('duration')}”."
        r = _ask({"type": "alarm_add", "kind": "timer", "label": str(p.get("label") or ""),
                  "fire_at": time.time() + secs, "days": []})
        return {"set": _describe(r["alarm"])}
    if a == "list":
        r = _ask({"type": "alarm_list"})
        out = {"alfred_alarms": [_describe(x) for x in r.get("alarms", [])]}
        if r.get("ringing"):
            out["ringing_now"] = r["ringing"].get("label") or r["ringing"].get("kind")
        if CLOCK_LIST in _shortcuts():
            try:
                out["clock_app_alarms"] = apps.shortcut_run(CLOCK_LIST)
            except OSAError as e:
                out["clock_app_alarms"] = f"couldn't read: {e}"
        else:
            out["clock_app_alarms"] = "not readable (no “ALFRED List Alarms” shortcut)"
        return out
    if a == "cancel":
        r = _ask({"type": "alarm_list"})
        items = r.get("alarms", [])
        q = str(p.get("query") or p.get("id") or "").strip()
        if q.lower() == "all":
            if not p.get("confirm"):
                return needs_confirm(f"Cancel all {len(items)} alarms and timers?")
            _ask({"type": "alarm_cancel", "id": "all"})
            return "All alarms and timers cancelled."
        if not q and len(items) == 1:
            hits = items
        else:
            kind = str(p.get("kind") or "").lower()
            hits = _match(items, q) if q else [x for x in items if not kind or x["kind"] == kind]
        if not hits:
            if CLOCK_SET in _shortcuts():
                subprocess.run(["open", "-a", "Clock"])
                return ("No ALFRED alarm matches. Alarms in the Clock app can't be deleted from here, "
                        "so I've opened Clock for you.")
            return "No matching alarm or timer."
        if len(hits) > 1:
            return {"ambiguous": True, "matches": [_describe(x) for x in hits],
                    "note": "Ask which one, then cancel with its id as query."}
        _ask({"type": "alarm_cancel", "id": hits[0]["id"]})
        return f"Cancelled the {hits[0]['kind']} for {_describe(hits[0])['rings']}."
    if a == "stop":
        r = _ask({"type": "alarm_stop"})
        return "Stopped." if r.get("was_ringing") else "Nothing is ringing."
    if a == "snooze":
        r = _ask({"type": "alarm_snooze", "minutes": float(p.get("minutes") or 9)})
        return f"Snoozed for {int(float(p.get('minutes') or 9))} minutes." if r.get("was_ringing") else "Nothing is ringing."
    return "Unknown action. Use set_alarm, set_timer, list, cancel, stop or snooze."


TOOL = {
    "name": "mac_alarm",
    "description": ("Alarms and timers on this Mac: set an alarm (goes into the Clock app when possible, otherwise "
                    "ALFRED rings it), repeating alarms, timers, list, cancel, stop or snooze the one ringing. "
                    "Tell the user where the alarm was set (Clock app or ALFRED) and relay any note."),
    "parameters": {"type": "OBJECT", "properties": {
        "action": S("What to do.", ["set_alarm", "set_timer", "list", "cancel", "stop", "snooze"]),
        "time": S("set_alarm: ISO local time (2026-10-01T07:00) or '7am', 'tomorrow 6:30'."),
        "repeat": S("set_alarm: once (default), daily, weekdays, weekends, or days like 'mon wed fri'."),
        "duration": S("set_timer: e.g. '10 minutes', '1h30m', '90 seconds'."),
        "label": S("Optional name, e.g. 'pasta' or 'gym'."),
        "where": S("set_alarm: 'clock' or 'alfred' only if the user asked for one explicitly."),
        "query": S("cancel: label, id or time of the alarm, or 'all'."),
        "kind": S("cancel: alarm or timer, when the user just says 'cancel the timer'."),
        "minutes": N("snooze: minutes (default 9)."),
        "confirm": B("cancel all: only true after the user agreed."),
    }, "required": ["action"]},
    "handler": mac_alarm,
}
