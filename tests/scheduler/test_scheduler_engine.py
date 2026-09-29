from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from core.scheduler import SchedulerEngine, parse_schedule
from core.scheduler.ledger import Ledger


class SchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.ledger = Ledger(Path(self.tempdir.name) / "schedule.json")
        self.spoken: list[str] = []
        self.events: list[dict] = []
        self.engine = SchedulerEngine(speak=self.spoken.append, notify=self.events.append, ledger=self.ledger)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_parser_supports_relative_clock_and_daily_phrases(self) -> None:
        now = datetime(2026, 1, 1, 9, 0)
        relative = parse_schedule("remind me to stretch in 10 minutes", now)
        daily = parse_schedule("remind me every day at 8:00 am to take medicine", now)
        self.assertEqual(datetime.fromisoformat(relative["trigger_time"]), now + timedelta(minutes=10))
        self.assertEqual(daily["recurrence"], "daily")
        self.assertEqual(daily["payload"]["message"], "take medicine")

    def test_due_reminder_is_spoken_and_acknowledgeable(self) -> None:
        task = self.engine.add("stretch", "reminder", {"message": "stretch"}, (datetime.now() - timedelta(seconds=1)).isoformat())
        self.engine.tick()
        saved = self.engine.list_tasks()[0]
        self.assertEqual(saved["status"], "done")
        self.assertTrue(self.spoken)
        self.assertTrue(self.engine.acknowledge(task["id"]))
        self.assertTrue(self.engine.list_tasks()[0]["acknowledged"])

    def test_cancelled_macro_never_reaches_input_automation(self) -> None:
        task = self.engine.add("macro", "macro", {"target_app": "missing", "paste_text": "hello"}, (datetime.now() + timedelta(seconds=5)).isoformat())
        self.engine.tick()
        self.assertTrue(self.engine.list_tasks()[0]["warned"])
        self.assertIn("Executing scheduled automation", self.spoken[0])
        self.assertTrue(self.engine.cancel(task["id"]))
        self.engine.tick(datetime.now() + timedelta(seconds=10))
        self.assertEqual(self.engine.list_tasks()[0]["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
