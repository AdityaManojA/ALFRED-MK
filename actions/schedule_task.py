"""Voice-action bridge for the process-wide local scheduler."""

from __future__ import annotations

from core.registry import lookup, register
from core.scheduler import SchedulerEngine, parse_schedule


def _engine(player=None) -> SchedulerEngine:
    engine = lookup("scheduler_engine")
    if engine is not None:
        return engine
    # Action discovery can run before JarvisLive in isolated tests.
    engine = SchedulerEngine(speak=getattr(player, "request_say", lambda _text: None))
    register("scheduler_engine", engine)
    engine.start()
    return engine


def schedule_task(parameters, player=None, **_) -> dict | str:
    params = parameters or {}
    schedule_text = str(params.get("schedule") or params.get("text") or "")
    parsed = parse_schedule(schedule_text)
    if not parsed:
        return "I need a time such as 'in 10 minutes' or 'every day at 8:00 AM', sir."
    macro = str(params.get("action_type") or "").lower() == "macro" or bool(params.get("paste_text"))
    payload = parsed["payload"]
    action_type = "reminder"
    name = "voice reminder"
    if macro:
        target = str(params.get("target_app") or params.get("target_tab") or "").strip()
        paste_text = str(params.get("paste_text") or "").strip()
        if not target or not paste_text:
            return "A scheduled macro needs a target application or tab keyword and the text to paste, sir."
        action_type, name = "macro", "scheduled macro"
        payload = {"target_app": target, "target_tab": str(params.get("target_tab") or ""),
                   "paste_text": paste_text, "hit_run": bool(params.get("hit_run", True))}
    task = _engine(player).add(name, action_type, payload, parsed["trigger_time"], parsed["recurrence"])
    return {"scheduled": True, "id": task["id"], "action_type": action_type, "trigger_time": task["trigger_time"]}


TOOL = {
    "name": "schedule_task",
    "description": "Schedule a local reminder or an opt-in local macro. Understands 'in 10 minutes', 'at 23:35', and 'every day at 8:00 AM'.",
    "parameters": {"type": "OBJECT", "properties": {
        "text": {"type": "STRING", "description": "Spoken reminder plus time."},
        "schedule": {"type": "STRING", "description": "Schedule phrase when creating a macro."},
        "action_type": {"type": "STRING", "description": "Use 'macro' for local paste-and-run automation."},
        "target_app": {"type": "STRING", "description": "Target application or window-title keyword."},
        "target_tab": {"type": "STRING", "description": "Optional browser tab-title keyword."},
        "paste_text": {"type": "STRING", "description": "Local text pasted after focus succeeds."},
        "hit_run": {"type": "BOOLEAN", "description": "Press Enter 200 ms after paste (default true)."},
    }},
    "handler": schedule_task,
}
