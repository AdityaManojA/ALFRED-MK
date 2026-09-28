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


if __name__ == "__main__":
    unittest.main()
