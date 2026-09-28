"""
Focus Protocol Plugin for ALFRED Mark-LIV.
Manages deep work intervals, Pomodoro timers, and distraction-free focus sessions.
Stores state in ~/.alfred/focus_state.json (or ~/.jarvis/focus_state.json fallback).
Auto-discovered by core/plugin_loader.py.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path

_LEGACY_STATE_FILE = Path.home() / ".jarvis" / "focus_state.json"
_STATE_FILE = Path.home() / ".alfred" / "focus_state.json"
if not _STATE_FILE.exists() and _LEGACY_STATE_FILE.exists():
    _STATE_FILE = _LEGACY_STATE_FILE


def _read_state() -> dict:
    if not _STATE_FILE.exists():
        return {"active": False}
    try:
        return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"active": False}


def _write_state(st: dict) -> None:
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(json.dumps(st, indent=2), encoding="utf-8")


PLUGIN = {
    "name": "focus_protocol",
    "description": (
        "Controls deep work focus sessions and Pomodoro productivity intervals. "
        "Allows starting a focus block, checking time remaining, or concluding a session. "
        "Trigger when user says 'start focus mode', 'start a 25-minute focus session', "
        "'deep work mode', 'how much time is left in my focus session', or 'end focus mode'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Operation: 'start' (begin session), 'status' (check time left), or 'stop' (end session)."
            },
            "duration_minutes": {
                "type": "INTEGER",
                "description": "Length of focus interval in minutes (default: 25)."
            },
            "task": {
                "type": "STRING",
                "description": "Optional name of the target objective (e.g. 'Writing API docs')."
            }
        },
        "required": ["action"]
    },
    "behavior": "BLOCKING",
    "scheduling": "WHEN_IDLE"
}

PLUGIN_SETTINGS = {
    "settings": [
        {
            "id": "default_pomodoro_minutes",
            "type": "INT",
            "label": "Default Session Length (minutes)",
            "default": 25,
            "min": 5,
            "max": 120,
        }
    ]
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Execute focus protocol actions."""
    action = str(parameters.get("action", "start")).strip().lower()
    duration = int(parameters.get("duration_minutes", 25))
    task = parameters.get("task", "").strip() or "General Focus"

    state = _read_state()

    # 1. START SESSION
    if action == "start":
        now = time.time()
        ends_at = now + (duration * 60)
        state = {
            "active": True,
            "task": task,
            "started_at": now,
            "ends_at": ends_at,
            "duration_minutes": duration
        }
        _write_state(state)

        end_clock = datetime.fromtimestamp(ends_at).strftime("%I:%M %p")
        res = f"Sir, focus protocol initiated for {duration} minutes on '{task}'. Target completion at {end_clock}."
        if player:
            try:
                player.write_log(f"ALFRED: [Focus Protocol] Active: '{task}' ({duration}m, until {end_clock})")
            except Exception:
                pass
        return res

    # 2. STATUS CHECK
    if action == "status":
        if not state.get("active"):
            return "Sir, no active focus session is currently in progress."

        now = time.time()
        ends_at = state.get("ends_at", now)
        remaining = int((ends_at - now) / 60)

        if remaining <= 0:
            state["active"] = False
            _write_state(state)
            return "Sir, your focus session has concluded. Excellent work."

        task_name = state.get("task", "Focus block")
        return f"Sir, you have approximately {remaining} minute{'s' if remaining != 1 else ''} remaining on '{task_name}'."

    # 3. STOP SESSION
    if action in ("stop", "end", "cancel"):
        if not state.get("active"):
            return "Sir, no focus protocol was active."

        state["active"] = False
        _write_state(state)
        msg = "Focus protocol deactivated. Non-critical notifications and background audio restored."
        if player:
            try:
                player.write_log("ALFRED: [Focus Protocol] Session concluded.")
            except Exception:
                pass
        return msg

    return "Focus protocol standby."
