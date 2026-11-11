"""
core/integrations/alexa/policy.py — Safe command authorization and policy enforcement for Alexa.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Set


class AlexaRiskLevel(Enum):
    """Risk tiers for Alexa actions, from read-only to denied."""
    READ_ONLY = 0
    REVERSIBLE = 1
    SENSITIVE = 2
    DENIED = 3


@dataclass(frozen=True)
class AuthorizationDecision:
    """Result of an authorization check: allowed flag, risk level and reason."""
    allowed: bool
    risk_level: AlexaRiskLevel
    reason: str


@dataclass(frozen=True)
class AlexaContext:
    """Request metadata for an Alexa command (request id, hashed user/device, timestamp)."""
    request_id: str
    user_hash: str = ""
    device_hash: str = ""
    timestamp: float = 0.0


# ── Canonical Intent to Capability Mapping ──────────────────────────────────
DEFAULT_ALLOWED_INTENTS: dict[str, AlexaRiskLevel] = {
    # Read-Only Telemetry
    "AlfredStatusIntent": AlexaRiskLevel.READ_ONLY,
    "get_status": AlexaRiskLevel.READ_ONLY,
    "system_status": AlexaRiskLevel.READ_ONLY,
    "get_time": AlexaRiskLevel.READ_ONLY,
    "get_date": AlexaRiskLevel.READ_ONLY,
    "weather_report": AlexaRiskLevel.READ_ONLY,
    "get_weather": AlexaRiskLevel.READ_ONLY,
    "ScheduleStatusIntent": AlexaRiskLevel.READ_ONLY,
    "calendar_summary": AlexaRiskLevel.READ_ONLY,

    # Reversible Controls
    "StartFocusIntent": AlexaRiskLevel.REVERSIBLE,
    "start_focus": AlexaRiskLevel.REVERSIBLE,
    "StopFocusIntent": AlexaRiskLevel.REVERSIBLE,
    "stop_focus": AlexaRiskLevel.REVERSIBLE,
    "PauseMediaIntent": AlexaRiskLevel.REVERSIBLE,
    "pause_media": AlexaRiskLevel.REVERSIBLE,
    "ResumeMediaIntent": AlexaRiskLevel.REVERSIBLE,
    "resume_media": AlexaRiskLevel.REVERSIBLE,
    "mute_microphone": AlexaRiskLevel.REVERSIBLE,
    "unmute_microphone": AlexaRiskLevel.REVERSIBLE,

    # Diagnostics / Background
    "InternetSpeedIntent": AlexaRiskLevel.REVERSIBLE,
    "internet_speed": AlexaRiskLevel.REVERSIBLE,
    "SetReminderIntent": AlexaRiskLevel.REVERSIBLE,

    # Built-in Alexa control intents
    "AMAZON.HelpIntent": AlexaRiskLevel.READ_ONLY,
    "AMAZON.CancelIntent": AlexaRiskLevel.READ_ONLY,
    "AMAZON.StopIntent": AlexaRiskLevel.READ_ONLY,
}

EXPLICIT_DENIED_INTENTS: set[str] = {
    "shell",
    "terminal",
    "run_command",
    "execute_script",
    "computer_control",
    "keyboard_type",
    "mouse_click",
    "screenshot",
    "screen_monitor",
    "screen_process",
    "webcam",
    "record_audio",
    "read_email",
    "send_email",
    "read_clipboard",
    "write_clipboard",
    "delete_file",
    "modify_file",
    "shutdown_alfred",
    "shutdown_jarvis",
    "undo",
    "password",
    "api_key_update",
}


class AlexaActionPolicy:
    """Policy engine enforcing strict permission checks on all incoming Alexa requests."""

    def __init__(self, allowed_overrides: Optional[dict[str, bool]] = None) -> None:
        """Initialise per-intent user permission toggles from ``allowed_overrides``."""
        # User toggles (e.g. from Manage Permissions panel)
        self._user_permissions: dict[str, bool] = dict(allowed_overrides or {})

    def is_capability_enabled(self, capability: str) -> bool:
        """Check if a named permission/capability is enabled."""
        return self._user_permissions.get(capability, True)

    def set_capability_enabled(self, capability: str, enabled: bool) -> None:
        """Update permission toggle."""
        self._user_permissions[capability] = bool(enabled)

    def get_permission_toggles(self) -> dict[str, bool]:
        """Return dict of current permission overrides."""
        return dict(self._user_permissions)

    def count_allowed_intents(self) -> int:
        """Return number of currently active allowed intents."""
        count = 0
        for intent in DEFAULT_ALLOWED_INTENTS:
            cap = self._map_intent_to_capability(intent)
            if self.is_capability_enabled(cap):
                count += 1
        return count

    def _map_intent_to_capability(self, intent: str) -> str:
        """Map intent name to a user-friendly capability toggle key."""
        lower = intent.lower()
        if "focus" in lower:
            return "focus_mode"
        if "media" in lower or "pause" in lower or "resume" in lower:
            return "media_playback"
        if "speed" in lower:
            return "internet_speed"
        if "schedule" in lower or "calendar" in lower:
            return "calendar_summary"
        if "reminder" in lower:
            return "reminders"
        if "mute" in lower:
            return "microphone_mute"
        return "telemetry_and_status"

    def authorize(
        self,
        intent: str,
        arguments: dict[str, Any],
        context: Optional[AlexaContext] = None,
    ) -> AuthorizationDecision:
        """Evaluate if an incoming Alexa intent is authorized to execute."""
        normalized = (intent or "").strip()

        # 1. Check explicit denylist
        if normalized.lower() in EXPLICIT_DENIED_INTENTS:
            return AuthorizationDecision(
                allowed=False,
                risk_level=AlexaRiskLevel.DENIED,
                reason=f"Action '{normalized}' is strictly prohibited for remote Alexa execution.",
            )

        # 2. Check if intent is recognized in allowlist
        risk = DEFAULT_ALLOWED_INTENTS.get(normalized)
        if risk is None:
            # Also check case-insensitive match
            for k, v in DEFAULT_ALLOWED_INTENTS.items():
                if k.lower() == normalized.lower():
                    risk = v
                    normalized = k
                    break

        if risk is None:
            return AuthorizationDecision(
                allowed=False,
                risk_level=AlexaRiskLevel.DENIED,
                reason=f"Intent '{normalized}' is not in the approved Alexa allowlist.",
            )

        # 3. Check user capability permission
        cap = self._map_intent_to_capability(normalized)
        if not self.is_capability_enabled(cap):
            return AuthorizationDecision(
                allowed=False,
                risk_level=risk,
                reason=f"Capability '{cap}' has been disabled by the user in Alexa permissions.",
            )

        # 4. Check for dangerous arguments (e.g. paths, scripts)
        for k, v in arguments.items():
            str_v = str(v).lower()
            if any(danger in str_v for danger in ("rmdir", "del ", "powershell", "cmd.exe", "eval(")):
                return AuthorizationDecision(
                    allowed=False,
                    risk_level=AlexaRiskLevel.DENIED,
                    reason=f"Argument '{k}' contained prohibited command syntax.",
                )

        return AuthorizationDecision(
            allowed=True,
            risk_level=risk,
            reason="Authorized by safe command policy.",
        )
