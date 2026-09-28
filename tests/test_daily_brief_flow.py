import asyncio
import threading
import time
import unittest
from unittest.mock import AsyncMock, patch

from actions import background_monitor as monitor_module
from actions import daily_brief as daily_brief_module
import main as main_module


class DailyBriefPerformanceTests(unittest.TestCase):
    def test_independent_brief_sections_run_concurrently(self):
        active = 0
        max_active = 0
        lock = threading.Lock()

        def section(value):
            def run(*_args):
                nonlocal active, max_active
                with lock:
                    active += 1
                    max_active = max(max_active, active)
                time.sleep(0.05)
                with lock:
                    active -= 1
                return value
            return run

        memory = {
            "identity": {"city": {"value": "Indore"}},
            "preferences": {"briefing_preference": {"value": "AI"}},
        }
        with (
            patch.object(daily_brief_module, "_get_live_weather", section("weather")),
            patch.object(daily_brief_module, "_get_gmail_brief", section("mail")),
            patch.object(daily_brief_module, "_get_reminders_brief", section("reminders")),
            patch.object(daily_brief_module, "_get_system_vitals", section("vitals")),
            patch("memory.memory_manager.load_memory", return_value=memory),
            patch("actions.web_search._news", section("Latest news: AI\n1. Headline")),
        ):
            result = daily_brief_module.daily_brief({})

        self.assertGreaterEqual(max_active, 3)
        self.assertIn("weather", result)
        self.assertIn("1. Headline", result)

    def test_monitored_topics_are_fetched_concurrently(self):
        active = 0
        max_active = 0
        lock = threading.Lock()

        def fetch(topic, max_results=5):
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.05)
            with lock:
                active -= 1
            return [{"title": f"{topic} headline", "snippet": "", "source": "test"}]

        monitors = {
            f"topic_{index}": {
                "topic": f"topic {index}",
                "last_check": "",
                "last_hash": "",
            }
            for index in range(4)
        }
        with (
            patch.object(monitor_module, "_load", return_value=monitors),
            patch.object(monitor_module, "_save") as save,
            patch("actions.web_search._ddg_news", side_effect=fetch),
        ):
            alerts = monitor_module.check_all()

        self.assertGreaterEqual(max_active, 3)
        self.assertEqual(len(alerts), 4)
        save.assert_called_once()


class StartupBriefTests(unittest.IsolatedAsyncioTestCase):
    async def test_startup_brief_is_sent_as_one_prompt(self):
        app = main_module.JarvisLive.__new__(main_module.JarvisLive)
        app._briefing_cancelled = False
        app._interrupted = False
        app._last_user_speech = time.monotonic() - 10
        app.session = object()
        app.ui = unittest.mock.Mock()
        app._dashboard = None
        app._send_proactive_prompt = AsyncMock(return_value=True)

        memory = {
            "identity": {"name": {"value": "Aditya"}, "language": {"value": "English"}},
            "preferences": {"briefing_preference": {"value": "AI"}},
        }
        with (
            patch.object(main_module, "load_memory", return_value=memory),
            patch.object(main_module, "pop_last_session", return_value=None),
            patch.object(main_module, "_fetch_news_sync", return_value="1. A useful headline"),
        ):
            await app._send_startup_briefing()

        app._send_proactive_prompt.assert_awaited_once()
        prompt = app._send_proactive_prompt.await_args.args[0]
        self.assertIn("ONE continuous", prompt)
        self.assertIn("A useful headline", prompt)
        app.ui.show_content.assert_called_once()


if __name__ == "__main__":
    unittest.main()
