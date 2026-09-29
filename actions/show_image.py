"""
actions/show_image.py — Reference image viewer and candidate cycling action.

Voice phrases:
- "show me a reference image of X" / "pull up a picture of X"
- "another one / next" (cycles candidates)
- "previous image / previous"
- "close the image"
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from core.image_viewer import (
    FETCH_MAX_MB,
    FETCH_TIMEOUT_S,
    ReferenceImageSession,
    extract_host,
    fetch_image,
    get_image_viewer,
)
from core.registry import lookup, register

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named Constants
# ---------------------------------------------------------------------------
FAILURE_SPEECH: str = "Couldn't find one, sir."
TOAST_PREFIX: str = "Reference image:"


def get_image_session() -> ReferenceImageSession:
    """Retrieve or register the process-wide reference image session."""
    sess = lookup("reference_image_session")
    if sess is None:
        sess = ReferenceImageSession()
        register("reference_image_session", sess)
    return sess


def _present_fetch_result(res: Any, session: ReferenceImageSession, player: Any) -> None:
    """Safely marshal image display to Qt viewer window and show toast."""
    win = getattr(player, "_win", player)
    viewer = get_image_viewer(parent=win)

    cand_info = f"{session.current_index + 1}/{session.total_candidates}" if session.total_candidates > 1 else ""
    source = res.file_path or res.data

    # Marshal to Qt thread via signal
    viewer.show_requested.emit(source, res.attribution, res.host, cand_info)

    # Toast only (no voice announcement on success)
    if hasattr(player, "show_toast"):
        try:
            player.show_toast(f"{TOAST_PREFIX} {res.host}")
        except Exception as exc:
            log.debug("[show_image] show_toast failed: %s", exc)


def show_image(
    parameters: dict[str, Any],
    player: Any = None,
    speak: Any = None,
    **_,
) -> str:
    """Main tool handler for reference image display, cycling, and dismissal."""
    params = parameters or {}
    action = str(params.get("action") or "search").strip().lower()
    query = str(params.get("query") or params.get("path") or "").strip()

    session = get_image_session()

    # 1. Close command
    if action == "close":
        viewer = lookup("image_viewer")
        if viewer is not None:
            viewer.close_requested.emit()
        return "Reference image closed."

    # 2. Cycle next candidate ("another one / next")
    if action in ("next", "cycle"):
        res = session.next_candidate()
        if not res.success:
            if callable(speak):
                speak(FAILURE_SPEECH)
            return FAILURE_SPEECH
        _present_fetch_result(res, session, player)
        return f"Showing candidate {session.current_index + 1} of {session.total_candidates} from {res.host}."

    # 3. Cycle previous candidate
    if action in ("prev", "previous"):
        res = session.previous_candidate()
        if not res.success:
            if callable(speak):
                speak(FAILURE_SPEECH)
            return FAILURE_SPEECH
        _present_fetch_result(res, session, player)
        return f"Showing candidate {session.current_index + 1} of {session.total_candidates} from {res.host}."

    # 4. Search / Fetch command
    if not query:
        if callable(speak):
            speak(FAILURE_SPEECH)
        return FAILURE_SPEECH

    res = session.search(query)
    if not res.success:
        log.warning("[show_image] fetch failed: %s", res.error)
        if callable(speak):
            speak(FAILURE_SPEECH)
        return FAILURE_SPEECH

    _present_fetch_result(res, session, player)
    return f"Displaying reference image from {res.host}."


TOOL = {
    "name": "show_image",
    "description": (
        "Show a reference image or picture in the HUD, cycle candidate images, or close the viewer. "
        "Use action='search' with query='...' for 'show me a reference image of X' or 'pull up a picture of X'. "
        "Use action='next' for 'another one / next'. "
        "Use action='prev' for 'previous image'. "
        "Use action='close' for 'close the image'. "
        "Explicit local file paths stay local."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "search | next | prev | close",
            },
            "query": {
                "type": "STRING",
                "description": "Reference search term (e.g. 'Tesla Cybertruck') or local path",
            },
            "path": {
                "type": "STRING",
                "description": "Explicit local image file path",
            },
        },
    },
    "handler": show_image,
}
