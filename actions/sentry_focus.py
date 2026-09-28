"""Action: Sentry FOCUS Mode Controller.

Provides tool invocation for Sentry Mode v2 FOCUS capabilities:
- Session start with duration in minutes and intent
- Session controls: pause, resume, extend, abort/stop
- Drift mitigations: snooze, excuse, and nag cadence adjustments
- Tone tuning: drill sergeant mode ('be harsh today') / gentle mode
- Surface locking
"""
from __future__ import annotations

import logging
from typing import Any

from core.sentry.focus.engine import get_focus_engine
from core.sentry.focus.state import DEFAULT_SESSION_MIN, SNOOZE_DEFAULT_S

_LOGGER = logging.getLogger(__name__)


def sentry_focus_action(
    action: str,
    duration_minutes: int = DEFAULT_SESSION_MIN,
    intent: str = "",
    minutes: int = 10,
    seconds: int = SNOOZE_DEFAULT_S,
    reason: str = "Research",
    lock_app: bool = False,
    lock_tab: bool = False,
    **kwargs: Any,
) -> str:
    """Execute a Sentry FOCUS mode action."""
    engine = get_focus_engine()
    act = (action or "status").lower().strip()

    if act in ("start", "begin", "focus"):
        mins = int(duration_minutes or DEFAULT_SESSION_MIN)
        res = engine.start(duration_minutes=mins, intent=intent, lock_app=lock_app, lock_tab=lock_tab)
        target_info = " Locked to current surface." if (lock_app or lock_tab) else " Will lock once you switch to your target window, sir."
        return f"FOCUS session initiated for {mins} minutes.{target_info}"

    elif act in ("pause", "freeze"):
        engine.pause()
        return "FOCUS session paused, sir."

    elif act in ("resume", "unpause"):
        engine.resume()
        return "FOCUS session resumed, sir."

    elif act in ("extend", "add_time", "more_time"):
        ext_m = int(minutes or 10)
        remaining = engine.extend(ext_m)
        return f"Session extended by {ext_m} minutes. {remaining // 60}m {remaining % 60}s remaining, sir."

    elif act in ("stop", "abort", "cancel", "end"):
        engine.abort(reason=f"Stopped by command: {reason}")
        return "FOCUS session terminated, sir."

    elif act in ("snooze", "silence"):
        snooze_s = int(seconds or SNOOZE_DEFAULT_S)
        engine.snooze(snooze_s)
        return f"Alerts snoozed for {snooze_s} seconds, sir."

    elif act in ("excuse", "research", "forgive"):
        engine.excuse(reason=reason)
        return f"Excursion excused for {reason}, sir. I will remain silent until you return to target."

    elif act in ("cadence", "nag_interval", "interval"):
        cadence_s = int(seconds or 30)
        actual = engine.set_nag_interval(cadence_s)
        return f"Drift reminder cadence set to {actual} seconds, sir."

    elif act in ("drill_sergeant", "harsh", "be_harsh", "tough"):
        engine.set_drill_sergeant(True)
        return "Drill sergeant mode engaged, sir. No mercy on distractions."

    elif act in ("gentle", "standard", "normal", "polite"):
        engine.set_drill_sergeant(False)
        return "Standard courteous tone restored, sir."

    elif act in ("status", "check", "remaining"):
        st = engine.get_state()
        if not st.active:
            return "No active FOCUS session, sir."
        m = st.remaining_s // 60
        s = st.remaining_s % 60
        status_desc = "paused" if st.paused else ("drifting" if st.drifting else "on target")
        return f"FOCUS session active: {m}m {s}s remaining ({status_desc}), sir."

    else:
        return f"Unknown FOCUS action '{action}'. Valid actions: start, pause, resume, extend, stop, snooze, excuse, cadence, drill_sergeant, gentle, status."


TOOL = {
    "name": "sentry_focus",
    "description": (
        "Controls Sentry FOCUS mode: manages distraction-free focus sessions, locks onto current window or tab, "
        "and handles drift controls. "
        "Actions: 'start' (with duration_minutes and optional intent), 'pause', 'resume', "
        "'extend' (with minutes), 'stop' / 'abort', 'snooze' (with seconds), 'excuse', 'cadence' (nag interval), "
        "'drill_sergeant' (be harsh today), 'gentle' (normal tone), or 'status'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "start | pause | resume | extend | stop | snooze | excuse | cadence | drill_sergeant | gentle | status",
            },
            "duration_minutes": {
                "type": "INTEGER",
                "description": "Session duration in minutes (e.g. 25, 30, 45). Default 25.",
            },
            "intent": {
                "type": "STRING",
                "description": "Optional stated intent or task description for this session.",
            },
            "minutes": {
                "type": "INTEGER",
                "description": "Minutes to add when action is 'extend'. Default 10.",
            },
            "seconds": {
                "type": "INTEGER",
                "description": "Seconds for snooze duration or nag cadence.",
            },
            "reason": {
                "type": "STRING",
                "description": "Reason for excusing the current excursion (e.g. 'research', 'documentation').",
            },
            "lock_app": {
                "type": "BOOLEAN",
                "description": "True to lock immediately to frontmost application.",
            },
            "lock_tab": {
                "type": "BOOLEAN",
                "description": "True to lock specifically to current browser tab/domain.",
            },
        },
        "required": ["action"],
    },
    "handler": sentry_focus_action,
}
