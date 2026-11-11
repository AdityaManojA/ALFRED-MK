"""
core/integrations/alexa/skill_model.py — Interaction model, intent contracts, and utterance fixtures for Alexa Custom Skill.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class TypedSkillIntent:
    """An Alexa skill intent name with its slot values."""
    intent_name: str
    slots: dict[str, Any] = field(default_factory=dict)


def parse_iso_duration_to_minutes(duration_str: str) -> Optional[int]:
    """Parse ISO-8601 duration (e.g., PT25M, PT1H, PT30S) or conversational duration to minutes."""
    if not duration_str:
        return None
    s = duration_str.strip().upper()
    # ISO-8601 regex: e.g. PT25M, PT1H30M
    match = re.match(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", s)
    if match:
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        total_mins = hours * 60 + minutes + (1 if seconds >= 30 else 0)
        return total_mins if total_mins > 0 else 1

    # Conversational numbers: "25 minutes", "twenty-five minutes"
    digit_match = re.search(r"(\d+)\s*(?:min|minute)", s, re.I)
    if digit_match:
        return int(digit_match.group(1))

    return None


# ── Utterance to Intent Deterministic Mapping ────────────────────────────────
SKILL_UTTERANCE_FIXTURES: list[tuple[re.Pattern, str, list[str]]] = [
    # Status / Telemetry
    (re.compile(r"^(what('s| is) (your |my )?status|status check|how are you|system status)\b", re.I), "AlfredStatusIntent", []),
    (re.compile(r"^(what('s| is) on my schedule|what is my schedule|do i have any meetings|schedule status)\b", re.I), "ScheduleStatusIntent", []),

    # Focus
    (re.compile(r"^start focus( mode)?( for (?P<duration>.+))?$", re.I), "StartFocusIntent", ["duration"]),
    (re.compile(r"^(stop|end|cancel) focus( mode)?$", re.I), "StopFocusIntent", []),

    # Media Playback
    (re.compile(r"^(pause|stop) (the |current )?(music|media|video|playback)$", re.I), "PauseMediaIntent", []),
    (re.compile(r"^(resume|play|unpause) (the |current )?(music|media|video|playback)$", re.I), "ResumeMediaIntent", []),

    # Diagnostics
    (re.compile(r"^(what('s| is) my internet speed|check internet speed|run a speed test|internet speed)\b", re.I), "InternetSpeedIntent", []),

    # Reminders
    (re.compile(r"^set a reminder( to (?P<reminder_text>.+?))?( at (?P<time>.+))?$", re.I), "SetReminderIntent", ["reminder_text", "time"]),

    # Built-ins
    (re.compile(r"^(help|what can you do)$", re.I), "AMAZON.HelpIntent", []),
    (re.compile(r"^(cancel|stop|never mind|dismiss)$", re.I), "AMAZON.CancelIntent", []),
]


def map_utterance_to_intent(utterance: str) -> Optional[TypedSkillIntent]:
    """
    Deterministic rule-based mapper converting spoken utterances into typed Alexa skill intents
    without consuming general LLM inference tokens.
    """
    clean = (utterance or "").strip()
    for pattern, intent_name, slot_names in SKILL_UTTERANCE_FIXTURES:
        match = pattern.match(clean)
        if match:
            slots = {}
            for name in slot_names:
                val = match.groupdict().get(name)
                if val:
                    slots[name] = val.strip()
            return TypedSkillIntent(intent_name=intent_name, slots=slots)
    return None


def export_interaction_model(invocation_name: str = "alfred") -> dict[str, Any]:
    """
    Generate the official Amazon Skills Kit interaction model JSON document.
    Can be loaded directly into developer.amazon.com -> Build -> Interaction Model -> JSON Editor.
    """
    return {
        "interactionModel": {
            "languageModel": {
                "invocationName": invocation_name,
                "intents": [
                    {
                        "name": "AlfredStatusIntent",
                        "samples": [
                            "what is your status",
                            "system status",
                            "status check",
                            "how are you",
                        ],
                    },
                    {
                        "name": "StartFocusIntent",
                        "slots": [
                            {"name": "duration", "type": "AMAZON.Duration"}
                        ],
                        "samples": [
                            "start focus mode",
                            "start focus",
                            "start focus mode for {duration}",
                            "start focus for {duration}",
                        ],
                    },
                    {
                        "name": "StopFocusIntent",
                        "samples": [
                            "stop focus mode",
                            "stop focus",
                            "end focus mode",
                        ],
                    },
                    {
                        "name": "ScheduleStatusIntent",
                        "samples": [
                            "what is on my schedule",
                            "schedule status",
                            "what are my upcoming events",
                            "do i have any meetings today",
                        ],
                    },
                    {
                        "name": "PauseMediaIntent",
                        "samples": [
                            "pause the music",
                            "pause playback",
                            "pause media",
                            "pause the current video",
                        ],
                    },
                    {
                        "name": "ResumeMediaIntent",
                        "samples": [
                            "resume the music",
                            "resume playback",
                            "resume media",
                            "continue playing",
                        ],
                    },
                    {
                        "name": "InternetSpeedIntent",
                        "samples": [
                            "for my internet speed",
                            "what is my internet speed",
                            "check internet speed",
                            "run a speed test",
                        ],
                    },
                    {
                        "name": "SetReminderIntent",
                        "slots": [
                            {"name": "reminder_text", "type": "AMAZON.SearchQuery"},
                            {"name": "time", "type": "AMAZON.Time"}
                        ],
                        "samples": [
                            "set a reminder",
                            "set a reminder to {reminder_text}",
                            "set a reminder to {reminder_text} at {time}",
                        ],
                    },
                    {"name": "AMAZON.HelpIntent", "samples": []},
                    {"name": "AMAZON.CancelIntent", "samples": []},
                    {"name": "AMAZON.StopIntent", "samples": []},
                ],
                "types": [],
            }
        }
    }
