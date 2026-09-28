"""Action: Sentry MONITOR Mode Controller.

Provides tool invocation for Sentry Mode v2 MONITOR capabilities:
- Natural language target parsing (terminal, window title, log file, process, command, clipboard, screen)
- Status and active target descriptions
- Individual target removal
- Alert cooldown tuning (quieter / louder)
"""
from __future__ import annotations

import logging
from typing import Any

from core.sentry.monitor.controller import get_monitor_controller

_LOGGER = logging.getLogger(__name__)


def sentry_monitor_action(
    action: str,
    target: str = "",
    interval_seconds: float = 5.0,
    **kwargs: Any,
) -> str:
    """Execute a Sentry MONITOR mode action."""
    controller = get_monitor_controller()
    act = (action or "status").lower().strip()

    if act in ("start", "monitor", "watch"):
        res = controller.start(goal=target, interval_seconds=interval_seconds)
        if res.get("active"):
            if res.get("target_count", 0) > 0:
                return f"Sentry MONITOR mode activated for {res.get('target_count')} target(s): {res.get('label')}, sir."
            return "Sentry MONITOR mode activated. Asking what you would like to keep an eye on, sir."
        return "Could not start Sentry MONITOR mode, sir."

    elif act in ("stop", "cancel", "off", "halt"):
        reason = f"Stopped target '{target}'." if target else "Stopped by voice command."
        if target:
            return controller.remove_target(target)
        controller.stop(reason)
        return "Sentry MONITOR mode stopped, sir."

    elif act in ("status", "what_are_you_monitoring", "active", "describe"):
        return controller.what_are_you_monitoring()

    elif act in ("remove_target", "stop_target", "delete_target"):
        return controller.remove_target(target)

    elif act in ("quieter", "quiet", "cooldown_up"):
        return controller.quieter()

    elif act in ("louder", "loud", "cooldown_down"):
        return controller.louder()

    else:
        return f"Unknown monitor action '{action}'. Valid actions: start, stop, status, remove_target, quieter, louder."


TOOL = {
    "name": "sentry_monitor",
    "description": (
        "Controls Sentry MONITOR mode: watches terminal builds, window titles, files/logs, "
        "processes, shell commands, or screen regions. "
        "Use when user asks to: 'monitor this', 'keep an eye on ...', 'what are you monitoring', "
        "'stop monitoring', 'stop monitoring <target>', 'monitor quieter', or 'monitor louder'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "start | stop | status | remove_target | quieter | louder",
            },
            "target": {
                "type": "STRING",
                "description": "Natural language monitoring target or specific target name/id to stop.",
            },
            "interval_seconds": {
                "type": "NUMBER",
                "description": "Polling interval in seconds (default 5).",
            },
        },
        "required": ["action"],
    },
    "handler": sentry_monitor_action,
}
