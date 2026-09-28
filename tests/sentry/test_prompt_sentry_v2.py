import os
import unittest
from pathlib import Path


class TestPromptSentryV2(unittest.TestCase):
    def setUp(self):
        repo_root = Path(__file__).resolve().parent.parent.parent
        self.prompt_path = repo_root / "core" / "prompt.txt"
        self.assertTrue(self.prompt_path.exists(), f"Prompt file not found at {self.prompt_path}")
        with open(self.prompt_path, "r", encoding="utf-8") as f:
            self.prompt_text = f.read()

    def test_sentry_section_exists(self):
        """Prompt must contain dedicated SENTRY MODE: MONITOR + FOCUS section."""
        self.assertIn("[SENTRY MODE: MONITOR + FOCUS]", self.prompt_text)

    def test_dual_mode_documentation(self):
        """Prompt must document both MONITOR MODE and FOCUS MODE."""
        self.assertIn("MONITOR MODE", self.prompt_text)
        self.assertIn("FOCUS MODE", self.prompt_text)

    def test_tool_names_present(self):
        """Prompt must teach the model the exact tool names: sentry_monitor and sentry_focus."""
        self.assertIn("sentry_monitor", self.prompt_text)
        self.assertIn("sentry_focus", self.prompt_text)

    def test_voice_intents_documented(self):
        """Prompt must map representative voice phrases to appropriate modes."""
        phrases = [
            "watch this terminal",
            "keep an eye on this build",
            "watch the screen until it's done",
            "focus on this tab",
            "lock me in",
            "lock on this tab",
            "drill sergeant",
            "snooze",
            "extend",
            "excuse",
        ]
        for phrase in phrases:
            self.assertIn(phrase, self.prompt_text, f"Voice intent '{phrase}' missing from prompt")

    def test_structural_privacy_law_documented(self):
        """Prompt must explicitly enforce structural privacy laws for Focus Mode."""
        self.assertIn("CRITICAL PRIVACY LAW FOR FOCUS MODE", self.prompt_text)
        self.assertIn("NEVER ask the user for their tab URL", self.prompt_text)
        self.assertIn("FocusState contains only booleans and numerical counters", self.prompt_text)


if __name__ == "__main__":
    unittest.main()
