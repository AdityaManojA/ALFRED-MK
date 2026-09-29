"""
actions/hud_video.py — In-HUD Video Player action for ALFRED.

LOCUS RULE (non-negotiable):
  This action must only be invoked when the user's utterance contains an
  explicit "in-app / in-player / in-HUD" locus phrase.
  Bare "play X" is music (spotify_control). This module enforces that
  deterministically in addition to the LLM system prompt instruction.

Speech contract:
  1. Immediately speak an ack line (before any network I/O).
  2. Resolve the target off the UI thread.
  3. On success: speak title and start playback muted.
  4. On failure: speak apology and return to avatar.
"""

from __future__ import annotations

import logging
import random
import threading
from typing import Any

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

VIDEO_ACK_LINES: tuple[str, ...] = (
    "Coming up, sir.",
    "On screen shortly, sir.",
    "Pulling that in now, sir.",
    "On it, sir.",
)

VIDEO_FAIL_LINES: tuple[str, ...] = (
    "I couldn't find that, sir.",
    "I'm unable to locate that, sir.",
    "No results for that one, sir.",
)

VIDEO_YTDLP_MISSING_LINE: str = (
    "YouTube in-HUD playback requires yt-dlp. "
    "Run pip install yt-dlp and try again, sir."
)

_RESOLVE_LOCK = threading.Lock()      # guard against double-start


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_controller():
    """Retrieve the HudVideoController from the process-wide service registry.

    Uses core.registry rather than `import main` to avoid the __main__ vs
    'main' module-identity split that occurs when running `python main.py`.
    """
    from core.registry import lookup
    return lookup("hud_video_controller")


def _resolve_and_play(query: str, speak, controller) -> None:
    """Run in a thread pool: resolve then hand off to controller."""
    import time as _time
    from core.hud_video.resolve import PlayableRef, ResolveError, resolve
    from core.hud_video.backends.youtube import YouTubeResolveError

    _t0 = _time.monotonic()

    try:
        ref = resolve(query, source_query=query)
    except ResolveError as exc:
        log.warning("[hud_video] resolve failed: %s", exc)
        if controller:
            controller.signal_error(str(exc)[:60])
        if speak:
            speak(random.choice(VIDEO_FAIL_LINES))
        return
    except Exception as exc:
        log.exception("[hud_video] unexpected resolve error")
        if controller:
            controller.signal_error("resolve_error")
        if speak:
            speak("Something went wrong, sir.")
        return

    # YouTube kind: try to extract stream URL
    if ref.kind == "youtube":
        from core.hud_video.backends.youtube import extract_stream_url

        try:
            stream_url = extract_stream_url(ref.uri)
            ref = PlayableRef(
                kind="direct_url",
                uri=stream_url,
                title=ref.title,
                thumb_url=ref.thumb_url,
                source_query=ref.source_query,
            )
        except YouTubeResolveError as exc:
            msg = str(exc)
            log.warning("[hud_video] YouTube stream resolve failed: %s", msg)
            if "not installed" in msg.lower():
                if speak:
                    speak(VIDEO_YTDLP_MISSING_LINE)
            else:
                if speak:
                    speak(f"Could not load the video, sir. {msg[:80]}")
            if controller:
                controller.signal_error("youtube_resolve_error")
            return

    if controller:
        controller.on_resolved(ref)

    elapsed_ms = int((_time.monotonic() - _t0) * 1000)
    log.info("[hud_video] resolved video_id=%s in %d ms",
             getattr(ref, 'uri', '')[:60], elapsed_ms)

    # Announce the title (non-blocking — happens concurrently with first frame)
    if speak and ref.title:
        speak(f"Playing in HUD: {ref.title}.")


# ---------------------------------------------------------------------------
# Action entry point
# ---------------------------------------------------------------------------

def hud_video(
    parameters: dict[str, Any],
    response=None,
    player=None,
    session_memory=None,
    speak=None,
) -> str:
    """Main action handler.

    Parameters
    ----------
    parameters["action"]   : play | pause | resume | stop | mute | unmute |
                             louder | quieter
    parameters["target"]   : search query / URL / path  (for play)
    parameters["locus_confirmed"] : bool — server-side gate, must be True for play
    """
    from core.hud_video.intent import detect

    params = parameters or {}
    action = params.get("action", "play").strip().lower()
    target = params.get("target", "").strip()
    locus_confirmed = params.get("locus_confirmed", False)

    controller = _get_controller()

    if player:
        player.write_log(f"[HUD Video] action={action} target={target!r}")

    # --- Transport commands (no locus required when video is active) ---
    if action in ("pause", "resume", "stop", "mute", "unmute", "louder", "quieter"):
        return _handle_transport(action, controller, speak)

    # --- Play action: REQUIRES locus gate ---
    if action == "play":
        # Deterministic locus re-check (model cannot bypass this)
        if not locus_confirmed:
            # Run intent detector on the target string as a last chance
            from core.hud_video.intent import detect
            r = detect(target)
            if not r.locus_found:
                log.debug("[hud_video] play rejected: no locus in target=%r", target)
                return (
                    "No locus phrase detected — this looks like a music request. "
                    "Use spotify_control for music."
                )

        if not target:
            return "What would you like me to play in the player, sir?"

        if controller is None:
            log.error(
                "[hud_video] HudVideoController not registered — "
                "check core/registry.py wiring in ui.py:_init_hud_video"
            )
            return "The HUD player is not available yet, sir."

        # Early ack — fires TTS immediately
        if speak:
            speak(random.choice(VIDEO_ACK_LINES))

        # Show loading chrome
        controller.begin_resolve(f"Searching: {target[:40]}…")

        # Resolve off the Qt thread
        t = threading.Thread(
            target=_resolve_and_play,
            args=(target, speak, controller),
            daemon=True,
            name="hud-video-resolve",
        )
        t.start()

        return f"[HUD Video] Resolving: {target[:60]}"

    return f"Unknown hud_video action: {action!r}"


def _handle_transport(action: str, controller, speak) -> str:
    if controller is None:
        return "HUD player is not active, sir."

    from core.hud_video.controller import VideoState

    state = controller.state

    if action == "pause":
        if state == VideoState.PLAYING:
            controller.pause()
            return "Video paused."
        return "Nothing to pause, sir."

    if action == "resume":
        if state == VideoState.PAUSED:
            controller.resume()
            return "Resuming video."
        return "Nothing to resume, sir."

    if action == "stop":
        controller.stop()
        return "Video stopped. Avatar restored."

    if action == "mute":
        controller.set_muted(True)
        return "Video muted."

    if action == "unmute":
        controller.set_muted(False)
        return "Video unmuted."

    if action == "louder":
        from core.hud_video.controller import VIDEO_VOLUME_STEP
        controller.step_volume(+VIDEO_VOLUME_STEP)
        return "Volume up."

    if action == "quieter":
        from core.hud_video.controller import VIDEO_VOLUME_STEP
        controller.step_volume(-VIDEO_VOLUME_STEP)
        return "Volume down."

    return "Unknown transport command."


# ---------------------------------------------------------------------------
# TOOL schema (auto-discovered by core/action_loader.py)
# ---------------------------------------------------------------------------

TOOL = {
    "name": "hud_video",
    "description": (
        "Play a video IN the HUD app. "
        "ONLY call this when the user explicitly says 'in the app', "
        "'in the player', 'in the HUD', 'on the screen', "
        "'in the batcomputer', or a listed alias. "
        "Bare 'play X' or 'play music' is ALWAYS spotify_control, never hud_video. "
        "For transport controls (pause/resume/stop/mute/unmute/louder/quieter) "
        "when video is active, no locus phrase is required."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "play | pause | resume | stop | mute | unmute | louder | quieter"
                    " (default: play)"
                ),
            },
            "target": {
                "type": "STRING",
                "description": (
                    "What to play: YouTube URL, direct media URL, local file path, "
                    "or a search description (e.g. 'Dune official trailer'). "
                    "Strip locus phrases before passing. For 'play this', "
                    "pass the resolved URL or current clipboard content."
                ),
            },
            "locus_confirmed": {
                "type": "BOOLEAN",
                "description": (
                    "Set to true ONLY when the user's utterance contained an "
                    "in-app/in-player/in-HUD locus phrase. Never set to true "
                    "for bare 'play X' requests."
                ),
            },
        },
        "required": [],
    },
    "handler": hud_video,
}
