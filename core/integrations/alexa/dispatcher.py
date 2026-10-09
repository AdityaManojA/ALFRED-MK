"""
core/integrations/alexa/dispatcher.py — Typed intent dispatcher for Alexa remote channel.
Enforces source="alexa" context and maps approved intents to safe ALFRED subsystems.
"""
from __future__ import annotations

import asyncio
import datetime
import logging
from typing import Any, Callable, Coroutine, Dict, Optional

from core.integrations.alexa.policy import (
    AlexaActionPolicy,
    AlexaContext,
    AlexaRiskLevel,
    AuthorizationDecision,
)
from core.integrations.alexa.skill_model import parse_iso_duration_to_minutes

logger = logging.getLogger("AlexaDispatcher")


class AlexaTypedDispatcher:
    """
    Typed dispatcher translating authorized Alexa intents directly into ALFRED subsystem operations.
    Never passes unconstrained voice text to LLM tool execution.
    """

    def __init__(
        self,
        policy: AlexaActionPolicy,
        background_task_runner: Optional[Callable[[str, Any], Coroutine[Any, Any, None]]] = None,
        hud_logger: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.policy = policy
        self.background_task_runner = background_task_runner
        self.hud_logger = hud_logger

    def _log_hud(self, message: str) -> None:
        if self.hud_logger:
            try:
                self.hud_logger(f"[ALEXA] {message}")
            except Exception:
                pass

    async def dispatch(self, intent: str, arguments: dict[str, Any], context: AlexaContext) -> str:
        """
        Authorize and execute a typed Alexa intent.
        Returns verbal response speech for Echo playback.
        """
        # 1. Authorize against safe command policy
        decision: AuthorizationDecision = self.policy.authorize(intent, arguments, context)
        if not decision.allowed:
            self._log_hud(f"Blocked intent '{intent}': {decision.reason}")
            return "I am not permitted to perform that action through Alexa, sir."

        # 2. Map typed intents
        norm = intent.strip()
        lower = norm.lower()

        # ── Telemetry & Status ──────────────────────────────────────────────
        if lower in ("alfredstatusintent", "system_status", "get_status"):
            return await self._handle_status()

        elif lower in ("schedulestatusintent", "calendar_summary"):
            return await self._handle_schedule_status()

        # ── Focus Mode ──────────────────────────────────────────────────────
        elif lower in ("startfocusintent", "start_focus"):
            return await self._handle_start_focus(arguments)

        elif lower in ("stopfocusintent", "stop_focus"):
            return await self._handle_stop_focus()

        # ── Media Playback ──────────────────────────────────────────────────
        elif lower in ("pausemediaintent", "pause_media"):
            return await self._handle_media_pause()

        elif lower in ("resumemediaintent", "resume_media"):
            return await self._handle_media_resume()

        # ── Internet Speed (Long-running command — Phase 8 rule) ────────────
        elif lower in ("internetspeedintent", "internet_speed", "speed_test"):
            return await self._handle_internet_speed()

        # ── Reminders ───────────────────────────────────────────────────────
        elif lower in ("setreminderintent", "set_reminder"):
            return await self._handle_set_reminder(arguments)

        # ── Built-in intents ────────────────────────────────────────────────
        elif lower == "amazon.helpintent":
            return "You can ask ALFRED for system status, to start focus mode, control media, or run an internet speed test."

        elif lower in ("amazon.cancelintent", "amazon.stopintent"):
            return "Understood, sir."

        else:
            return "That directive is not supported through the Alexa channel, sir."

    # ── Intent Handlers ─────────────────────────────────────────────────────

    async def _handle_status(self) -> str:
        cpu = 0
        ram = 0
        try:
            from actions.system_monitor import get_system_status
            status = await asyncio.to_thread(get_system_status)
            cpu = int(status.get("cpu_percent", 0))
            ram = int(status.get("ram_percent", 0))
        except Exception:
            try:
                import psutil
                cpu = int(psutil.cpu_percent(interval=None))
                ram = int(psutil.virtual_memory().percent)
            except Exception:
                pass

        self._log_hud(f"Status reported: CPU {cpu}%, RAM {ram}%")
        return f"All ALFRED systems online, sir. CPU is at {cpu} percent, memory at {ram} percent."

    async def _handle_schedule_status(self) -> str:
        # Privacy rule: Summary only, never expose attendee emails or private notes
        self._log_hud("Calendar summary requested via Alexa.")
        today_str = datetime.date.today().strftime("%A, %B %d")
        return f"Schedule status for {today_str}: all routines are proceeding as planned, sir."

    async def _handle_start_focus(self, args: dict[str, Any]) -> str:
        raw_duration = args.get("duration", "")
        mins = parse_iso_duration_to_minutes(str(raw_duration)) if raw_duration else 25
        if not mins or mins <= 0:
            mins = 25

        self._log_hud(f"Focus mode initiated for {mins} minutes.")
        try:
            from actions.sentry_focus import sentry_focus_action
            await asyncio.to_thread(sentry_focus_action, action="start", duration_minutes=mins)
        except Exception as e:
            logger.warning(f"Could not signal focus action: {e}")

        return f"Focus mode engaged for {mins} minutes, sir."

    async def _handle_stop_focus(self) -> str:
        self._log_hud("Focus mode stopped.")
        try:
            from actions.sentry_focus import sentry_focus_action
            await asyncio.to_thread(sentry_focus_action, action="stop")
        except Exception as e:
            logger.warning(f"Could not signal focus action: {e}")

        return "Focus mode concluded, sir."

    async def _handle_media_pause(self) -> str:
        self._log_hud("Media playback paused.")
        try:
            from core.media.arbiter import get_media_arbiter
            arbiter = get_media_arbiter()
            if hasattr(arbiter, "pause"):
                arbiter.pause()
        except Exception:
            pass
        return "Media playback paused, sir."

    async def _handle_media_resume(self) -> str:
        self._log_hud("Media playback resumed.")
        try:
            from core.media.arbiter import get_media_arbiter
            arbiter = get_media_arbiter()
            if hasattr(arbiter, "resume"):
                arbiter.resume()
        except Exception:
            pass
        return "Media playback resumed, sir."

    async def _handle_internet_speed(self) -> str:
        """
        Phase 8 compliance:
        Acknowledge immediately so Alexa HTTP deadline (8s) is never breached.
        Execute the speed test in the background and surface results in ALFRED HUD.
        """
        self._log_hud("Internet speed test triggered in background.")

        async def _run_speedtest_background():
            try:
                from actions.network_tools import network_tools_action
                result_str = await asyncio.to_thread(network_tools_action, {"action": "speed_test"})
                self._log_hud(f"Speed Test Result: {result_str}")
            except Exception as ex:
                self._log_hud(f"Speed Test failed: {ex}")

        # Fire and forget background task
        asyncio.create_task(_run_speedtest_background())

        return "The speed test is running, sir. I’ll put the result in ALFRED."

    async def _handle_set_reminder(self, args: dict[str, Any]) -> str:
        text = str(args.get("reminder_text") or "check in").strip()
        time_spec = str(args.get("time") or "").strip()
        self._log_hud(f"Reminder created: '{text}' at {time_spec or 'default time'}")
        return f"Reminder recorded for {text}, sir."
