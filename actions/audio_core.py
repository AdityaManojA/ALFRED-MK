# actions/audio_core.py
"""
Tactical Audio Core Control Action for ALFRED.

Controls the tactical HUD's background audio engine (Audio Core),
which runs the ambient TRON Legacy score ('The Son of Flynn') and custom soundtracks.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("audio_core")

_last_action: str = ""
_last_call_time: float = 0.0
_call_lock = threading.Lock()
_DEBOUNCE_SEC = 1.0


def audio_core(
    parameters: Optional[Dict[str, Any]] = None,
    player: Optional[Any] = None,
    **kwargs: Any
) -> str:
    """
    Main handler for the Audio Core control action.
    """
    global _last_action, _last_call_time

    params = parameters or {}
    action = str(params.get("action", "pause")).lower().strip()
    volume_percent = params.get("volume_percent")

    # Debounce rapid duplicate calls from multi-segment transcripts
    with _call_lock:
        now = time.time()
        if action == _last_action and (now - _last_call_time) < _DEBOUNCE_SEC:
            logger.debug(f"[AudioCore] Debouncing duplicate action '{action}'")
            return f"Audio Core {action} request already executed, sir."
        _last_action = action
        _last_call_time = now

    logger.info(f"[AudioCore] Action: {action} | Params: {params}")
    if hasattr(player, "write_log"):
        try:
            player.write_log(f"[AudioCore] Action: {action.upper()}" + (f" ({volume_percent}%)" if volume_percent is not None else ""))
        except Exception:
            pass

    if not player:
        return "Audio Core is currently not accessible from this interface, sir."

    # Locate the background player instance on MainWindow
    bg_player = getattr(player, "_bg_music", None)

    try:
        if action in ("pause", "stop", "halt", "mute", "turn_off", "off", "disable"):
            if hasattr(player, "pause_audio_core"):
                player.pause_audio_core()
            elif bg_player and hasattr(bg_player, "pause_core"):
                bg_player.pause_core()
            elif bg_player and hasattr(bg_player, "pause"):
                bg_player.pause()
            else:
                return "Could not pause the Audio Core, sir."
            return "Audio Core paused, sir."

        elif action in ("resume", "play", "start", "unpause", "turn_on", "on", "enable"):
            if hasattr(player, "resume_audio_core"):
                player.resume_audio_core()
            elif bg_player and hasattr(bg_player, "resume_core"):
                bg_player.resume_core()
            elif bg_player and hasattr(bg_player, "play"):
                bg_player.play()
            else:
                return "Could not resume the Audio Core, sir."
            return "Audio Core resumed, playing TRON Legacy score, sir."

        elif action in ("toggle", "toggle_play"):
            if bg_player and hasattr(bg_player, "toggle_play"):
                bg_player.toggle_play()
                state = "resumed" if bg_player.is_playing() else "paused"
                return f"Audio Core {state}, sir."
            elif hasattr(player, "resume_audio_core"):
                player.resume_audio_core()
                return "Audio Core toggled, sir."
            return "Could not toggle the Audio Core, sir."

        elif action in ("set_volume", "volume"):
            if volume_percent is None:
                # Default to current or reasonable 10%
                vol_val = 10
            else:
                try:
                    vol_val = int(volume_percent)
                except (ValueError, TypeError):
                    vol_val = 10
            vol_val = max(0, min(100, vol_val))

            if hasattr(player, "set_audio_core_volume"):
                player.set_audio_core_volume(vol_val)
            elif bg_player and hasattr(bg_player, "set_base_volume"):
                bg_player.set_base_volume(vol_val / 100.0)
            else:
                return "Could not adjust Audio Core volume, sir."
            return f"Audio Core volume set to {vol_val}%, sir."

        elif action in ("next", "skip_next", "skip"):
            if bg_player and hasattr(bg_player, "next_track"):
                bg_player.next_track()
                return "Advanced to next track on the Audio Core, sir."
            return "Could not skip Audio Core track, sir."

        elif action in ("prev", "previous", "skip_prev"):
            if bg_player and hasattr(bg_player, "prev_track"):
                bg_player.prev_track()
                return "Returning to previous track on the Audio Core, sir."
            return "Could not return to previous Audio Core track, sir."

        elif action in ("status", "info", "what_is_playing"):
            if hasattr(player, "get_audio_core_status"):
                st = player.get_audio_core_status()
                state_str = "playing" if st.get("is_playing") else "paused"
                vol = st.get("volume", 10)
                track = st.get("track", "The Son of Flynn")
                return f"Audio Core is currently {state_str}. Active track: {track} at {vol}% base volume, sir."
            elif bg_player:
                state_str = "playing" if bg_player.is_playing() else "paused"
                vol = int(bg_player.base_volume() * 100)
                return f"Audio Core is currently {state_str} at {vol}% volume, sir."
            return "Audio Core status is currently unavailable, sir."

        elif action in ("restore_tron", "tron_music", "default_score"):
            if hasattr(player, "restore_tron_music"):
                player.restore_tron_music()
            elif bg_player and hasattr(bg_player, "clear_spotify_and_restore_tron"):
                bg_player.clear_spotify_and_restore_tron()
            return "Audio Core restored to default TRON Legacy soundtrack, sir."

        else:
            return f"Unknown Audio Core action '{action}'. Available actions: pause, resume, play, stop, set_volume, status, next, prev, restore_tron."

    except Exception as e:
        logger.error(f"[AudioCore] Error handling action '{action}': {e}", exc_info=True)
        return f"Audio Core action '{action}' encountered an issue, sir: {e}"


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "audio_core",
    "description": (
        "Controls ALFRED's tactical Audio Core (the background TRON Legacy ambient music engine in the HUD). "
        "Use when the user asks to pause, resume, play, stop, mute, or adjust volume for the 'audio core', "
        "'tron music', 'background score', or 'ambient music' (e.g. 'pause audio core', 'resume audio core', 'audio core volume to 20%')."
    ),
    "scheduling": "WHEN_IDLE",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "pause | resume | play | stop | set_volume | status | next | prev | restore_tron (default: pause)"
            },
            "volume_percent": {
                "type": "INTEGER",
                "description": "Base volume percentage 0 to 100 (for set_volume action)"
            }
        },
        "required": []
    },
    "handler": audio_core,
}
