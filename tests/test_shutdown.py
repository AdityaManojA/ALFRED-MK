import unittest
from unittest.mock import MagicMock, patch, AsyncMock, call
import asyncio
import os


class TestShutdown(unittest.TestCase):
    """Test suite for graceful shutdown with butler farewell speech."""

    def test_shutdown_tool_declaration(self):
        """Verify shutdown_alfred is declared with required confirmation parameter."""
        from main import TOOL_DECLARATIONS
        tools = {t["name"]: t for t in TOOL_DECLARATIONS}
        cmd_name = "shutdown_alfred" if "shutdown_alfred" in tools else "shutdown_jarvis"
        self.assertIn(cmd_name, tools)
        decl = tools[cmd_name]
        self.assertIn("confirmation", decl["parameters"]["required"])

    def test_is_shutdown_command_positive_matches(self):
        """Verify verbal directives to shut down ALFRED are recognized."""
        from main import is_shutdown_command

        positive_phrases = [
            "shut down",
            "shutdown",
            "shut down alfred",
            "shutdown alfred",
            "alfred shut down",
            "alfred shutdown",
            "alfred, shut down",
            "alfred, shutdown",
            "please shut down",
            "shut down now",
            "shut down completely",
            "quit alfred",
            "exit alfred",
            "power down alfred",
            "power down",
            "turn off alfred",
            "exit assistant",
        ]
        for phrase in positive_phrases:
            with self.subTest(phrase=phrase):
                self.assertTrue(
                    is_shutdown_command(phrase),
                    f"Phrase '{phrase}' should be recognized as a shutdown command",
                )

    def test_is_shutdown_command_negative_matches(self):
        """Verify queries, negations, or non-shutdown phrases are rejected."""
        from main import is_shutdown_command

        negative_phrases = [
            "don't shut down",
            "do not shut down",
            "never shut down",
            "why did you shut down",
            "when do you shut down",
            "how to shut down windows",
            "shut up",
            "shut the door",
            "go to sleep",
            "sleep alfred",
            "take a nap",
            "play music",
            "what is the time",
        ]
        for phrase in negative_phrases:
            with self.subTest(phrase=phrase):
                self.assertFalse(
                    is_shutdown_command(phrase),
                    f"Phrase '{phrase}' should NOT be recognized as a shutdown command",
                )

    def test_resolve_shutdown_username_fallbacks(self):
        """Verify user name resolution precedence: config -> profile -> 'sir'."""
        from main import resolve_shutdown_username

        # Case 1: Config has user_name
        with patch("memory.config_manager.get_user_name", return_value="Master Wayne"):
            self.assertEqual(resolve_shutdown_username(), "Master Wayne")

        # Case 2: Config is empty, speaker profile has name
        mock_prof = MagicMock()
        mock_prof.user_name = "Bruce"
        mock_store = MagicMock()
        mock_store.list_profiles.return_value = [mock_prof]
        with patch("memory.config_manager.get_user_name", return_value=""), \
             patch("core.speaker.profile_store.get_default_profile_store", return_value=mock_store):
            self.assertEqual(resolve_shutdown_username(), "Bruce")

        # Case 3: Both empty -> fallback to 'sir'
        mock_store_empty = MagicMock()
        mock_store_empty.list_profiles.return_value = []
        with patch("memory.config_manager.get_user_name", return_value=""), \
             patch("core.speaker.profile_store.get_default_profile_store", return_value=mock_store_empty):
            self.assertEqual(resolve_shutdown_username(), "sir")

    def test_dispatch_tool_shutdown_requires_confirmation(self):
        """Verify shutdown tool call without confirmation=True is ignored."""
        from main import JarvisLive

        with patch.object(JarvisLive, "__init__", return_value=None):
            app = JarvisLive(None)
            app.ui = MagicMock()
            app._dashboard = None

            loop = asyncio.new_event_loop()
            try:
                res = loop.run_until_complete(
                    app._dispatch_tool("shutdown_alfred", {"confirmation": False})
                )
                self.assertIn("ignored", res.lower())
                app.ui.write_log.assert_called_with("SYS: Shutdown ignored (missing explicit confirmation).")
            finally:
                loop.close()

    def test_execute_shutdown_speaks_phrase_and_exits_after(self):
        """Verify execute_shutdown speaks exact phrase and only exits after speech completes."""
        from main import JarvisLive

        execution_order = []

        def mock_speak(text):
            execution_order.append(("speak", text))

        def mock_exit(code):
            execution_order.append(("exit", code))

        with patch.object(JarvisLive, "__init__", return_value=None), \
             patch("main.resolve_shutdown_username", return_value="Master Wayne"), \
             patch("core.tts.get_engine") as mock_get_engine, \
             patch("os._exit", side_effect=mock_exit):

            mock_engine = MagicMock()
            mock_engine.speak.side_effect = mock_speak
            mock_get_engine.return_value = mock_engine

            app = JarvisLive(None)
            app.ui = MagicMock()
            app._dashboard = None
            app._screen_monitor = MagicMock()
            app.scheduler = MagicMock()
            app.session = MagicMock()
            app.audio_in_queue = asyncio.Queue()
            app.set_speaking = MagicMock()
            app._save_session_summary = AsyncMock()

            expected_phrase = "I am alfred your loyal butler , Hoping to be of service again Master Wayne , shutting down."

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(app.execute_shutdown())
            finally:
                loop.close()

            # Verify speech and exit happened in sequence
            self.assertEqual(len(execution_order), 2)
            self.assertEqual(execution_order[0], ("speak", expected_phrase))
            self.assertEqual(execution_order[1], ("exit", 0))

            # Verify UI was notified
            app.ui.write_log.assert_any_call("SYS: Shutdown requested.")
            app.ui.write_log.assert_any_call(f"ALFRED: {expected_phrase}")


if __name__ == "__main__":
    unittest.main()
