"""
core/imagery/intent.py — Deterministic voice intent classification for image requests.

Precedence:
1. Cycle / close commands ("another one", "next", "previous", "close the image")
2. Clashes with video / media commands are rejected ("play ...", "close the visual hud", trailer/video indicators, video locus phrases)
3. Explicit file paths ("show me the file ...")
4. Reference image queries ("show me a reference image of ...", "pull up a picture of ...")
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Named Constants
# ---------------------------------------------------------------------------
IMAGE_SEARCH_PREFIXES: tuple[str, ...] = (
    "show me a reference image of ",
    "show me a picture of ",
    "show me an image of ",
    "show me a photo of ",
    "pull up a reference image of ",
    "pull up a picture of ",
    "pull up an image of ",
    "pull up a photo of ",
    "show me reference image of ",
    "show me ",
)

IMAGE_FILE_PREFIXES: tuple[str, ...] = (
    "show me the file ",
    "show the file ",
    "open the file ",
    "open image file ",
)

IMAGE_CYCLE_NEXT_PHRASES: tuple[str, ...] = (
    "another one",
    "next image",
    "next picture",
    "next one",
    "next candidate",
    "cycle image",
    "next",
)

IMAGE_CYCLE_PREV_PHRASES: tuple[str, ...] = (
    "previous image",
    "previous picture",
    "previous one",
    "prev image",
    "prev picture",
    "previous candidate",
    "prev",
    "previous",
)

IMAGE_CLOSE_PHRASES: tuple[str, ...] = (
    "close the image",
    "close image",
    "close the picture",
    "close picture",
    "dismiss the image",
    "dismiss image",
    "hide the image",
    "hide image",
    "close the viewer",
    "close image viewer",
)

VIDEO_LOCUS_PHRASES: tuple[str, ...] = (
    "in the app",
    "in the player",
    "on the hud",
    "on hud",
    "in hud",
    "on screen",
    "in the batcomputer",
    "on the batcomputer",
)

VIDEO_INDICATORS: tuple[str, ...] = (
    "trailer",
    "video",
    "movie",
    "teaser",
    "clip",
    "episode",
    "season",
    "stream",
    "youtube",
)

HUD_CLOSE_PHRASES: tuple[str, ...] = (
    "close the visual hud",
    "close visual hud",
    "close the hud",
    "close hud",
    "back to the globe",
    "restore the avatar",
    "hide the hud",
)


@dataclass(frozen=True)
class ImageIntentResult:
    """Structured representation of an image intent."""
    action: str       # "search", "path", "next", "prev", "close", "none"
    query: str = ""
    path: str = ""


def classify_image_intent(utterance: str) -> ImageIntentResult:
    """Classify user utterance into image intent with strict clash avoidance."""
    text = (utterance or "").strip()
    if not text:
        return ImageIntentResult(action="none")

    lower = text.lower().strip(" .,!?")

    # 1. Check HUD close phrases first (must not be intercepted by image close)
    for hud_close in HUD_CLOSE_PHRASES:
        if hud_close in lower:
            return ImageIntentResult(action="none")

    # 2. Check Image Close phrases
    if lower in IMAGE_CLOSE_PHRASES:
        return ImageIntentResult(action="close")

    # 3. Check Candidate Cycling phrases
    if lower in IMAGE_CYCLE_NEXT_PHRASES:
        return ImageIntentResult(action="next")
    if lower in IMAGE_CYCLE_PREV_PHRASES:
        return ImageIntentResult(action="prev")

    # 4. Reject audio/video playback clashes ("play ...")
    if lower.startswith("play "):
        return ImageIntentResult(action="none")

    # 5. Reject if any video locus phrase is present
    for locus in VIDEO_LOCUS_PHRASES:
        if locus in lower:
            return ImageIntentResult(action="none")

    # 6. Reject if any video indicator is present
    for vid_ind in VIDEO_INDICATORS:
        if vid_ind in lower:
            return ImageIntentResult(action="none")

    # 7. Check explicit file prefixes
    for file_pfx in IMAGE_FILE_PREFIXES:
        if lower.startswith(file_pfx):
            target = text[len(file_pfx):].strip()
            return ImageIntentResult(action="path", path=target)

    # 8. Check image search prefixes
    for search_pfx in IMAGE_SEARCH_PREFIXES:
        if lower.startswith(search_pfx):
            val = text[len(search_pfx):].strip()
            if not val:
                return ImageIntentResult(action="none")
            p = Path(val).expanduser()
            if p.is_file():
                return ImageIntentResult(action="path", path=val)
            return ImageIntentResult(action="search", query=val)

    return ImageIntentResult(action="none")


def detect(utterance: str) -> tuple[str, str]:
    """Legacy compatibility wrapper returning (action, query_or_path)."""
    res = classify_image_intent(utterance)
    if res.action == "none":
        return ("", "")
    if res.action == "search":
        return ("search", res.query)
    if res.action == "path":
        return ("path", res.path)
    return (res.action, "")
