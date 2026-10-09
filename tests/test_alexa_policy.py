"""
tests/test_alexa_policy.py — Unit tests for Alexa safe command policy allowlist, denylist, and permissions toggles.
"""
import unittest

from core.integrations.alexa.policy import (
    AlexaActionPolicy,
    AlexaRiskLevel,
    DEFAULT_ALLOWED_INTENTS,
    EXPLICIT_DENIED_INTENTS,
)


class TestAlexaPolicy(unittest.TestCase):
    """Test suite validating AlexaActionPolicy."""

    def setUp(self):
        self.policy = AlexaActionPolicy()

    def test_default_allowed_intents(self):
        allowed_samples = [
            ("AlfredStatusIntent", {}),
            ("start_focus", {"duration_s": 1500}),
            ("stop_focus", {}),
            ("pause_media", {}),
            ("resume_media", {}),
            ("get_time", {}),
            ("get_weather", {}),
            ("InternetSpeedIntent", {}),
            ("calendar_summary", {}),
        ]
        for intent, args in allowed_samples:
            decision = self.policy.authorize(intent, args)
            self.assertTrue(decision.allowed, f"Intent {intent} should be allowed by default")
            self.assertIn(decision.risk_level, (AlexaRiskLevel.READ_ONLY, AlexaRiskLevel.REVERSIBLE))

    def test_explicit_denied_intents(self):
        denied_samples = [
            "shell",
            "terminal",
            "run_command",
            "computer_control",
            "keyboard_type",
            "mouse_click",
            "screenshot",
            "screen_monitor",
            "delete_file",
            "read_email",
            "shutdown_alfred",
            "undo",
        ]
        for intent in denied_samples:
            decision = self.policy.authorize(intent, {})
            self.assertFalse(decision.allowed, f"Dangerous intent {intent} must be rejected")
            self.assertEqual(decision.risk_level, AlexaRiskLevel.DENIED)

    def test_unknown_intent_denied(self):
        decision = self.policy.authorize("ArbitraryHackerIntent", {})
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.risk_level, AlexaRiskLevel.DENIED)

    def test_permission_toggle_disables_capability(self):
        # Focus is allowed by default
        self.assertTrue(self.policy.authorize("start_focus", {}).allowed)

        # User disables focus capability
        self.policy.set_capability_enabled("focus_mode", False)
        decision = self.policy.authorize("start_focus", {})
        self.assertFalse(decision.allowed)
        self.assertIn("disabled by the user", decision.reason)

        # User re-enables focus capability
        self.policy.set_capability_enabled("focus_mode", True)
        self.assertTrue(self.policy.authorize("start_focus", {}).allowed)

    def test_malicious_argument_injection_rejected(self):
        decision = self.policy.authorize(
            "start_focus",
            {"note": "test; powershell -Command Remove-Item -Force C:\\"}
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.risk_level, AlexaRiskLevel.DENIED)


if __name__ == "__main__":
    unittest.main()
