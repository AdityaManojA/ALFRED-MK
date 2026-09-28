"""Focused tests for the reusable continuous screen monitoring backend."""
from __future__ import annotations

import sys
import threading
import time
import unittest
from io import BytesIO
from pathlib import Path

from PIL import Image


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from actions.screen_monitor import AnalysisResult, ScreenMonitorController


def _wait_until(predicate, timeout: float = 1.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


def _jpeg_frame(color: tuple[int, int, int]) -> bytes:
    output = BytesIO()
    Image.new("RGB", (64, 64), color).save(output, format="JPEG", quality=80)
    return output.getvalue()


class TestScreenMonitorController(unittest.TestCase):
    def tearDown(self) -> None:
        controller = getattr(self, "controller", None)
        if controller is not None:
            controller.stop(timeout=1.0)

    def test_start_stop_status_and_latest_observation_only(self):
        capture_count = 0

        def capture():
            nonlocal capture_count
            capture_count += 1
            return (
                f"frame-{capture_count}".encode("ascii"),
                "image/jpeg",
                f"[WINDOW_CONTEXT] App: IDE | Title: Run {capture_count} | Monitor: 1",
            )

        self.controller = ScreenMonitorController(
            capture=capture,
            analyze=lambda *_: AnalysisResult(),
            interval_seconds=0.01,
        )

        self.assertTrue(self.controller.start("Watch the IDE"))
        self.assertFalse(self.controller.start("Duplicate run"))
        self.assertTrue(_wait_until(lambda: self.controller.status().capture_count >= 3))

        running = self.controller.status()
        self.assertTrue(running.active)
        self.assertEqual(running.goal, "Watch the IDE")
        self.assertEqual(
            running.latest_observation.image_bytes,
            f"frame-{running.capture_count}".encode("ascii"),
        )

        self.assertTrue(self.controller.stop(timeout=1.0))
        stopped = self.controller.status()
        self.assertFalse(stopped.active)
        self.assertEqual(stopped.stopped_reason, "stopped")
        self.assertFalse(self.controller.stop())

    def test_polls_until_stopped_and_interval_is_configurable(self):
        captured = threading.Event()
        calls = 0

        def capture():
            nonlocal calls
            calls += 1
            if calls >= 2:
                captured.set()
            return (
                b"frame",
                "image/jpeg",
                "[WINDOW_CONTEXT] App: IDE | Title: Busy | Monitor: 1",
            )

        self.controller = ScreenMonitorController(capture=capture, analyze=lambda *_: None)
        self.assertTrue(self.controller.start("Wait", interval_seconds=0.01))
        self.assertTrue(captured.wait(1.0))
        self.controller.stop(timeout=1.0)
        calls_after_stop = calls
        time.sleep(0.03)

        self.assertEqual(calls, calls_after_stop)
        self.assertEqual(self.controller.status().interval_seconds, 0.01)

    def test_stops_after_three_consecutive_capture_failures(self):
        attempts = 0
        stopped = []

        def failing_capture():
            nonlocal attempts
            attempts += 1
            raise RuntimeError("screen unavailable")

        self.controller = ScreenMonitorController(
            capture=failing_capture,
            analyze=lambda *_: None,
            on_stopped=stopped.append,
            interval_seconds=0.005,
        )
        self.controller.start("Watch")

        self.assertTrue(_wait_until(lambda: len(stopped) == 1))
        status = self.controller.status()
        self.assertEqual(attempts, 3)
        self.assertEqual(status.consecutive_failures, 3)
        self.assertEqual(status.stopped_reason, "capture_failures")
        self.assertIn("screen unavailable", status.last_error)
        self.assertEqual(len(stopped), 1)
        self.assertFalse(stopped[0].active)
        self.assertEqual(stopped[0].stopped_reason, "capture_failures")

    def test_success_resets_consecutive_capture_failures(self):
        outcomes = iter(
            [
                RuntimeError("one"),
                (b"ok", "image/jpeg", "ctx"),
                RuntimeError("two"),
                RuntimeError("three"),
                RuntimeError("four"),
            ]
        )

        def capture():
            outcome = next(outcomes)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        self.controller = ScreenMonitorController(
            capture=capture,
            analyze=lambda *_: None,
            interval_seconds=0.005,
        )
        self.controller.start("Watch")

        self.assertTrue(_wait_until(lambda: not self.controller.status().active))
        status = self.controller.status()
        self.assertEqual(status.capture_count, 1)
        self.assertEqual(status.consecutive_failures, 3)
        self.assertIn("four", status.last_error)

    def test_meaningful_state_is_deduplicated(self):
        events = []

        self.controller = ScreenMonitorController(
            capture=lambda: (b"same", "image/jpeg", "same-context"),
            analyze=lambda *_: AnalysisResult(
                meaningful_change=True,
                summary="still working",
                event_key="working",
            ),
            on_meaningful_state=events.append,
            interval_seconds=0.005,
        )
        self.controller.start("Watch")

        self.assertTrue(_wait_until(lambda: self.controller.status().capture_count >= 3))
        self.controller.stop(timeout=1.0)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].analysis.summary, "still working")

    def test_default_analysis_detects_visual_change_with_constant_context(self):
        frames = iter(
            [
                _jpeg_frame((0, 0, 0)),
                _jpeg_frame((255, 255, 255)),
                _jpeg_frame((255, 255, 255)),
            ]
        )
        last_frame = _jpeg_frame((255, 255, 255))
        events = []

        def capture():
            try:
                frame = next(frames)
            except StopIteration:
                frame = last_frame
            return frame, "image/jpeg", "[WINDOW_CONTEXT] App: IDE | Title: Task"

        self.controller = ScreenMonitorController(
            capture=capture,
            on_meaningful_state=events.append,
            interval_seconds=0.005,
        )
        self.controller.start("Watch Antigravity")

        self.assertTrue(_wait_until(lambda: self.controller.status().capture_count >= 3))
        self.controller.stop(timeout=1.0)
        visual_events = [
            event
            for event in events
            if event.analysis.summary == "Visual frame changed."
        ]
        self.assertEqual(len(visual_events), 1)
        self.assertEqual(
            visual_events[0].observation.window_context,
            "[WINDOW_CONTEXT] App: IDE | Title: Task",
        )

    def test_completion_callback_fires_once_and_stops(self):
        completions = []
        stopped = []

        self.controller = ScreenMonitorController(
            capture=lambda: (b"done", "image/jpeg", "task complete"),
            analyze=lambda *_: {
                "meaningful_change": True,
                "completed": True,
                "summary": "Task completed",
            },
            on_completion=completions.append,
            on_stopped=stopped.append,
            interval_seconds=0.005,
        )
        self.controller.start("Tell me when the task completes")

        self.assertTrue(_wait_until(lambda: len(stopped) == 1))
        status = self.controller.status()
        self.assertEqual(len(completions), 1)
        self.assertEqual(status.capture_count, 1)
        self.assertEqual(status.stopped_reason, "completed")
        self.assertEqual(len(stopped), 1)
        self.assertFalse(stopped[0].active)
        self.assertTrue(stopped[0].completed)
        self.assertEqual(stopped[0].stopped_reason, "completed")

    def test_callback_exception_does_not_stop_monitoring(self):
        callback_called = threading.Event()

        def broken_callback(_event):
            callback_called.set()
            raise RuntimeError("consumer failed")

        self.controller = ScreenMonitorController(
            capture=lambda: (b"frame", "image/jpeg", "ctx"),
            analyze=lambda *_: AnalysisResult(
                meaningful_change=True,
                event_key="once",
            ),
            on_meaningful_state=broken_callback,
            interval_seconds=0.005,
        )
        self.controller.start("Watch")

        self.assertTrue(callback_called.wait(1.0))
        self.assertTrue(_wait_until(lambda: self.controller.status().capture_count >= 2))
        self.assertTrue(self.controller.status().active)


if __name__ == "__main__":
    unittest.main()
