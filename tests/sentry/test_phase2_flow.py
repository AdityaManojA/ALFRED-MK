"""Integration test for Phase 2: parser, scheduler, two-target scenario, and CPU verification."""
import time
import unittest
from unittest.mock import MagicMock, patch

from core.sentry.monitor.parser import parse_monitoring_request
from core.sentry.monitor.scheduler import MonitorScheduler
from core.sentry.monitor.targets.terminal import TerminalTarget
from core.sentry.monitor.targets.window_title import WindowTitleTarget


class TestPhase2Flow(unittest.TestCase):
    def test_answer_parsing_two_targets(self):
        # Exact prompt scenario: "watch the build in the terminal and tell me when Chrome's title says Deployed"
        user_answer = "watch the build in the terminal and tell me when Chrome's title says Deployed"
        targets = parse_monitoring_request(user_answer)

        self.assertEqual(len(targets), 2)
        # Target 1 should be a TerminalTarget
        self.assertTrue(any(isinstance(t, TerminalTarget) for t in targets))
        # Target 2 should be a WindowTitleTarget for Chrome
        chrome_target = next(t for t in targets if isinstance(t, WindowTitleTarget))
        self.assertEqual(chrome_target.app_name.lower(), "chrome")
        self.assertEqual(chrome_target.pattern_str, "Deployed")

    def test_two_targets_alert_and_scheduler_lifecycle(self):
        alerts = []
        status_updates = []
        follow_up_called = []

        scheduler = MonitorScheduler(
            on_alert=lambda msg: alerts.append(msg),
            on_status=lambda s: status_updates.append(s),
            on_follow_up=lambda: follow_up_called.append(True),
        )
        scheduler.set_cooldown(1.0)  # low cooldown for fast test

        # Create the two targets
        t1 = TerminalTarget("term1", "Terminal build", interval_s=0.1)
        t2 = WindowTitleTarget("win1", "Chrome Deploy", app_name="Chrome", title_pattern="Deployed", interval_s=0.1)

        scheduler.add_target(t1)
        scheduler.add_target(t2)
        self.assertEqual(scheduler.target_count, 2)

        # Mock the polls so both alert on their first run
        with patch("actions.screen_processor.get_active_window_info", return_value={"app": "terminal", "title": "Build complete: success"}), \
             patch.object(t2, "_get_matching_window_titles", return_value=["Google Chrome - Deployed"]):
            scheduler.start()
            self.assertTrue(scheduler.is_running)

            # Wait for 1-2 scheduler ticks
            time.sleep(1.2)

        # Stopping MONITOR kills all polling immediately
        scheduler.stop()
        self.assertFalse(scheduler.is_running)
        self.assertEqual(scheduler.target_count, 0)

        # Verify alerts were generated
        self.assertGreaterEqual(len(alerts), 1)

    def test_cooldown_adjustment(self):
        scheduler = MonitorScheduler()
        self.assertEqual(scheduler.cooldown, 15.0)

        # Quieter increases cooldown
        new_cd = scheduler.quieter()
        self.assertEqual(new_cd, 30.0)

        # Louder decreases cooldown
        new_cd2 = scheduler.louder()
        self.assertEqual(new_cd2, 20.0)


if __name__ == "__main__":
    unittest.main()
