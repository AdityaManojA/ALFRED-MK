import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio

class TestVoiceSleep(unittest.TestCase):
    """Test suite for voice-activated sleep mode (standby without shutdown)."""

    def test_go_to_sleep_tool_declaration(self):
        """Verify go_to_sleep is declared in TOOL_DECLARATIONS with proper schema."""
        from main import TOOL_DECLARATIONS
        tools = {t["name"]: t for t in TOOL_DECLARATIONS}
        self.assertIn("go_to_sleep", tools, "go_to_sleep tool must be declared in TOOL_DECLARATIONS")
        decl = tools["go_to_sleep"]
        self.assertIn("sleep", decl["description"].lower())
        self.assertIn("wake", decl["description"].lower())
        # Parameters should be an object (no required params needed for sleep)
        self.assertEqual(decl.get("parameters", {}).get("type"), "OBJECT")

    def test_shutdown_jarvis_does_not_conflict_with_sleep(self):
        """Verify shutdown_jarvis requires confirmation and explicitly warns against sleep commands."""
        from main import TOOL_DECLARATIONS
        tools = {t["name"]: t for t in TOOL_DECLARATIONS}
        cmd_name = "shutdown_alfred" if "shutdown_alfred" in tools else "shutdown_jarvis"
        self.assertIn(cmd_name, tools)
        decl = tools[cmd_name]
        self.assertIn("confirmation", decl["parameters"]["required"])
        # Description should distinguish shutdown from sleep
        self.assertIn("sleep", decl["description"].lower())

    def test_is_sleep_command_positive_matches(self):
        """Verify diverse voice phrases correctly identify sleep directives."""
        from main import is_sleep_command

        positive_phrases = [
            "go to sleep",
            "go to sleep alfred",
            "alfred go to sleep",
            "alfred, go to sleep",
            "sleep alfred",
            "alfred sleep",
            "sleep",
            "take a nap",
            "stand down",
            "stand down alfred",
            "alfred stand down",
            "stop listening",
            "stop listening alfred",
            "alfred stop listening",
            "enter sleep mode",
            "put yourself to sleep",
            "go to sleep now, sir",
            "alfred, please go to sleep",
        ]
        for phrase in positive_phrases:
            with self.subTest(phrase=phrase):
                self.assertTrue(
                    is_sleep_command(phrase),
                    f"Phrase '{phrase}' should be recognized as a sleep command"
                )

    def test_is_sleep_command_negative_matches(self):
        """Verify non-sleep or negated phrases are rejected."""
        from main import is_sleep_command

        negative_phrases = [
            "don't go to sleep",
            "do not go to sleep",
            "why did you go to sleep",
            "how much sleep do humans need",
            "what time do you go to sleep",
            "play sleeping music",
            "what is sleep apnea",
            "shut down alfred",
            "exit the program",
            "tell me a story",
            "what is the weather today",
        ]
        for phrase in negative_phrases:
            with self.subTest(phrase=phrase):
                self.assertFalse(
                    is_sleep_command(phrase),
                    f"Phrase '{phrase}' should NOT be recognized as a sleep command"
                )

    def test_dispatch_tool_go_to_sleep(self):
        """Verify _dispatch_tool('go_to_sleep') schedules sleep without terminating."""
        from main import JarvisLive

        with patch.object(JarvisLive, "__init__", return_value=None):
            app = JarvisLive(None)
            app.ui = MagicMock()
            app._dashboard = None
            app._awake = True
            app._is_speaking = False
            app.audio_in_queue = asyncio.Queue()
            app.sleep = MagicMock()

            # Run dispatch tool
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                res = loop.run_until_complete(app._dispatch_tool("go_to_sleep", {}))
                self.assertIn("sleep", res.lower())
                # Allow background task to fire (waits up to 1.15s)
                loop.run_until_complete(asyncio.sleep(1.5))
                app.sleep.assert_called_once()
                self.assertEqual(app.sleep.call_args[1].get("reason"), "voice command")
            finally:
                loop.close()

    def test_sleep_gates_microphone_and_resets_wake(self):
        """Verify sleep() sets _awake to False, sets UI state to SLEEPING, and resets detector."""
        from main import JarvisLive

        with patch.object(JarvisLive, "__init__", return_value=None):
            app = JarvisLive(None)
            app._awake = True
            app.set_speaking = MagicMock()
            app.ui = MagicMock()
            app._wake_detector = MagicMock()
            app._dashboard = None

            app.sleep(reason="voice command")

            self.assertFalse(app._awake)
            app.ui.set_state.assert_called_with("SLEEPING")
            app._wake_detector.reset.assert_called_once()

    def test_sleep_and_wake_log_deduplication(self):
        """Verify chat notices show once on auto-silence/wake-word while processes run continuously."""
        from main import JarvisLive

        with patch.object(JarvisLive, "__init__", return_value=None):
            app = JarvisLive(None)
            app.set_speaking = MagicMock()
            app.ui = MagicMock()
            app.ui.muted = False
            app._wake_detector = MagicMock()
            app._dashboard = None
            app._has_logged_sleep = False
            app._has_logged_wake = False

            # First auto-sleep logs to chat
            app._awake = True
            app.sleep(reason="silence for 15s")
            self.assertFalse(app._awake)
            app.ui.set_state.assert_called_with("SLEEPING")
            app.ui.write_log.assert_called_once()
            self.assertIn("Sleeping — silence for 15s", app.ui.write_log.call_args[0][0])

            # Second auto-sleep: UI state and background tasks execute, but chat is NOT spammed
            app.ui.write_log.reset_mock()
            app.ui.set_state.reset_mock()
            app._awake = True
            app.sleep(reason="silence for 15s")
            self.assertFalse(app._awake)
            app.ui.set_state.assert_called_with("SLEEPING")
            app.ui.write_log.assert_not_called()

            # First wake word logs to chat
            app.wake(reason="wake word")
            self.assertTrue(app._awake)
            app.ui.set_state.assert_called_with("LISTENING")
            app.ui.write_log.assert_called_once()
            self.assertIn("Awake — wake word", app.ui.write_log.call_args[0][0])

            # Second wake word: sets state and un-gates mic, but chat is NOT spammed
            app.ui.write_log.reset_mock()
            app.ui.set_state.reset_mock()
            app._awake = False
            app.wake(reason="wake word")
            self.assertTrue(app._awake)
            app.ui.set_state.assert_called_with("LISTENING")
            app.ui.write_log.assert_not_called()

            # Manual explicit tap: logs to chat confirming user interaction
            app.ui.write_log.reset_mock()
            app.ui.set_state.reset_mock()
            app._awake = True
            app.sleep(reason="you tapped sleep")
            self.assertFalse(app._awake)
            app.ui.set_state.assert_called_with("SLEEPING")
            app.ui.write_log.assert_called_once()
            self.assertIn("you tapped sleep", app.ui.write_log.call_args[0][0])


if __name__ == "__main__":
    unittest.main()
