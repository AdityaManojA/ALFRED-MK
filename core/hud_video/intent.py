"""
core/hud_video/intent.py — Locus-phrase detection, intent precedence, and payload extraction.

Deterministic gate for HUD video requests and transport control.
Enforces:
- Transport route sits ahead of 'play <query>' new-video route
- Current video references ("current video", "this video", "it") route to transport
- Transport sits ahead of FOCUS/snooze only while Visual HUD is visible
- New video with timestamp ("play Dune trailer at 1:10") extracts start_s
- Acknowledgements are a toast only (SPEAK_TRANSPORT = False)
- TERSE ALFRED persona ("sir")
"""

from __future__ import annotations

import re
from typing import NamedTuple, Optional

from core.hud_video.mediatime import parse_media_time, ParsedTime

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

SPEAK_TRANSPORT: bool = False       # Transport acks are toasts only, not speech
DUCK_VOLUME_PCT: float = 30.0       # Volume percent during ALFRED speech ducking

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

_FILLER = re.compile(
    r"\b(me|us|the|a|an|some|up|please|now|quickly|sir)\b",
    re.IGNORECASE,
)
_SPACES = re.compile(r" {2,}")


class IntentResult(NamedTuple):
    locus_found: bool
    play_intent_found: bool
    query: str          # Cleaned query with locus + intent verbs stripped
    locus_matched: str  # Which locus phrase was detected ("" if none)
    start_s: Optional[float] = None  # Start timestamp for new videos


class HudIntentClassification(NamedTuple):
    action: str                     # "pause", "resume", "replay", "seek", "query_time", "stop", "new_video", "none"
    target: str = ""                # Query for new video
    seek_s: Optional[float] = None  # Absolute seek position or None
    is_relative: bool = False       # True if seek_s is a delta (+30, -10)
    start_s: Optional[float] = None # Start position for new video


def detect(utterance: str) -> IntentResult:
    """Parse a raw utterance for HUD video intent and optional start timestamp.

    Returns an IntentResult. Only `locus_found AND play_intent_found` means
    the utterance should trigger a new HUD video.
    """
    lower = utterance.lower().strip()

    # 1. Find locus phrase
    locus_matched = ""
    for phrase in VIDEO_LOCUS_PHRASES:
        if phrase in lower:
            locus_matched = phrase
            break

    # 2. Find play intent
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
            start_s=None,
        )

    # 3. Strip locus phrase(s)
    clean = utterance
    for phrase in VIDEO_LOCUS_PHRASES:
        clean = re.sub(re.escape(phrase), "", clean, flags=re.IGNORECASE)

    # 4. Extract optional timestamp at the end: "at 1:10", "from 2:35"
    start_s: Optional[float] = None
    time_match = re.search(
        r"\b(?:at|from)\s+(\d{1,2}:\d{2}(?::\d{2})?|\d+\s*(?:minutes?|seconds?))\b",
        clean,
        re.IGNORECASE,
    )
    if time_match:
        parsed = parse_media_time(time_match.group(1))
        if parsed is not None:
            start_s = parsed.seconds
            clean = clean[:time_match.start()] + clean[time_match.end():]

    # 5. Strip intent verbs at the start
    for word in sorted(PLAY_INTENT_WORDS, key=len, reverse=True):
        clean = re.sub(
            rf"^\s*{re.escape(word)}\s*", "", clean.strip(), flags=re.IGNORECASE
        )

    # 6. Strip filler words and tidy whitespace
    clean = _FILLER.sub(" ", clean).strip()
    clean = _SPACES.sub(" ", clean).strip(" .,!?")

    return IntentResult(
        locus_found=True,
        play_intent_found=True,
        query=clean,
        locus_matched=locus_matched,
        start_s=start_s,
    )


def classify_hud_intent(
    utterance: str,
    video_loaded: bool = False,
    video_visible: bool = False,
    duration_s: float = 0.0,
) -> HudIntentClassification:
    """Master intent router with strict precedence.

    Rules:
    - Transport route sits ahead of 'play <query>' new-video route.
    - With video loaded: bare transport words, phrases with current/this/it/the video,
      and bare time references route to transport.
    - Transport sits ahead of FOCUS pause/resume and snooze only while Visual HUD is visible.
    - FOCUS remains reachable with "pause focus".
    """
    lower = utterance.lower().strip()

    # Rule: FOCUS stays reachable with explicit "pause focus" / "stop focus"
    if re.search(r"\b(pause|stop|resume|snooze)\s+focus\b", lower):
        return HudIntentClassification(action="none")

    # 1. Close Visual HUD / back to globe
    if re.search(
        r"\b(close\s+(the\s+)?visual\s+hud|back\s+to\s+(the\s+)?globe|dismiss\s+(the\s+)?visual\s+hud|"
        r"return\s+to\s+(the\s+)?globe|restore\s+(the\s+)?avatar|bring\s+back\s+(the\s+)?avatar|"
        r"bring\s+back\s+(the\s+)?globe|restore\s+(the\s+)?globe|stop\s+video|close\s+video|"
        r"close\s+player|stop\s+player)\b",
        lower,
    ):
        return HudIntentClassification(action="stop")

    # 2. Query time left / position ("how much is left / where are we")
    if re.search(r"\b(how\s+much\s+(time\s+)?is\s+left|where\s+are\s+we|how\s+long\s+is\s+left|time\s+left|remaining\s+time)\b", lower):
        if video_loaded and video_visible:
            return HudIntentClassification(action="query_time")

    # 3. Replay ("replay / play again / restart / start over")
    if re.search(r"\b(replay|play\s+again|restart|start\s+over)\b", lower):
        if video_loaded:
            return HudIntentClassification(action="replay")

    # 4. Phrases targeting the current video:
    # "play the current video at 2:35", "jump to 1:15 in this video", "seek the current video to 30s"
    has_current_ref = bool(re.search(
        r"\b(current\s+video|this\s+video|the\s+video|it|this\s+clip|the\s+current\s+video)\b",
        lower,
    ))

    if has_current_ref and video_loaded:
        # Check for time expression
        parsed = parse_media_time(lower, duration_s)
        if parsed is not None:
            return HudIntentClassification(
                action="seek",
                seek_s=parsed.seconds,
                is_relative=parsed.is_relative,
            )
        if re.search(r"\b(pause|freeze)\b", lower):
            return HudIntentClassification(action="pause")
        if re.search(r"\b(resume|continue|play|unpause)\b", lower):
            return HudIntentClassification(action="resume")

    # 5. Bare transport commands (only while Visual HUD is visible and loaded)
    if video_visible and video_loaded:
        # Bare pause
        if re.search(r"^\s*(pause|pause\s+playback|freeze)\s*$", lower):
            return HudIntentClassification(action="pause")

        # Bare resume / play
        if re.search(r"^\s*(resume|continue|unpause|keep\s+playing)\s*$", lower):
            return HudIntentClassification(action="resume")

        # Direct time reference or seek: "play at 2:35", "jump to 2:35", "go to 2:35", "skip to 2:35", "forward 30s"
        if re.search(r"\b(play\s+at|go\s+to|jump\s+to|skip\s+to|seek\s+to|forward|back|rewind|advance)\b", lower):
            parsed = parse_media_time(lower, duration_s)
            if parsed is not None:
                return HudIntentClassification(
                    action="seek",
                    seek_s=parsed.seconds,
                    is_relative=parsed.is_relative,
                )

    # 6. Check for new video with locus: "play <query> in the app"
    locus_res = detect(utterance)
    if locus_res.locus_found and locus_res.play_intent_found and locus_res.query:
        return HudIntentClassification(
            action="new_video",
            target=locus_res.query,
            start_s=locus_res.start_s,
        )

    return HudIntentClassification(action="none")


def is_transport_command(utterance: str) -> str | None:
    """Backward-compatible helper for basic transport command detection."""
    lower = utterance.lower().strip()

    _TRANSPORT: dict[str, list[str]] = {
        "pause":      ["pause", "pause video", "pause player", "pause this"],
        "resume":     ["resume", "resume video", "unpause", "continue playing", "keep playing"],
        "replay":     ["replay", "play again", "restart", "start over", "replay video"],
        "stop_video": [
            "stop video", "close video", "close player", "stop player",
            "dismiss video", "dismiss player", "bring back the avatar",
            "restore avatar", "exit video", "quit player",
            "close the visual hud", "close visual hud", "back to the globe",
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
