"""
tests/test_alexa_skill_model.py — Unit tests for Alexa Custom Skill contract, utterances, and interaction model.
"""
import unittest

from core.integrations.alexa.skill_model import (
    TypedSkillIntent,
    export_interaction_model,
    map_utterance_to_intent,
    parse_iso_duration_to_minutes,
)


class TestAlexaSkillModel(unittest.TestCase):
    """Test suite for Custom Skill interaction model and utterance mapper."""

    def test_utterance_fixtures_mapping(self):
        cases = [
            ("what is your status", "AlfredStatusIntent", {}),
            ("status check", "AlfredStatusIntent", {}),
            ("what is on my schedule", "ScheduleStatusIntent", {}),
            ("start focus", "StartFocusIntent", {}),
            ("start focus for 25 minutes", "StartFocusIntent", {"duration": "25 minutes"}),
            ("stop focus mode", "StopFocusIntent", {}),
            ("pause the music", "PauseMediaIntent", {}),
            ("resume media", "ResumeMediaIntent", {}),
            ("what is my internet speed", "InternetSpeedIntent", {}),
            ("run a speed test", "InternetSpeedIntent", {}),
            ("set a reminder to take medicine at 5pm", "SetReminderIntent", {"reminder_text": "take medicine", "time": "5pm"}),
            ("help", "AMAZON.HelpIntent", {}),
            ("cancel", "AMAZON.CancelIntent", {}),
        ]

        for utterance, expected_intent, expected_slots in cases:
            res = map_utterance_to_intent(utterance)
            self.assertIsNotNone(res, f"Failed to map utterance: '{utterance}'")
            self.assertEqual(res.intent_name, expected_intent)
            for k, v in expected_slots.items():
                self.assertEqual(res.slots.get(k), v)

    def test_unsupported_utterance_returns_none(self):
        res = map_utterance_to_intent("tell me a long philosophical bedtime story about space")
        self.assertIsNone(res)

    def test_iso_duration_parsing(self):
        self.assertEqual(parse_iso_duration_to_minutes("PT25M"), 25)
        self.assertEqual(parse_iso_duration_to_minutes("PT1H"), 60)
        self.assertEqual(parse_iso_duration_to_minutes("PT1H30M"), 90)
        self.assertEqual(parse_iso_duration_to_minutes("25 minutes"), 25)
        self.assertEqual(parse_iso_duration_to_minutes("10 min"), 10)
        self.assertIsNone(parse_iso_duration_to_minutes("invalid"))

    def test_export_interaction_model_schema(self):
        model = export_interaction_model("alfred")
        self.assertIn("interactionModel", model)
        lang_model = model["interactionModel"]["languageModel"]
        self.assertEqual(lang_model["invocationName"], "alfred")

        intent_names = [i["name"] for i in lang_model["intents"]]
        self.assertIn("AlfredStatusIntent", intent_names)
        self.assertIn("StartFocusIntent", intent_names)
        self.assertIn("StopFocusIntent", intent_names)
        self.assertIn("ScheduleStatusIntent", intent_names)
        self.assertIn("PauseMediaIntent", intent_names)
        self.assertIn("ResumeMediaIntent", intent_names)
        self.assertIn("InternetSpeedIntent", intent_names)
        self.assertIn("SetReminderIntent", intent_names)
        self.assertIn("AMAZON.HelpIntent", intent_names)


if __name__ == "__main__":
    unittest.main()
