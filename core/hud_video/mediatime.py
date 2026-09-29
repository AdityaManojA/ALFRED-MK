"""
core/hud_video/mediatime.py — Natural language media timestamp and relative skip parser.

Pure Python (no Qt, no network, zero dependencies).
Parses:
- "2:35", "02:35", "1:02:03"
- "2 minutes 35 seconds", "90 seconds", "1 minute", "a minute"
- "two thirty five", "one fifteen", "three forty"
- "the start", "beginning", "halfway", "the end"
- Relative: "forward 30 seconds", "back 30 seconds", "skip a minute", "rewind 15 seconds"
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Named Constants
# ---------------------------------------------------------------------------

DEFAULT_SKIP_S: float = 10.0

WORD_TO_NUM: dict[str, int] = {
    "zero": 0, "oh": 0, "o'clock": 0,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
}


@dataclass(frozen=True)
class ParsedTime:
    """Result of parsing a timestamp or relative time offset."""
    seconds: float
    is_relative: bool = False
    raw_match: str = ""


# ---------------------------------------------------------------------------
# Parser Logic
# ---------------------------------------------------------------------------

def _words_to_number(phrase: str) -> Optional[int]:
    """Convert spoken number phrases like 'thirty five' or 'two' to an integer."""
    tokens = phrase.lower().strip().split()
    if not tokens:
        return None

    # Check if purely digits
    if len(tokens) == 1 and tokens[0].isdigit():
        return int(tokens[0])

    val = 0
    matched = 0
    for tok in tokens:
        if tok in WORD_TO_NUM:
            val += WORD_TO_NUM[tok]
            matched += 1
        elif tok.isdigit():
            val += int(tok)
            matched += 1
        else:
            return None
    return val if matched > 0 else None


def parse_media_time(utterance: str, duration_s: float = 0.0) -> Optional[ParsedTime]:
    """Parse an utterance for absolute timestamps or relative skips.

    Returns ParsedTime(seconds, is_relative) or None if no time expression found.
    """
    text = utterance.lower().strip()

    # 1. Colon-separated timestamps: "H:MM:SS" or "M:SS" (e.g. "1:02:03", "2:35", "0:45")
    colon_match = re.search(r"\b(?:at\s+|to\s+)?(\d{1,2}):(\d{2})(?::(\d{2}))?\b", text)
    if colon_match:
        part1 = int(colon_match.group(1))
        part2 = int(colon_match.group(2))
        part3 = colon_match.group(3)
        if part3 is not None:
            # H:MM:SS
            secs = float(part1 * 3600 + part2 * 60 + int(part3))
        else:
            # M:SS
            secs = float(part1 * 60 + part2)
        return ParsedTime(seconds=secs, is_relative=False, raw_match=colon_match.group(0))

    # 2. Symbolic references
    if re.search(r"\b(the\s+)?(start|beginning)\b", text):
        return ParsedTime(seconds=0.0, is_relative=False, raw_match="start")
    if re.search(r"\b(halfway|the\s+middle|middle)\b", text):
        half = max(0.0, duration_s / 2.0)
        return ParsedTime(seconds=half, is_relative=False, raw_match="halfway")
    if re.search(r"\b(the\s+)?end\b", text):
        return ParsedTime(seconds=max(0.0, duration_s), is_relative=False, raw_match="end")

    # 3. Relative time skips ("forward 30 seconds", "back 10s", "rewind a minute", "skip 15 seconds")
    rel_match = re.search(
        r"\b(forward|ahead|skip|jump|fast[- ]forward|advance|back|backward|rewind)\s+"
        r"(?:by\s+)?(?:about\s+)?(\d+|a|an|one|two|three|four|five|ten|fifteen|twenty|thirty|forty|fifty)?"
        r"\s*(seconds?|secs?|minutes?|mins?|s|m)?\b",
        text,
    )
    if rel_match:
        direction_word = rel_match.group(1)
        qty_word = rel_match.group(2) or "10"
        unit_word = rel_match.group(3) or "seconds"

        is_backward = direction_word in ("back", "backward", "rewind")

        # Resolve quantity
        if qty_word in ("a", "an", "one"):
            qty = 1.0
        elif qty_word in WORD_TO_NUM:
            qty = float(WORD_TO_NUM[qty_word])
        elif qty_word.isdigit():
            qty = float(qty_word)
        else:
            qty = DEFAULT_SKIP_S

        # Unit multiplier
        if unit_word.startswith("m"):
            qty *= 60.0

        delta = -qty if is_backward else qty
        return ParsedTime(seconds=delta, is_relative=True, raw_match=rel_match.group(0))

    # 4. Spoken / written units: "2 minutes 35 seconds", "90 seconds", "1 minute"
    min_sec_match = re.search(
        r"\b(?:at\s+|to\s+)?(?:(\d+|a|an|one|two|three|four|five|ten|fifteen|twenty|thirty|forty|fifty)\s*(?:minutes?|mins?))?"
        r"(?:\s*(?:and\s+)?(\d+|one|two|three|four|five|ten|fifteen|twenty|thirty|forty|fifty)\s*(?:seconds?|secs?))?\b",
        text,
    )
    if min_sec_match and (min_sec_match.group(1) or min_sec_match.group(2)):
        m_str = min_sec_match.group(1)
        s_str = min_sec_match.group(2)
        total_s = 0.0

        if m_str:
            if m_str in ("a", "an", "one"):
                total_s += 60.0
            elif m_str in WORD_TO_NUM:
                total_s += WORD_TO_NUM[m_str] * 60.0
            elif m_str.isdigit():
                total_s += int(m_str) * 60.0

        if s_str:
            if s_str in WORD_TO_NUM:
                total_s += WORD_TO_NUM[s_str]
            elif s_str.isdigit():
                total_s += int(s_str)

        if total_s > 0.0:
            return ParsedTime(seconds=total_s, is_relative=False, raw_match=min_sec_match.group(0))

    # 5. Spoken minutes and seconds: "two thirty five", "one fifteen", "three forty"
    spoken_match = re.search(
        r"\b(?:at\s+|to\s+)?(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+"
        r"(twenty\s+\w+|thirty\s+\w+|forty\s+\w+|fifty\s+\w+|o'clock|oh\s+\w+|fifteen|twenty|thirty|forty|fifty|\d{1,2})\b",
        text,
    )
    if spoken_match:
        m_word = spoken_match.group(1)
        s_phrase = spoken_match.group(2)
        minutes = WORD_TO_NUM.get(m_word)
        if minutes is not None:
            # Handle "oh five" -> 5
            if s_phrase.startswith("oh "):
                s_part = s_phrase[3:].strip()
                seconds = WORD_TO_NUM.get(s_part, 0)
            elif s_phrase == "o'clock":
                seconds = 0
            else:
                seconds = _words_to_number(s_phrase)

            if seconds is not None:
                return ParsedTime(
                    seconds=float(minutes * 60 + seconds),
                    is_relative=False,
                    raw_match=spoken_match.group(0),
                )

    # 6. Standalone seconds: "90 seconds", "45s"
    sec_only_match = re.search(r"\b(?:at\s+|to\s+)?(\d+)\s*(?:seconds?|secs?)\b", text)
    if sec_only_match:
        return ParsedTime(
            seconds=float(sec_only_match.group(1)),
            is_relative=False,
            raw_match=sec_only_match.group(0),
        )

    return None
