"""Small, dependency-free parsing of spoken times, dates and durations.

The model is asked for ISO 8601 local times, but people say "tomorrow at 7",
"in 20 minutes" or "next friday 3pm" and the model passes those through
often enough that tools should cope. Everything returned is a naive local
datetime.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_UNITS = {"s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1,
          "m": 60, "min": 60, "mins": 60, "minute": 60, "minutes": 60,
          "h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600,
          "d": 86400, "day": 86400, "days": 86400, "week": 604800, "weeks": 604800, "w": 604800}
_WORD_NUMS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
              "seven": 7, "eight": 8, "nine": 9, "ten": 10, "fifteen": 15, "twenty": 20,
              "thirty": 30, "forty": 40, "forty-five": 45, "fifty": 50, "sixty": 60, "ninety": 90,
              "half": 0.5, "couple": 2}


def parse_duration(text: str) -> float | None:
    """'10 minutes', '1h30m', 'an hour and a half', 'half an hour', '90s', '1:30' (m:s) → seconds."""
    s = str(text or "").strip().lower()
    if not s:
        return None
    try:
        return float(s) * 60          # bare number = minutes
    except ValueError:
        pass
    m = re.fullmatch(r"(\d+):(\d{2})(?::(\d{2}))?", s)
    if m:
        a, b, c = m.groups()
        return int(a) * 3600 + int(b) * 60 + int(c) if c else int(a) * 60 + int(b)
    s = re.sub(r"\bcouple of\b", "2", s)
    s = re.sub(r"\bhalf an? hour\b", "30 minutes", s)
    s = re.sub(r"\b(?:an?|one) hour and a half\b", "90 minutes", s)
    s = re.sub(r"\b(" + "|".join(k for k in _WORD_NUMS if len(k) > 2 and k not in ("half", "couple")) + r")\b",
               lambda m: str(_WORD_NUMS[m.group(1)]), s)
    s = re.sub(r"\b(\d+(?:\.\d+)?) (?:and a half (hours?|minutes?)|(hours?|minutes?) and a half)\b",
               lambda m: f"{float(m.group(1)) + 0.5} {m.group(2) or m.group(3)}", s)
    s = re.sub(r"\b(?:an?|one) (hour|minute|second|day|week)\b", r"1 \1", s)
    total, found = 0.0, False
    for num, unit in re.findall(r"(\d+(?:\.\d+)?)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?|days?|weeks?|[smhdw])(?![a-z])", s):
        key = unit if unit in _UNITS else {"w": "week"}.get(unit, unit)
        total += float(num) * _UNITS[key]
        found = True
    return total if found else None


def _time_of_day(s: str) -> tuple[int, int] | None:
    s = s.strip()
    if s in ("noon", "midday"):
        return 12, 0
    if s == "midnight":
        return 0, 0
    m = re.fullmatch(r"(\d{1,2})(?::|\.)?(\d{2})?\s*(a\.?m\.?|p\.?m\.?)?", s)
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").replace(".", "")
    if ap == "pm" and h < 12:
        h += 12
    if ap == "am" and h == 12:
        h = 0
    if h > 23 or mi > 59:
        return None
    return h, mi


def parse_datetime(text: str, now: datetime | None = None, prefer_future: bool = True) -> datetime | None:
    """ISO strings, 'in 20 minutes', 'tomorrow at 7am', 'friday 3pm', '19:30', 'tonight at 9'."""
    now = now or datetime.now()
    s = str(text or "").strip()
    if not s:
        return None
    iso = s.replace("Z", "")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(iso[:len(datetime.now().strftime(fmt))], fmt)
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(s)
        return dt.astimezone().replace(tzinfo=None) if dt.tzinfo else dt
    except ValueError:
        pass

    low = s.lower().strip()
    low = re.sub(r"\b(o'?clock)\b", "", low)
    low = re.sub(r"\s+", " ", low).strip()

    m = re.match(r"^in (.+)$", low)
    if m:
        secs = parse_duration(m.group(1))
        return now + timedelta(seconds=secs) if secs else None

    day = None
    rest = low
    if rest.startswith("today"):
        day, rest = now.date(), rest[5:]
    elif rest.startswith("tonight"):
        day, rest = now.date(), rest[7:]
        if not re.search(r"\d", rest):
            rest = "9pm"
    elif rest.startswith(("this evening", "this afternoon", "this morning")):
        day, rest = now.date(), rest[len(rest.split()[0]) + len(rest.split()[1]) + 1:]
    elif rest.startswith("tomorrow"):
        day, rest = (now + timedelta(days=1)).date(), rest[8:]
    elif rest.startswith("day after tomorrow"):
        day, rest = (now + timedelta(days=2)).date(), rest[18:]
    else:
        m = re.match(r"^(next |this )?(" + "|".join(_WEEKDAYS) + r")\b", rest)
        if m:
            target = _WEEKDAYS.index(m.group(2))
            delta = (target - now.weekday()) % 7
            if delta == 0 or m.group(1) == "next ":
                delta = delta or 7
            day, rest = (now + timedelta(days=delta)).date(), rest[m.end():]
    rest = re.sub(r"^(,|\s|at|morning|evening|afternoon|night)+", "", rest).strip()
    if "morning" in low and not rest:
        rest = "8am"
    tod = _time_of_day(rest) if rest else None
    if tod and tod[0] < 12 and not re.search(r"[ap]\.?m", rest) and re.search(r"tonight|evening|afternoon", low):
        tod = (tod[0] + 12, tod[1])
    if tod is None and day is None:
        return None
    if tod is None:
        tod = (9, 0)
    if day is None:
        cand = now.replace(hour=tod[0], minute=tod[1], second=0, microsecond=0)
        # "7" with no am/pm said at 18:00 most likely means 19:00, not tomorrow 07:00.
        if prefer_future and cand <= now and not re.search(r"[ap]\.?m", rest) and tod[0] < 12:
            if cand + timedelta(hours=12) > now:
                return cand + timedelta(hours=12)
        if prefer_future and cand <= now:
            cand += timedelta(days=1)
        return cand
    return datetime(day.year, day.month, day.day, tod[0], tod[1])


def parse_days(text) -> list[int]:
    """Repeat rule → ISO weekdays (1=Mon…7=Sun). '' / 'once' → []."""
    if isinstance(text, (list, tuple)):
        out = []
        for t in text:
            out += parse_days(t) if isinstance(t, str) else [int(t)]
        return sorted(set(d for d in out if 1 <= d <= 7))
    s = str(text or "").lower().strip()
    if s in ("", "once", "none", "never", "no"):
        return []
    if s in ("daily", "every day", "everyday"):
        return [1, 2, 3, 4, 5, 6, 7]
    if "weekday" in s:
        return [1, 2, 3, 4, 5]
    if "weekend" in s:
        return [6, 7]
    return sorted({i + 1 for i, d in enumerate(_WEEKDAYS) if d[:3] in s})


def speak_time(dt: datetime, now: datetime | None = None) -> str:
    now = now or datetime.now()
    t = dt.strftime("%-I:%M %p")
    if dt.date() == now.date():
        return f"today at {t}"
    if dt.date() == (now + timedelta(days=1)).date():
        return f"tomorrow at {t}"
    if 0 < (dt.date() - now.date()).days < 7:
        return f"{dt.strftime('%A')} at {t}"
    return dt.strftime(f"%A %-d %B at {t}")
