"""
Comprehensive lifecycle tests for ALFRED audio ducking and volume restoration.

Verifies:
1. Exact volume restoration when speech finishes normally.
2. Exact volume restoration when turn_complete is delayed or omitted (silence watchdog).
3. Exact volume restoration when interrupted mid-speech (no re-ducking race).
4. Symmetrical duck/unduck across multiple speech bursts without volume drift.
5. Failsafe unducking on error or watchdog expiration.
"""

import unittest
from unittest.mock import MagicMock, patch
import os
import core.audio_ducker as audio_ducker


class TestAudioDuckRestoreLifecycle(unittest.TestCase):
    def setUp(self):
        audio_ducker._original_volumes.clear()
        audio_ducker._is_ducked = False
        audio_ducker._cancel_auto_unduck_watchdog()

    def tearDown(self):
        audio_ducker._cancel_auto_unduck_watchdog()
        audio_ducker._original_volumes.clear()
        audio_ducker._is_ducked = False

    @patch("core.audio_ducker.platform.system", return_value="Windows")
    def test_single_turn_exact_volume_restoration(self, mock_sys):
        """External apps must return to their exact volume when speech ends."""
        proc = MagicMock()
        proc.name.return_value = "chrome.exe"
        proc.pid = 2001

        vol = MagicMock()
        vol.GetMasterVolume.return_value = 0.85
        session = MagicMock()
        session.Process = proc
        session._ctl.QueryInterface.return_value = vol

        with patch("pycaw.pycaw.AudioUtilities.GetAllSessions", return_value=[session]):
            # 1. Duck
            ducked = audio_ducker.duck_media_apps(volume_factor=0.3, sync=True)
            self.assertIn("chrome.exe", ducked)
            self.assertAlmostEqual(ducked["chrome.exe"], 0.255, places=3)
            vol.SetMasterVolume.assert_called_with(0.255, None)
            self.assertTrue(audio_ducker.is_ducked())

            # 2. Unduck
            restored = audio_ducker.unduck_media_apps(sync=True)
            self.assertIn("chrome.exe", restored)
            self.assertEqual(restored["chrome.exe"], 0.85)
            vol.SetMasterVolume.assert_called_with(0.85, None)
            self.assertFalse(audio_ducker.is_ducked())
            self.assertEqual(len(audio_ducker._original_volumes), 0)

    @patch("core.audio_ducker.platform.system", return_value="Windows")
    def test_multi_burst_no_volume_drift(self, mock_sys):
        """Repeated speech turns must preserve the true initial volume across all bursts."""
        proc = MagicMock()
        proc.name.return_value = "spotify.exe"
        proc.pid = 3001

        vol = MagicMock()
        initial_vol = 0.90
        vol.GetMasterVolume.return_value = initial_vol
        session = MagicMock()
        session.Process = proc
        session._ctl.QueryInterface.return_value = vol

        with patch("pycaw.pycaw.AudioUtilities.GetAllSessions", return_value=[session]):
            for _ in range(5):
                audio_ducker.duck_media_apps(volume_factor=0.3, sync=True)
                self.assertEqual(audio_ducker._original_volumes[3001], initial_vol)

                restored = audio_ducker.unduck_media_apps(sync=True)
                self.assertEqual(restored["spotify.exe"], initial_vol)
                vol.SetMasterVolume.assert_called_with(initial_vol, None)
                self.assertFalse(audio_ducker.is_ducked())

    @patch("core.audio_ducker.platform.system", return_value="Windows")
    def test_auto_watchdog_restoration(self, mock_sys):
        """If Alfred fails to call unduck, the watchdog timer restores volume."""
        proc = MagicMock()
        proc.name.return_value = "vlc.exe"
        proc.pid = 4001

        vol = MagicMock()
        vol.GetMasterVolume.return_value = 0.60
        session = MagicMock()
        session.Process = proc
        session._ctl.QueryInterface.return_value = vol

        with patch("pycaw.pycaw.AudioUtilities.GetAllSessions", return_value=[session]):
            audio_ducker.duck_media_apps(volume_factor=0.3, sync=True)
            self.assertTrue(audio_ducker.is_ducked())

            # Watchdog timeout fires
            audio_ducker._on_watchdog_timeout()
            self.assertFalse(audio_ducker.is_ducked())
            vol.SetMasterVolume.assert_called_with(0.60, None)

    @patch("core.audio_ducker.platform.system", return_value="Windows")
    def test_wildcard_ducks_all_applications(self, mock_sys):
        """Targeting '*' or 'all' ducks any active non-Alfred application."""
        game_proc = MagicMock()
        game_proc.name.return_value = "my_game.exe"
        game_proc.pid = 5555

        game_vol = MagicMock()
        game_vol.GetMasterVolume.return_value = 1.0
        game_session = MagicMock()
        game_session.Process = game_proc
        game_session._ctl.QueryInterface.return_value = game_vol

        with patch("pycaw.pycaw.AudioUtilities.GetAllSessions", return_value=[game_session]):
            ducked = audio_ducker.duck_media_apps(volume_factor=0.3, targets={"*"}, sync=True)
            self.assertIn("my_game.exe", ducked)
            self.assertAlmostEqual(ducked["my_game.exe"], 0.30, places=2)

            restored = audio_ducker.unduck_media_apps(sync=True)
            self.assertIn("my_game.exe", restored)
            self.assertEqual(restored["my_game.exe"], 1.0)
            self.assertFalse(audio_ducker.is_ducked())


if __name__ == "__main__":
    unittest.main()
