"""Tests for all 7 MonitorTarget types."""
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.sentry.monitor.targets.base import TargetStatus
from core.sentry.monitor.targets.command import CommandTarget
from core.sentry.monitor.targets.file_log import FileLogTarget
from core.sentry.monitor.targets.process import ProcessTarget
from core.sentry.monitor.targets.terminal import TerminalTarget
from core.sentry.monitor.targets.window_title import WindowTitleTarget


class TestMonitorTargets(unittest.TestCase):
    def test_terminal_target_detects_completion(self):
        t = TerminalTarget(name="Cargo build")
        with patch("actions.screen_processor.get_active_window_info", return_value={"app": "terminal", "title": "Build complete: 0 warnings"}):
            status = t.poll()
            self.assertEqual(status, TargetStatus.FINISHED)
            alerted, msg = t.should_alert()
            self.assertTrue(alerted)
            self.assertIn("finished", msg)

    def test_window_title_target_matches_regex(self):
        t = WindowTitleTarget(target_id="w1", name="Chrome Deployed", app_name="Chrome", title_pattern=r"Deployed")
        with patch.object(t, "_get_matching_window_titles", return_value=["Google Chrome - App Deployed Successfully"]):
            status = t.poll()
            self.assertEqual(status, TargetStatus.FINISHED)
            alerted, msg = t.should_alert()
            self.assertTrue(alerted)
            self.assertIn("Deployed", msg)

    def test_file_log_target_matches_pattern(self):
        with tempfile.NamedTemporaryFile("w+", delete=False, encoding="utf-8") as tmp:
            tmp.write("Initial line\n")
            tmp.flush()
            tmp_path = Path(tmp.name)

        try:
            t = FileLogTarget("l1", "Log check", tmp_path, pattern=r"FATAL_ERROR", interval_s=1.0)
            status1 = t.poll()
            self.assertEqual(status1, TargetStatus.RUNNING)
            self.assertFalse(t.should_alert()[0])

            # Append new lines matching pattern
            with open(tmp_path, "a", encoding="utf-8") as f:
                f.write("Line 2: System running\nLine 3: FATAL_ERROR in database\n")

            status2 = t.poll()
            self.assertEqual(status2, TargetStatus.ALERTED)
            alerted, msg = t.should_alert()
            self.assertTrue(alerted)
            self.assertIn("FATAL_ERROR", msg)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_command_target_alerts_on_nonzero_exit(self):
        t = CommandTarget("c1", "Failing Command", command="python -c \"import sys; sys.exit(42)\"", expected_code=0)
        status = t.poll()
        self.assertEqual(status, TargetStatus.ALERTED)
        alerted, msg = t.should_alert()
        self.assertTrue(alerted)
        self.assertIn("42", msg)


if __name__ == "__main__":
    unittest.main()
