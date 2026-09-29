"""
core/hud_video/intent.py — Locus-phrase detection and payload extraction.

Deterministic gate (not model-only) for HUD video requests.
"""

from __future__ import annotations

import re
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Named constants — change phrases here only
# ---------------------------------------------------------------------------

VIDEO_LOCUS_PHRASES: tuple[str, ...] = (
    "in the app",
    "in app",
    "in the player",
    "in player",
    "on the player",
    "in the hud",
    "on the hud",
    "in hud",
    "on the screen",
    "on screen",
    "in the batcomputer",
    "on the batcomputer",
)

# Intent verbs that must accompany the locus
PLAY_INTENT_WORDS: tuple[str, ...] = (
    "play",
    "watch",
    "show",
    "put",
    "stream",
    "load",
    "pull up",
    "bring up",
    "open",
)

# Filler words between verb and target (stripped during extraction)
_FILLER = re.compile(
    r"\b(me|us|the|a|an|some|up|please|now|quickly|sir)\b",
    re.IGNORECASE,
)

# Collapse multiple spaces
_SPACES = re.compile(r" {2,}")


class IntentResult(NamedTuple):
    locus_found: bool
    play_intent_found: bool
    query: str          # Cleaned query with locus + intent verbs stripped
    locus_matched: str  # Which locus phrase was detected ("" if none)


def detect(utterance: str) -> IntentResult:
    """Parse a raw utterance for HUD video intent.

    Returns an IntentResult. Only `locus_found AND play_intent_found` means
    the utterance should trigger HUD video.  Either alone is not sufficient.

    Examples
    --------
    >>> r = detect("play the new Dune trailer in the app")
    >>> r.locus_found, r.play_intent_found, r.query
    (True, True, 'the new Dune trailer')

    >>> r = detect("play Starboy")
    >>> r.locus_found
    False
    """
    lower = utterance.lower().strip()

    # 1. Find locus phrase
    locus_matched = ""
    for phrase in VIDEO_LOCUS_PHRASES:
        if phrase in lower:
            locus_matched = phrase
            break

    # 2. Find play intent — word-boundary check to avoid 'player' matching 'play'
    play_found = any(
        re.search(rf"\b{re.escape(word)}\b", lower)
        for word in PLAY_INTENT_WORDS
    )

    if not locus_matched or not play_found:
        return IntentResult(
            locus_found=bool(locus_matched),
            play_intent_found=play_found,
            query="",
            locus_matched=locus_matched,
        )

    # 3. Strip locus phrase(s) from original utterance (case-insensitive)
    clean = utterance
    for phrase in VIDEO_LOCUS_PHRASES:
        clean = re.sub(re.escape(phrase), "", clean, flags=re.IGNORECASE)

    # 4. Strip intent verbs at the start of the remaining string
    for word in sorted(PLAY_INTENT_WORDS, key=len, reverse=True):
        clean = re.sub(
            rf"^\s*{re.escape(word)}\s*", "", clean.strip(), flags=re.IGNORECASE
        )

    # 5. Strip filler words and tidy whitespace
    clean = _FILLER.sub(" ", clean).strip()
    clean = _SPACES.sub(" ", clean).strip(" .,!?")

    return IntentResult(
        locus_found=True,
        play_intent_found=True,
        query=clean,
        locus_matched=locus_matched,
    )


def is_transport_command(utterance: str) -> str | None:
    """Detect transport/control commands that don't require a locus.

    Returns the normalised command name or None.
    Commands: pause, resume, stop_video, mute, unmute, louder, quieter.
    These fire when the HudVideoController is PLAYING or PAUSED without
    needing a locus phrase.
    """
    lower = utterance.lower().strip()

    _TRANSPORT: dict[str, list[str]] = {
        "pause":      ["pause", "pause video", "pause player"],
        "resume":     ["resume", "resume video", "unpause", "continue playing"],
        "stop_video": [
            "stop video", "close video", "close player", "stop player",
            "dismiss video", "dismiss player", "bring back the avatar",
            "restore avatar", "exit video", "quit player",
        ],
        "unmute":     ["unmute", "sound on", "with sound", "enable sound", "unmute video"],
        "mute":       ["mute", "sound off", "mute video", "mute player", "no sound"],
        "louder":     ["louder", "volume up", "turn up"],
        "quieter":    ["quieter", "softer", "volume down", "turn down"],
    }

    for cmd, triggers in _TRANSPORT.items():
        for t in triggers:
            if t in lower:
                return cmd

    return None
