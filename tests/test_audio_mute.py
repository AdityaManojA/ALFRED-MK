"""
tests/test_audio_mute.py — Unit tests for Phase 5 System Microphone Mute and "Mute Me" Intent.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from core.audio.mute import (
    MUTE_CONFIRMATION_SPEECH,
    execute_mute_me,
    is_microphone_muted,
    mute_system_microphone,
    unmute_system_microphone,
)
from core.intents.router import IntentRouter
from actions.computer_settings import _detect_action


class TestAudioMute(unittest.TestCase):

    def test_mute_confirmation_speech_constant(self):
        self.assertEqual(
            MUTE_CONFIRMATION_SPEECH,
            "Microphone muted, sir. You will need to unmute manually to speak to me again.",
        )

    @patch("platform.system", return_value="Windows")
    def test_mute_system_microphone_windows(self, mock_sys):
        mock_mic = MagicMock()
        mock_vol = MagicMock()
        mock_mic.Activate.return_value = mock_vol

        with patch("pycaw.pycaw.AudioUtilities.GetMicrophone", return_value=mock_mic):
            ok = mute_system_microphone()
            self.assertTrue(ok)
            mock_vol.SetMute.assert_called_with(1, None)

    @patch("platform.system", return_value="Windows")
    def test_unmute_system_microphone_windows(self, mock_sys):
        mock_mic = MagicMock()
        mock_vol = MagicMock()
        mock_mic.Activate.return_value = mock_vol

        with patch("pycaw.pycaw.AudioUtilities.GetMicrophone", return_value=mock_mic):
            ok = unmute_system_microphone()
            self.assertTrue(ok)
            mock_vol.SetMute.assert_called_with(0, None)

    @patch("platform.system", return_value="Linux")
    @patch("subprocess.run")
    def test_mute_system_microphone_linux(self, mock_subproc, mock_sys):
        mock_subproc.return_value = MagicMock(returncode=0)
        ok = mute_system_microphone()
        self.assertTrue(ok)
        mock_subproc.assert_called_with(
            ["pactl", "set-source-mute", "@DEFAULT_SOURCE@", "1"],
            capture_output=True,
            timeout=2,
        )

    @patch("platform.system", return_value="Darwin")
    @patch("subprocess.run")
    def test_mute_system_microphone_mac(self, mock_subproc, mock_sys):
        mock_subproc.return_value = MagicMock(returncode=0)
        ok = mute_system_microphone()
        self.assertTrue(ok)
        mock_subproc.assert_called_with(
            ["osascript", "-e", "set volume input volume 0"],
            capture_output=True,
            timeout=2,
        )

    @patch("core.audio.mute.mute_system_microphone")
    def test_execute_mute_me_speaks_and_mutes(self, mock_mute):
        mock_speak = MagicMock()
        res = execute_mute_me(speak_fn=mock_speak)
        self.assertEqual(res, MUTE_CONFIRMATION_SPEECH)
        mock_speak.assert_called_once_with(MUTE_CONFIRMATION_SPEECH)
        mock_mute.assert_called_once()

    def test_intent_router_mute_me_fast_path(self):
        router = IntentRouter()
        for phrase in ["mute me", "mute my mic", "mute microphone", "mute the microphone"]:
            match = router.route(phrase)
            self.assertIsNotNone(match, f"Phrase '{phrase}' failed to match fast-path")
            self.assertEqual(match.intent_name, "mute_me")
            self.assertEqual(match.action_name, "mute_system_microphone")

    def test_computer_settings_action_aliases(self):
        for phrase in ["mute me", "mute my mic", "mute microphone", "mute mic"]:
            act = _detect_action(phrase)
            self.assertIn(act.get("action"), ("mute_mic", "mute_me", "mute_microphone"))


if __name__ == "__main__":
    unittest.main()
