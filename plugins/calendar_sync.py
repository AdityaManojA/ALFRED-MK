"""
Calendar Sync Plugin for ALFRED Mark-LIV.
Tracks agenda, meetings, appointments, and daily schedules.
Stores events in ~/.alfred/calendar.json (or ~/.jarvis/calendar.json fallback).
Auto-discovered by core/plugin_loader.py.
"""
from __future__ import annotations

import json
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

_LEGACY_STORE = Path.home() / ".jarvis" / "calendar.json"
_STORE = Path.home() / ".alfred" / "calendar.json"
if not _STORE.exists() and _LEGACY_STORE.exists():
    _STORE = _LEGACY_STORE


def _load_events() -> list[dict]:
    if not _STORE.exists():
        return []
    try:
        return json.loads(_STORE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_events(events: list[dict]) -> None:
    _STORE.parent.mkdir(parents=True, exist_ok=True)
    _STORE.write_text(json.dumps(events, indent=2), encoding="utf-8")


PLUGIN = {
    "name": "calendar_sync",
    "description": (
        "Manages calendar events, meetings, and daily agenda. "
        "Allows creating meetings, checking today's schedule, or viewing upcoming appointments. "
        "Trigger when user says 'what's on my calendar', 'schedule a meeting', 'add to my calendar', "
        "or 'when is my next appointment'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Operation: 'list' (view agenda), 'add' (schedule event), or 'next' (next meeting)."
            },
            "title": {
                "type": "STRING",
                "description": "Title or summary of the meeting/event (e.g. 'Sync with Design Team')."
            },
            "date": {
                "type": "STRING",
                "description": "Date in YYYY-MM-DD format (defaults to today)."
            },
            "time": {
                "type": "STRING",
                "description": "Time in HH:MM (24-hour) format (e.g. '14:30' or '09:00')."
            },
            "duration_minutes": {
                "type": "INTEGER",
                "description": "Duration in minutes (default: 30)."
            }
        },
        "required": ["action"]
    },
    "behavior": "BLOCKING",
    "scheduling": "WHEN_IDLE"
}

PLUGIN_SETTINGS = {
    "settings": [
        {
            "id": "work_start_hour",
            "type": "INT",
            "label": "Workday Start Hour (0-23)",
            "default": 9,
            "min": 0,
            "max": 23,
        },
        {
            "id": "work_end_hour",
            "type": "INT",
            "label": "Workday End Hour (0-23)",
            "default": 18,
            "min": 0,
            "max": 23,
        }
    ]
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Execute calendar action."""
    action = str(parameters.get("action", "list")).strip().lower()
    title = parameters.get("title", "").strip()
    date_str = parameters.get("date") or datetime.now().strftime("%Y-%m-%d")
    time_str = parameters.get("time", "").strip()
    duration = int(parameters.get("duration_minutes", 30))

    events = _load_events()

    # 1. ADD EVENT
    if action == "add":
        if not title:
            return "Sir, I require an event title to add it to your calendar."
        if not time_str:
            time_str = "10:00"

        new_event = {
            "id": f"evt_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "title": title,
            "date": date_str,
            "time": time_str,
            "duration": duration,
            "created_at": datetime.now().isoformat()
        }
        events.append(new_event)
        # Sort chronologically
        events.sort(key=lambda x: (x.get("date", ""), x.get("time", "")))
        _save_events(events)

        msg = f"Scheduled '{title}' for {date_str} at {time_str} ({duration} mins)."
        if player:
            try:
                player.write_log(f"ALFRED: [Calendar] {msg}")
            except Exception:
                pass
        return f"Sir, I have scheduled '{title}' for {date_str} at {time_str}."

    # 2. NEXT EVENT
    if action == "next":
        now_dt = datetime.now()
        upcoming = []
        for ev in events:
            try:
                ev_dt = datetime.strptime(f"{ev['date']} {ev['time']}", "%Y-%m-%d %H:%M")
                if ev_dt >= now_dt:
                    upcoming.append((ev_dt, ev))
            except Exception:
                pass

        if not upcoming:
            return "Sir, you have no upcoming meetings scheduled on your calendar."

        upcoming.sort(key=lambda x: x[0])
        next_dt, next_ev = upcoming[0]
        friendly_time = next_dt.strftime("%A, %B %d at %I:%M %p")
        return f"Your next appointment is '{next_ev['title']}' on {friendly_time}."

    # 3. LIST TODAY'S AGENDA
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_events = [ev for ev in events if ev.get("date") == date_str]

    if not today_events:
        target_day = "today" if date_str == today_str else f"for {date_str}"
        return f"Sir, your calendar is completely open {target_day}. No meetings scheduled."

    brief = [f"Sir, you have {len(today_events)} event{'s' if len(today_events) != 1 else ''} scheduled:"]
    for ev in today_events:
        brief.append(f"• At {ev.get('time')}: {ev.get('title')} ({ev.get('duration', 30)} mins)")

    res = " ".join(brief)
    if player:
        try:
            player.write_log(f"ALFRED: [Calendar] Agenda for {date_str}:")
            for ev in today_events:
                player.write_log(f"   • {ev.get('time')} — {ev.get('title')}")
        except Exception:
            pass
    return res
