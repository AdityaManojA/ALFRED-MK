import unittest
from unittest.mock import MagicMock, patch
import os
import core.audio_ducker as audio_ducker


class TestAudioDucker(unittest.TestCase):
    def setUp(self):
        audio_ducker._original_volumes.clear()
        audio_ducker._is_ducked = False

    def tearDown(self):
        audio_ducker._original_volumes.clear()
        audio_ducker._is_ducked = False

    @patch("core.audio_ducker.platform.system", return_value="Windows")
    def test_duck_and_unduck_windows(self, mock_system):
        """
        Verify that duck_media_apps lowers target media processes by 70% (0.3 factor),
        stores original volumes, and unduck_media_apps restores exact original levels.
        """
        # Mock Spotify and Chrome audio sessions
        spotify_proc = MagicMock()
        spotify_proc.name.return_value = "Spotify.exe"
        spotify_proc.pid = 1234

        spotify_vol = MagicMock()
        spotify_vol.GetMasterVolume.return_value = 0.8
        spotify_session = MagicMock()
        spotify_session.Process = spotify_proc
        spotify_session._ctl.QueryInterface.return_value = spotify_vol

        # Mock self process (ALFRED) - should NOT be ducked
        alfred_proc = MagicMock()
        alfred_proc.name.return_value = "python.exe"
        alfred_proc.pid = os.getpid()
        alfred_vol = MagicMock()
        alfred_vol.GetMasterVolume.return_value = 1.0
        alfred_session = MagicMock()
        alfred_session.Process = alfred_proc
        alfred_session._ctl.QueryInterface.return_value = alfred_vol

        # Mock unrelated process (notepad.exe) - should NOT be ducked
        notepad_proc = MagicMock()
        notepad_proc.name.return_value = "notepad.exe"
        notepad_proc.pid = 5678
        notepad_session = MagicMock()
        notepad_session.Process = notepad_proc

        mock_sessions = [spotify_session, alfred_session, notepad_session]

        with patch("pycaw.pycaw.AudioUtilities.GetAllSessions", return_value=mock_sessions):
            # 1. Duck media apps by 70% (factor = 0.3)
            result = audio_ducker.duck_media_apps(volume_factor=0.3, sync=True)

            # Spotify volume should be set to 0.8 * 0.3 = 0.24
            self.assertIn("spotify.exe", result)
            self.assertAlmostEqual(result["spotify.exe"], 0.24, places=2)
            spotify_vol.SetMasterVolume.assert_called_with(0.24, None)

            # ALFRED own process must NOT be touched
            alfred_vol.SetMasterVolume.assert_not_called()

            # Verify state
            self.assertTrue(audio_ducker.is_ducked())
            self.assertEqual(audio_ducker._original_volumes[1234], 0.8)

            # 2. Unduck media apps
            restored = audio_ducker.unduck_media_apps(sync=True)
            self.assertIn("spotify.exe", restored)
            self.assertEqual(restored["spotify.exe"], 0.8)
            spotify_vol.SetMasterVolume.assert_called_with(0.8, None)

            # Verify state restored
            self.assertFalse(audio_ducker.is_ducked())
            self.assertEqual(len(audio_ducker._original_volumes), 0)

    @patch("core.audio_ducker.platform.system", return_value="Linux")
    def test_duck_and_unduck_linux(self, mock_system):
        """Verify Linux pulsectl ducking fallback logic."""
        mock_sink = MagicMock()
        mock_sink.proplist = {"application.name": "spotify", "application.process.id": "999"}
        mock_sink.volume.value_flat = 0.9

        mock_pulse = MagicMock()
        mock_pulse.__enter__.return_value = mock_pulse
        mock_pulse.sink_input_list.return_value = [mock_sink]

        mock_pulse_module = MagicMock()
        mock_pulse_module.Pulse.return_value = mock_pulse

        with patch.dict("sys.modules", {"pulsectl": mock_pulse_module}):
            result = audio_ducker.duck_media_apps(volume_factor=0.3, sync=True)
            self.assertIn("spotify", result)
            self.assertAlmostEqual(result["spotify"], 0.27, places=2)
            mock_pulse.volume_set_all_flat.assert_called_with(mock_sink, 0.27)

            restored = audio_ducker.unduck_media_apps(sync=True)
            self.assertIn("spotify", restored)
            self.assertEqual(restored["spotify"], 0.9)
            mock_pulse.volume_set_all_flat.assert_called_with(mock_sink, 0.9)

    @patch("core.audio_ducker.platform.system", return_value="Windows")
    def test_duck_windows_resilient_to_access_denied_session(self, mock_system):
        """A session whose .Process throws an exception does not abort ducking/unducking of other sessions."""
        # Malformed / AccessDenied session
        bad_session = MagicMock()
        type(bad_session).Process = unittest.mock.PropertyMock(side_effect=PermissionError("Access denied"))

        # Valid Spotify session
        spotify_proc = MagicMock()
        spotify_proc.name.return_value = "Spotify.exe"
        spotify_proc.pid = 4321
        spotify_vol = MagicMock()
        spotify_vol.GetMasterVolume.return_value = 0.7
        spotify_session = MagicMock()
        spotify_session.Process = spotify_proc
        spotify_session._ctl.QueryInterface.return_value = spotify_vol

        mock_sessions = [bad_session, spotify_session]
        with patch("pycaw.pycaw.AudioUtilities.GetAllSessions", return_value=mock_sessions):
            result = audio_ducker.duck_media_apps(volume_factor=0.3, sync=True)
            self.assertIn("spotify.exe", result)
            self.assertAlmostEqual(result["spotify.exe"], 0.21, places=2)

            restored = audio_ducker.unduck_media_apps(sync=True)
            self.assertIn("spotify.exe", restored)
            self.assertEqual(restored["spotify.exe"], 0.7)
            self.assertFalse(audio_ducker.is_ducked())

    @patch("core.audio_ducker.platform.system", return_value="Windows")
    def test_duck_windows_double_duck_preserves_original(self, mock_system):
        """Calling duck_media_apps twice must not overwrite original volume with already-ducked volume."""
        spotify_proc = MagicMock()
        spotify_proc.name.return_value = "Spotify.exe"
        spotify_proc.pid = 8888
        spotify_vol = MagicMock()
        spotify_vol.GetMasterVolume.return_value = 1.0
        spotify_session = MagicMock()
        spotify_session.Process = spotify_proc
        spotify_session._ctl.QueryInterface.return_value = spotify_vol

        mock_sessions = [spotify_session]
        with patch("pycaw.pycaw.AudioUtilities.GetAllSessions", return_value=mock_sessions):
            # First duck
            audio_ducker.duck_media_apps(volume_factor=0.3, sync=True)
            self.assertEqual(audio_ducker._original_volumes[8888], 1.0)

            # Simulate volume is now 0.3
            spotify_vol.GetMasterVolume.return_value = 0.3

            # Second duck
            audio_ducker.duck_media_apps(volume_factor=0.3, sync=True)
            # Original volume MUST still be 1.0, not 0.3!
            self.assertEqual(audio_ducker._original_volumes[8888], 1.0)

            # Unduck restores to original 1.0
            restored = audio_ducker.unduck_media_apps(sync=True)
            self.assertEqual(restored["spotify.exe"], 1.0)
            spotify_vol.SetMasterVolume.assert_called_with(1.0, None)

    @patch("core.audio_ducker.platform.system", return_value="Windows")
    def test_watchdog_auto_unducks_on_timeout(self, mock_system):
        """If unduck_media_apps is not called, watchdog auto-restores volume."""
        spotify_proc = MagicMock()
        spotify_proc.name.return_value = "Spotify.exe"
        spotify_proc.pid = 9999
        spotify_vol = MagicMock()
        spotify_vol.GetMasterVolume.return_value = 0.5
        spotify_session = MagicMock()
        spotify_session.Process = spotify_proc
        spotify_session._ctl.QueryInterface.return_value = spotify_vol

        mock_sessions = [spotify_session]
        with patch("pycaw.pycaw.AudioUtilities.GetAllSessions", return_value=mock_sessions):
            audio_ducker.duck_media_apps(volume_factor=0.3, sync=True)
            self.assertTrue(audio_ducker.is_ducked())

            # Trigger watchdog callback directly
            audio_ducker._on_watchdog_timeout()
            self.assertFalse(audio_ducker.is_ducked())
            spotify_vol.SetMasterVolume.assert_called_with(0.5, None)


if __name__ == "__main__":
    unittest.main()
