"""Integration contracts for Sentry screen monitoring controls."""
from __future__ import annotations

import asyncio
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from actions.screen_monitor import AnalysisResult, ScreenMonitorEvent, ScreenObservation
from main import JarvisLive, TOOL_DECLARATIONS
from ui import MainWindow


class _FakeButton:
    def __init__(self) -> None:
        self.checked = False
        self.text = ""
        self.tooltip = ""

    def setChecked(self, value: bool) -> None:
        self.checked = value

    def setText(self, value: str) -> None:
        self.text = value

    def setToolTip(self, value: str) -> None:
        self.tooltip = value


class _FakeLog:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def append_log(self, message: str) -> None:
        self.messages.append(message)


class _FakeUI:
    def __init__(self) -> None:
        self.states: list[tuple[bool, str]] = []
        self.logs: list[str] = []

    def set_screen_monitor_state(self, active: bool, label: str = "") -> None:
        self.states.append((active, label))

    def write_log(self, message: str) -> None:
        self.logs.append(message)


class _FakeController:
    def __init__(self) -> None:
        self.active = False
        self.goal = None
        self.interval = 3.0
        self.capture_count = 0
        self.stopped_reason = None

    def start(self, goal: str, interval_seconds: float = 3.0) -> bool:
        if self.active:
            return False
        self.active = True
        self.goal = goal
        self.interval = interval_seconds
        return True

    def stop(self, *, wait: bool = True) -> bool:
        del wait
        was_active = self.active
        self.active = False
        self.stopped_reason = "stopped"
        return was_active

    def status(self):
        return SimpleNamespace(
            active=self.active,
            goal=self.goal,
            interval_seconds=self.interval,
            capture_count=self.capture_count,
            stopped_reason=self.stopped_reason,
        )


class _FakeSession:
    def __init__(self) -> None:
        self.turns = None

    async def send_client_content(self, *, turns, turn_complete: bool) -> None:
        self.turns = turns
        self.turn_complete = turn_complete


class TestScreenMonitorIntegration(unittest.TestCase):
    def test_tool_is_declared_for_voice_start_stop_and_status(self):
        declaration = next(tool for tool in TOOL_DECLARATIONS if tool["name"] == "screen_monitor")
        self.assertIn("stop monitoring", declaration["description"])
        self.assertEqual(declaration["parameters"]["required"], ["action"])

    def test_sentry_click_uses_monitor_callback_and_never_needs_camera(self):
        calls = []
        window = SimpleNamespace(
            on_screen_monitor_toggle=lambda enabled: calls.append(enabled) or {
                "active": enabled,
                "label": "watching" if enabled else "off",
            },
            _sentry_btn=_FakeButton(),
            _log=_FakeLog(),
        )
        window._apply_screen_monitor_state = lambda active, label="": (
            MainWindow._apply_screen_monitor_state(window, active, label)
        )

        MainWindow._toggle_sentry_mode(window, True)
        MainWindow._toggle_sentry_mode(window, False)

        self.assertEqual(calls, [True, False])
        self.assertFalse(window._sentry_btn.checked)
        self.assertEqual(window._sentry_btn.text, "[ ▣ ]  SENTRY MODE")

    def test_main_start_stop_helpers_share_one_controller(self):
        app = object.__new__(JarvisLive)
        app.ui = _FakeUI()
        app._screen_monitor = _FakeController()

        started = app._start_screen_monitor("Watch Antigravity", 0.1)
        stopped = app._stop_screen_monitor("Stopped by voice.")
        stopped_again = app._stop_screen_monitor("Stopped by voice.")

        self.assertTrue(started["active"])
        self.assertEqual(app._screen_monitor.interval, 1.0)
        self.assertTrue(stopped["stopped"])
        self.assertFalse(stopped_again["stopped"])
        self.assertFalse(stopped["active"])
        self.assertEqual(app.ui.states[-1], (False, "Screen monitoring off"))
        self.assertEqual(app.ui.logs.count("SYS: Stopped by voice."), 1)

    def test_completion_prompt_does_not_request_a_second_stop(self):
        app = object.__new__(JarvisLive)
        app._is_speaking = False
        app.session = _FakeSession()
        app._local_msg_queue = None
        event = ScreenMonitorEvent(
            goal="Notify me when the task completes.",
            observation=ScreenObservation(
                image_bytes=b"frame",
                mime_type="image/png",
                window_context="Build completed successfully",
                captured_at=datetime.now(timezone.utc),
            ),
            analysis=AnalysisResult(completed=True, summary="Build completed."),
        )

        asyncio.run(app._analyze_screen_monitor_event(event, completion_hint=True))

        prompt = app.session.turns["parts"][1]["text"]
        self.assertIn("monitoring is already stopped", prompt)
        self.assertIn("Do not call screen_monitor again", prompt)
        self.assertNotIn("action='stop'", prompt)


if __name__ == "__main__":
    unittest.main()
