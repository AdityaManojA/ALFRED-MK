"""
actions/hud_video.py — Visual HUD player and transport action handler for ALFRED.

LOCUS & PRECEDENCE RULES:
- Transport route sits ahead of 'play <query>' new-video route.
- With video loaded: bare transport words, phrases with current/this/it/the video,
  and bare time references route to transport.
- Transport sits ahead of FOCUS pause/resume and snooze only while Visual HUD is visible.
- New video with timestamp ("play Dune trailer at 1:10") extracts start_s.
- Acknowledgements are a toast only (SPEAK_TRANSPORT = False, SPEAK_RESOLVE = False).
- Terse ALFRED persona ("sir"). Speak ONLY on final failure and queries.
"""

from __future__ import annotations

import logging
import random
import re
import threading
import time
from typing import Any, Optional

from core.hud_video.intent import (
    SPEAK_TRANSPORT,
    classify_hud_intent,
    detect,
    VIDEO_LOCUS_PHRASES,
)
from core.hud_video.mediatime import parse_media_time
from core.hud_video.transport import format_timestamp, VideoStatus

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------
ANSWER_WINDOW_S: float = 8.0
DEST_REASK_MAX: int = 1
REMEMBER_DEST: bool = True
RESOLVE_DEBOUNCE_MS: int = 800
SAME_TARGET_TTL_S: int = 30
STT_GATE_AFTER_PLAY_S: float = 2.0
SPEAK_RESOLVE: bool = False

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
    "Visual HUD YouTube playback requires yt-dlp. "
    "Run pip install yt-dlp and try again, sir."
)


# ---------------------------------------------------------------------------
# Single Flight & Deduplication Manager
# ---------------------------------------------------------------------------

class _SingleFlightManager:
    """Thread-safe deduplication, debounce, and cancellation for HUD video resolution."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active_target: str = ""
        self._active_token: int = 0
        self._last_resolve_time: float = 0.0
        self._is_resolving: bool = False

    def normalize(self, target: str) -> str:
        """Strip punctuation and normalize whitespace for consistent target matching."""
        cleaned = re.sub(r"[^\w\s]", "", (target or "").lower())
        return re.sub(r"\s+", " ", cleaned).strip()

    def check_and_acquire(self, target: str) -> tuple[bool, str, int]:
        """Check if target can proceed or if it is duplicate/in-flight.

        Returns: (can_proceed, terminal_message, generation_token)
        """
        norm = self.normalize(target)
        now = time.monotonic()

        with self._lock:
            # 1. Debounce check: identical target within RESOLVE_DEBOUNCE_MS
            time_since_last = (now - self._last_resolve_time) * 1000.0
            if norm == self._active_target and time_since_last < RESOLVE_DEBOUNCE_MS:
                return (False, f"Visual HUD is already preparing {target}.", self._active_token)

            # 2. In-flight check: identical target within SAME_TARGET_TTL_S
            if self._is_resolving and norm == self._active_target and (now - self._last_resolve_time) < SAME_TARGET_TTL_S:
                return (False, f"Visual HUD is already preparing {target}.", self._active_token)

            # 3. New / different target: acquire resolve slot and increment token to cancel prior in-flight task
            self._active_token += 1
            self._active_target = norm
            self._last_resolve_time = now
            self._is_resolving = True
            token = self._active_token

            return (True, f"Playing {target} on the Visual HUD.", token)

    def is_current_token(self, token: int) -> bool:
        """Check if generation token is still current (not superseded by newer request)."""
        with self._lock:
            return token == self._active_token

    def mark_completed(self, token: int) -> None:
        """Mark resolution as finished."""
        with self._lock:
            if token == self._active_token:
                self._is_resolving = False

    def mark_failed(self, token: int) -> None:
        """Mark resolution as failed / cleared."""
        with self._lock:
            if token == self._active_token:
                self._is_resolving = False
                self._active_target = ""

    def reset(self) -> None:
        """Reset state for testing."""
        with self._lock:
            self._active_target = ""
            self._active_token = 0
            self._last_resolve_time = 0.0
            self._is_resolving = False


_single_flight = _SingleFlightManager()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_controller():
    """Retrieve the HudVideoController from the process-wide service registry."""
    from core.registry import lookup
    return lookup("hud_video_controller")


def _resolve_and_play(
    query: str,
    speak,
    controller,
    start_s: Optional[float] = None,
    token: int = 0,
) -> None:
    """Run in a thread pool: resolve then hand off to controller."""
    import time as _time
    from core.hud_video.resolve import PlayableRef, ResolveError, resolve
    from core.hud_video.backends.youtube import YouTubeResolveError

    _t0 = _time.monotonic()

    if not _single_flight.is_current_token(token):
        return

    try:
        ref = resolve(query, source_query=query)
    except ResolveError as exc:
        log.warning("[hud_video] resolve failed: %s", exc)
        if _single_flight.is_current_token(token):
            _single_flight.mark_failed(token)
            if controller:
                controller.signal_error(str(exc)[:60])
            if speak:
                speak(random.choice(VIDEO_FAIL_LINES))
        return
    except Exception as exc:
        log.exception("[hud_video] unexpected resolve error")
        if _single_flight.is_current_token(token):
            _single_flight.mark_failed(token)
            if controller:
                controller.signal_error("resolve_error")
            if speak:
                speak("Something went wrong, sir.")
        return

    if not _single_flight.is_current_token(token):
        return

    # YouTube kind: extract stream URL
    if ref.kind == "youtube":
        from core.hud_video.backends.youtube import extract_stream_url

        try:
            stream_res = extract_stream_url(ref.uri)
            if isinstance(stream_res, tuple):
                stream_url, audio_url = stream_res
            else:
                stream_url, audio_url = stream_res, None

            ref = PlayableRef(
                kind="direct_url",
                uri=stream_url,
                title=ref.title,
                thumb_url=ref.thumb_url,
                source_query=ref.source_query,
                audio_uri=audio_url,
            )
        except YouTubeResolveError as exc:
            msg = str(exc)
            log.warning("[hud_video] YouTube stream resolve failed: %s", msg)
            if _single_flight.is_current_token(token):
                _single_flight.mark_failed(token)
                if "not installed" in msg.lower():
                    if speak:
                        speak(VIDEO_YTDLP_MISSING_LINE)
                else:
                    if speak:
                        speak(f"Could not load the video, sir. {msg[:80]}")
                if controller:
                    controller.signal_error("youtube_resolve_error")
            return

    if not _single_flight.is_current_token(token):
        return

    _single_flight.mark_completed(token)

    elapsed_ms = int((_time.monotonic() - _t0) * 1000)
    # Privacy rule: never log raw stream URL tokens
    log.info("[hud_video] resolved media in %d ms", elapsed_ms)

    if controller:
        controller.on_resolved(ref, start_s=start_s or 0.0)


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
    """Main action handler."""
    params = parameters or {}
    action = params.get("action", "play").strip().lower()
    target = params.get("target", "").strip()
    locus_confirmed = params.get("locus_confirmed", False)
    timestamp_param = params.get("timestamp")

    controller = _get_controller()

    if player:
        player.write_log(f"[Visual HUD] action={action} target={target!r}")

    # --- 1. Preference & Memory commands ("always play in the app", "ask me again") ---
    from core.hud_video.destination import (
        check_preference_command,
        parse_explicit_destination,
        execute_destination,
        get_destination_manager,
    )
    from memory.config_manager import get_video_play_destination

    is_pref, pref_msg, _ = check_preference_command(target or action)
    if is_pref:
        if controller:
            controller.show_toast(pref_msg)
        return pref_msg

    # --- 2. Precedence & Intent Classification (Transport Controls) ---
    # Check if target is a transport command or current video command
    if controller is not None:
        c_state = controller.state()
        c_intent = classify_hud_intent(
            target or action,
            video_loaded=c_state.loaded,
            video_visible=controller.is_active,
            duration_s=c_state.duration_s,
        )

        if c_intent.action in ("pause", "resume", "replay", "seek", "query_time", "stop"):
            action = c_intent.action
            if c_intent.seek_s is not None:
                timestamp_param = c_intent.seek_s

        if c_intent.action == "new_video":
            action = "play"
            target = c_intent.target
            locus_confirmed = True
            if c_intent.start_s is not None:
                timestamp_param = c_intent.start_s

    # --- Transport commands ---
    if action in (
        "pause", "resume", "toggle", "replay", "seek", "seek_rel",
        "stop", "query_time", "mute", "unmute", "louder", "quieter"
    ):
        return _handle_transport(action, target, timestamp_param, controller, speak)

    # --- 3. Play action: Check explicit destination or prompt user ---
    if action == "play":
        # Check for start timestamp in target
        start_s: Optional[float] = None
        if timestamp_param is not None:
            try:
                start_s = float(timestamp_param)
            except (ValueError, TypeError):
                pass

        dest_kind, clean_target, named_app = parse_explicit_destination(target)
        if locus_confirmed:
            dest_kind = "app"

        # A. Explicit Destination Provided
        if dest_kind == "app":
            target_to_play = clean_target or target
            if not target_to_play:
                return "What would you like me to play in the Visual HUD, sir?"

            if controller is None:
                log.error("[hud_video] HudVideoController not registered")
                return "The Visual HUD is not available yet, sir."

            # Deduplication & single-flight check
            can_proceed, terminal_msg, token = _single_flight.check_and_acquire(target_to_play)
            if not can_proceed:
                return terminal_msg

            # Show loading chrome
            controller.begin_resolve(f"Searching: {target_to_play[:40]}…", source_query=target_to_play)
            controller.show_toast(f"Visual HUD: {target_to_play[:40]}")

            # Resolve off the Qt thread with token-based cancellation
            t = threading.Thread(
                target=_resolve_and_play,
                args=(target_to_play, speak, controller, start_s, token),
                daemon=True,
                name=f"hud-video-resolve-{token}",
            )
            t.start()
            return terminal_msg

        if dest_kind == "netflix":
            from core.pilots.netflix.actions import get_netflix_actions
            target_to_play = clean_target or target
            return get_netflix_actions().play_netflix(target_to_play)

        if dest_kind in ("youtube", "default", "window"):
            target_to_play = clean_target or target
            return execute_destination(
                dest_kind,
                target_to_play,
                start_s,
                controller,
                speak,
                app_name=named_app,
            )

        # B. No destination in request: check remembered preference
        target_to_play = clean_target or target
        if not target_to_play:
            return "What would you like me to play, sir?"

        if REMEMBER_DEST:
            remembered = get_video_play_destination()
            if remembered == "app":
                if controller is None:
                    return "The Visual HUD is not available yet, sir."
                can_proceed, terminal_msg, token = _single_flight.check_and_acquire(target_to_play)
                if not can_proceed:
                    return terminal_msg

                controller.begin_resolve(f"Searching: {target_to_play[:40]}…", source_query=target_to_play)
                controller.show_toast(f"Visual HUD: {target_to_play[:40]}")

                t = threading.Thread(
                    target=_resolve_and_play,
                    args=(target_to_play, speak, controller, start_s, token),
                    daemon=True,
                    name=f"hud-video-resolve-{token}",
                )
                t.start()
                return terminal_msg
            elif remembered:
                return execute_destination(
                    remembered,
                    target_to_play,
                    start_s,
                    controller,
                    speak,
                )

        # C. No preference & no explicit destination: Ask destination flow
        dest_mgr = get_destination_manager()
        if dest_mgr.is_prompting:
            return "Visual HUD is already asking for play destination."

        return dest_mgr.start_flow(target_to_play, start_s, controller, speak)

    return f"Unknown hud_video action: {action!r}"


def _handle_transport(
    action: str,
    target: str,
    timestamp_param: Any,
    controller,
    speak,
) -> str:
    """Handle all transport controls with deterministic returns."""
    if controller is None:
        return "The Visual HUD is not available yet, sir."

    c_state = controller.state()

    if action == "pause":
        controller.pause()
        controller.show_toast("Visual HUD: Paused")
        return "Visual HUD paused."

    if action == "resume":
        controller.resume()
        controller.show_toast("Visual HUD: Resumed")
        return "Visual HUD resumed."

    if action == "replay":
        controller.replay()
        controller.show_toast("Visual HUD: Replaying")
        return "Replaying Visual HUD video."

    if action == "toggle":
        if c_state.status == VideoStatus.PLAYING:
            controller.pause()
            controller.show_toast("Visual HUD: Paused")
            return "Visual HUD paused."
        else:
            controller.resume()
            controller.show_toast("Visual HUD: Resumed")
            return "Visual HUD resumed."

    if action in ("seek", "seek_rel"):
        abs_s: Optional[float] = None
        is_rel = False

        if timestamp_param is not None:
            try:
                abs_s = float(timestamp_param)
            except (ValueError, TypeError):
                pass

        if abs_s is None and target:
            parsed = parse_media_time(target)
            if parsed is not None:
                abs_s = parsed.seconds
                is_rel = parsed.is_relative

        if action == "seek_rel":
            is_rel = True

        if abs_s is None:
            return "Could not determine seek timestamp, sir."

        if is_rel:
            controller.seek_rel(abs_s)
            sign = "+" if abs_s >= 0 else ""
            controller.show_toast(f"Visual HUD: {sign}{int(abs_s)}s")
            return f"Skipped {sign}{int(abs_s)} seconds."
        else:
            controller.seek(abs_s)
            controller.show_toast(f"Visual HUD: {format_timestamp(abs_s)}")
            return f"Seeked to {format_timestamp(abs_s)}."

    if action == "query_time":
        rem_s = max(0.0, c_state.duration_s - c_state.position_s)
        pos_str = format_timestamp(c_state.position_s)
        rem_str = format_timestamp(rem_s)
        return f"Currently at {pos_str}, with {rem_str} remaining, sir."

    if action == "stop":
        controller.stop()
        controller.show_toast("Visual HUD: Closed")
        return "Visual HUD closed."

    if action == "mute":
        controller.set_muted(True)
        controller.show_toast("Visual HUD: Muted")
        return "Visual HUD muted."

    if action == "unmute":
        controller.set_muted(False)
        controller.show_toast("Visual HUD: Unmuted")
        return "Visual HUD unmuted."

    if action == "louder":
        from core.hud_video.controller import VIDEO_VOLUME_STEP
        controller.step_volume(VIDEO_VOLUME_STEP)
        return "Volume up."

    if action == "quieter":
        from core.hud_video.controller import VIDEO_VOLUME_STEP
        controller.step_volume(-VIDEO_VOLUME_STEP)
        return "Volume down."

    return "Unknown transport command."


TOOL = {
    "name": "hud_video",
    "description": (
        "Controls the Visual HUD in-app video player. "
        "Use this tool when the user says play/watch/show/stream PLUS an in-app locus "
        "('in the app', 'in the player', 'on the hud', 'on screen', 'in the batcomputer'), "
        "OR for transport controls ('pause', 'resume', 'replay', 'jump to 2:35', 'how much is left', "
        "'close the Visual HUD') when a video is loaded. "
        "Bare 'play X' or 'play music' is ALWAYS spotify_control, never hud_video. "
        "For 'play the current video at 2:35', use action='seek' or action='play'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "play | pause | resume | replay | seek | query_time | stop | mute | unmute | louder | quieter",
            },
            "target": {
                "type": "STRING",
                "description": "Video search query, URL, or time phrase (e.g. 'the current video at 2:35')",
            },
            "timestamp": {
                "type": "STRING",
                "description": "Optional timestamp (e.g. '2:35', '70') for seek or start time",
            },
            "locus_confirmed": {
                "type": "BOOLEAN",
                "description": "Set to true if user explicitly requested playback in-app/in-player/on-HUD",
            },
        },
        "required": ["action"],
    },
    "handler": hud_video,
}
