"""Monitor Controller: Orchestrates AnswerWindow, MonitorScheduler, and SentryModeManager."""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any, Callable

from core.sentry.answer_window import AnswerWindow, ANSWER_WINDOW_S
from core.sentry.mode_manager import get_sentry_mode_manager
from core.sentry.monitor.parser import parse_monitoring_request
from core.sentry.monitor.scheduler import (
    MonitorScheduler,
    MONITOR_ALERT_COOLDOWN_S,
    MONITOR_DEFAULT_INTERVAL_S,
)

# ── Named Constants ──────────────────────────────────────────────────────────
DEFAULT_PROMPT: str = "What shall I keep an eye on, sir?"
FOLLOW_UP_PROMPT: str = "Shall I keep watching, sir?"
ALERT_PREFIX: str = "Sir, "

_LOGGER = logging.getLogger(__name__)


class MonitorController:
    """High-level controller coordinating answer windows, target scheduling, and mode state."""

    _instance: MonitorController | None = None
    _instance_lock = threading.Lock()

    @classmethod
    def instance(cls) -> MonitorController:
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(
        self,
        speak_fn: Callable[[str], None] | None = None,
        un_gate_fn: Callable[[bool], None] | None = None,
        status_fn: Callable[[str], None] | None = None,
        loop_provider: Callable[[], asyncio.AbstractEventLoop | None] | None = None,
    ) -> None:
        self._speak_fn = speak_fn
        self._un_gate_fn = un_gate_fn
        self._status_fn = status_fn
        self._loop_provider = loop_provider

        self.answer_window = AnswerWindow(
            speak_fn=self._speak,
            un_gate_fn=self._un_gate,
        )
        self.scheduler = MonitorScheduler(
            on_alert=self._on_scheduler_alert,
            on_status=self._on_scheduler_status,
            on_follow_up=self._on_scheduler_follow_up,
        )
        self._lock = threading.Lock()
        self._async_task: asyncio.Task[Any] | None = None

    @property
    def is_waiting_for_answer(self) -> bool:
        return self.answer_window.is_active

    def set_callbacks(
        self,
        speak_fn: Callable[[str], None] | None = None,
        un_gate_fn: Callable[[bool], None] | None = None,
        status_fn: Callable[[str], None] | None = None,
        loop_provider: Callable[[], asyncio.AbstractEventLoop | None] | None = None,
    ) -> None:
        with self._lock:
            if speak_fn is not None:
                self._speak_fn = speak_fn
            if un_gate_fn is not None:
                self._un_gate_fn = un_gate_fn
            if status_fn is not None:
                self._status_fn = status_fn
            if loop_provider is not None:
                self._loop_provider = loop_provider

        self.answer_window.set_callbacks(
            speak_fn=self._speak,
            un_gate_fn=self._un_gate,
        )

    # ── Spoken and Audio I/O ──────────────────────────────────────────────────

    def _speak(self, text: str) -> None:
        with self._lock:
            fn = self._speak_fn
        if fn:
            try:
                fn(text)
            except Exception as exc:
                _LOGGER.warning("Error speaking monitor message: %s", exc)

    def _un_gate(self, active: bool) -> None:
        with self._lock:
            fn = self._un_gate_fn
        if fn:
            try:
                fn(active)
            except Exception as exc:
                _LOGGER.debug("Error un-gating mic: %s", exc)

    def _update_status(self, text: str) -> None:
        with self._lock:
            fn = self._status_fn
        if fn:
            try:
                fn(text)
            except Exception:
                pass

    # ── Answer Window Submission ──────────────────────────────────────────────

    def submit_answer(self, text: str) -> bool:
        """Feed captured transcript/text into the waiting answer window."""
        return self.answer_window.submit_answer(text)

    # ── Lifecycle Orchestration ───────────────────────────────────────────────

    def start(
        self,
        goal: str = "",
        interval_seconds: float = MONITOR_DEFAULT_INTERVAL_S,
    ) -> dict[str, Any]:
        """Start monitoring. If goal is empty, prompt user via AnswerWindow."""
        goal_cleaned = (goal or "").strip()

        if goal_cleaned:
            # Immediate target parsing
            targets = parse_monitoring_request(goal_cleaned)
            for t in targets:
                t.interval_s = max(1.0, interval_seconds)
                self.scheduler.add_target(t)

            self.scheduler.start()
            label = goal_cleaned[:40]
            mgr = get_sentry_mode_manager()
            mgr.update_monitor_state(
                active=True,
                target_count=self.scheduler.target_count,
                label=label,
            )
            self._update_status(f"Monitoring: {label}")
            return {
                "active": True,
                "target_count": len(targets),
                "label": label,
            }

        # No target given -> Open answer window and ask
        self._spawn_prompt_flow(interval_seconds)
        return {
            "active": True,
            "target_count": 0,
            "label": "Awaiting target...",
        }

    def stop(self, reason: str = "Stopped by user.") -> dict[str, Any]:
        """Stop monitoring and cancel any active answer window."""
        self.answer_window.cancel()
        self.scheduler.stop()

        mgr = get_sentry_mode_manager()
        mgr.update_monitor_state(
            active=False,
            target_count=0,
            label=reason,
        )
        self._update_status("Monitoring off")
        return {
            "active": False,
            "target_count": 0,
            "label": reason,
        }

    def status(self) -> dict[str, Any]:
        """Return current monitoring status snapshot."""
        return {
            "active": self.scheduler.is_running,
            "target_count": self.scheduler.target_count,
            "cooldown": self.scheduler.cooldown,
            "description": self.scheduler.describe_active(),
            "waiting_for_answer": self.answer_window.is_active,
        }

    # ── Spoken Voice Controls ─────────────────────────────────────────────────

    def what_are_you_monitoring(self) -> str:
        return self.scheduler.describe_active()

    def remove_target(self, target_name: str) -> str:
        if not target_name:
            self.stop("Stopped by command.")
            return "Monitoring stopped, sir."

        removed = self.scheduler.remove_target(target_name)
        mgr = get_sentry_mode_manager()
        mgr.update_monitor_state(
            active=self.scheduler.target_count > 0,
            target_count=self.scheduler.target_count,
        )
        if removed:
            if self.scheduler.target_count == 0:
                self.scheduler.stop()
                return f"Target '{target_name}' removed. No active targets remaining, sir."
            return f"Target '{target_name}' removed, sir. {self.scheduler.describe_active()}"
        return f"Could not find target '{target_name}', sir."

    def quieter(self) -> str:
        new_cd = self.scheduler.quieter()
        msg = f"Alert cooldown increased to {new_cd:g} seconds, sir."
        self._update_status(msg)
        return msg

    def louder(self) -> str:
        new_cd = self.scheduler.louder()
        msg = f"Alert cooldown decreased to {new_cd:g} seconds, sir."
        self._update_status(msg)
        return msg

    # ── Background Flows ──────────────────────────────────────────────────────

    def _spawn_prompt_flow(self, interval_seconds: float) -> None:
        loop = None
        if self._loop_provider:
            try:
                loop = self._loop_provider()
            except Exception:
                loop = None

        if loop is not None and loop.is_running():
            asyncio.run_coroutine_threadsafe(self._async_prompt_flow(interval_seconds), loop)
        else:
            threading.Thread(
                target=lambda: asyncio.run(self._async_prompt_flow(interval_seconds)),
                name="sentry-prompt-worker",
                daemon=True,
            ).start()

    async def _async_prompt_flow(self, interval_seconds: float) -> None:
        self._update_status("Asking what to monitor...")
        answer = await self.answer_window.request_answer(
            prompt_speech=DEFAULT_PROMPT,
            timeout_s=ANSWER_WINDOW_S,
        )

        if not answer:
            self.stop("No target specified.")
            self._speak("Monitoring cancelled, sir. No target was specified.")
            return

        targets = parse_monitoring_request(answer)
        for t in targets:
            t.interval_s = max(1.0, interval_seconds)
            self.scheduler.add_target(t)

        self.scheduler.start()
        label = answer[:40]
        mgr = get_sentry_mode_manager()
        mgr.update_monitor_state(
            active=True,
            target_count=len(targets),
            label=label,
        )
        desc = ", ".join(t.describe() for t in targets)
        self._speak(f"Understood, sir. Monitoring {desc}.")

    def _spawn_follow_up_flow(self) -> None:
        loop = None
        if self._loop_provider:
            try:
                loop = self._loop_provider()
            except Exception:
                loop = None

        if loop is not None and loop.is_running():
            asyncio.run_coroutine_threadsafe(self._async_follow_up_flow(), loop)
        else:
            threading.Thread(
                target=lambda: asyncio.run(self._async_follow_up_flow()),
                name="sentry-followup-worker",
                daemon=True,
            ).start()

    async def _async_follow_up_flow(self) -> None:
        self._update_status("Task completed. Following up...")
        answer = await self.answer_window.request_answer(
            prompt_speech=FOLLOW_UP_PROMPT,
            timeout_s=ANSWER_WINDOW_S,
        )

        low = (answer or "").lower().strip()
        if not low or any(neg in low for neg in ("no", "stop", "all done", "that's all", "finished")):
            self.stop("Monitoring completed.")
            self._speak("Very well, sir. Monitoring concluded.")
            return

        targets = parse_monitoring_request(answer)
        for t in targets:
            self.scheduler.add_target(t)

        self.scheduler.start()
        desc = ", ".join(t.describe() for t in targets)
        self._speak(f"Continuing to watch, sir: {desc}.")

    # ── Scheduler Callbacks ───────────────────────────────────────────────────

    def _on_scheduler_alert(self, message: str) -> None:
        spoken = f"{ALERT_PREFIX}{message}"
        self._speak(spoken)
        self._update_status(f"Alert: {message}")

    def _on_scheduler_status(self, text: str) -> None:
        self._update_status(text)

    def _on_scheduler_follow_up(self) -> None:
        self._spawn_follow_up_flow()


def get_monitor_controller() -> MonitorController:
    return MonitorController.instance()
