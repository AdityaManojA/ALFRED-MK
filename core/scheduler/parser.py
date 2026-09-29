"""Deterministic scheduling phrases accepted by the local task engine."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

_RELATIVE = re.compile(r"\bin\s+(\d+)\s+(minutes?|hours?)\b", re.IGNORECASE)
_AT_TIME = re.compile(r"\b(?:every\s+day\s+)?at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", re.IGNORECASE)
_REMINDER_PREFIX = re.compile(r"^.*?\b(?:remind|tell)\s+me\s+(?:to\s+)?", re.IGNORECASE)


def _message(text: str) -> str:
    value = _REMINDER_PREFIX.sub("", text).strip(" .")
    value = re.sub(
        r"^(?:every\s+day\s+)?at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s+(?:to\s+)?",
        "",
        value,
        flags=re.IGNORECASE,
    ).strip(" .")
    return value or text.strip()


def parse_schedule(text: str, now: datetime | None = None) -> dict[str, Any] | None:
    now = now or datetime.now()
    source = str(text or "").strip()
    if not source:
        return None
    relative = _RELATIVE.search(source)
    if relative:
        amount, unit = int(relative.group(1)), relative.group(2).lower()
        trigger = now + timedelta(minutes=amount if unit.startswith("minute") else amount * 60)
        return {"trigger_time": trigger.isoformat(), "recurrence": "once", "payload": {"message": _message(source)}}
    match = _AT_TIME.search(source)
    if not match:
        return None
    hour, minute, meridiem = int(match.group(1)), int(match.group(2) or 0), (match.group(3) or "").lower()
    if not 0 <= minute <= 59 or not 0 <= hour <= 23 or (meridiem and not 1 <= hour <= 12):
        return None
    if meridiem:
        hour = (hour % 12) + (12 if meridiem == "pm" else 0)
    trigger = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if trigger <= now:
        trigger += timedelta(days=1)
    daily = bool(re.search(r"\bevery\s+day\b", source, re.IGNORECASE))
    return {"trigger_time": trigger.isoformat(), "recurrence": "daily" if daily else "once", "payload": {"message": _message(source)}}
