"""Regression tests for verified Spotify and Audio Core playback state."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication

import ui
import actions.spotify_control as spotify_module
from actions.spotify_control import SpotifyClient
from ui import TacticalAudioPlayerWidget, TronScoreBackgroundPlayer


class TestAudioCoreState(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_patch = patch.object(ui, "CONFIG_DIR", Path(self.temp_dir.name))
        self.config_patch.start()
        self.engine = TronScoreBackgroundPlayer()
        self.engine._spotify_sync_timer.stop()
        self.widget = TacticalAudioPlayerWidget(self.engine)

    def tearDown(self) -> None:
        self.widget.close()
        self.engine.stop()
        self.config_patch.stop()
        self.temp_dir.cleanup()

    def test_loaded_tron_track_starts_paused_with_play_button(self):
        self.assertFalse(self.engine.is_playing())
        self.assertEqual(self.widget._btn_play._mode, "play")
        self.assertEqual(self.widget._vol_btn.text(), "PAUSED")

    def test_spotify_snapshot_updates_title_and_button(self):
        self.engine._apply_spotify_state({
            "name": "679",
            "artist": "Fetty Wap, Remy Boyz",
            "uri": "spotify:track:679",
            "is_playing": True,
        })
        self.app.processEvents()

        self.assertEqual(self.widget._hdr_lbl.text(), "SPOTIFY // LIVE")
        self.assertIn("679", self.widget._track_lbl.text())
        self.assertIn("Fetty Wap", self.widget._track_lbl.text())
        self.assertEqual(self.widget._btn_play._mode, "pause")
        self.assertEqual(self.widget._vol_btn.text(), "LIVE")
        self.assertFalse(self.widget._vol_btn.isEnabled())

        self.engine._apply_spotify_state({
            "name": "679",
            "artist": "Fetty Wap, Remy Boyz",
            "uri": "spotify:track:679",
            "is_playing": False,
        })
        self.app.processEvents()
        self.assertEqual(self.widget._btn_play._mode, "play")
        self.assertEqual(self.widget._vol_btn.text(), "PAUSED")


class TestSpotifyApiOnlyPlayback(unittest.TestCase):
    def _client(self, status_code: int) -> SpotifyClient:
        client = SpotifyClient.__new__(SpotifyClient)
        client._refresh_token = "refresh-token"
        client._access_token = "access-token"
        client._token_expires_at = 99999999999.0
        client._session = MagicMock()
        client._session.put.return_value.status_code = status_code
        client._session.put.return_value.text = "failure"
        client._active_device_id = None
        client._current_track_info = {}
        client._last_playback_error = ""
        client.get_devices = MagicMock(return_value=[{
            "id": "device-1",
            "is_active": True,
            "is_restricted": False,
        }])
        return client

    def test_successful_api_playback_is_reported(self):
        client = self._client(204)
        result = client.play(uri="spotify:track:679")

        self.assertEqual(result["status"], "playing")
        self.assertEqual(result["method"], "api")
        client._session.put.assert_called_once()

    @patch("actions.spotify_control.subprocess.Popen")
    @patch("actions.spotify_control.webbrowser.open")
    def test_failed_api_playback_does_not_launch_spotify(self, open_browser, popen):
        client = self._client(403)
        result = client.play(uri="spotify:track:679")

        self.assertEqual(result["status"], "error")
        self.assertIn("Premium", result["error"])
        popen.assert_not_called()
        open_browser.assert_not_called()

    def test_playback_requires_user_authorization(self):
        client = self._client(204)
        client._refresh_token = ""
        result = client.play(uri="spotify:track:679")

        self.assertEqual(result["status"], "error")
        self.assertIn("Connect Spotify", result["error"])
        client._session.put.assert_not_called()

    def test_action_does_not_update_ui_after_failed_playback(self):
        client = MagicMock()
        client.play.return_value = {"status": "error", "error": "No active device."}
        player = MagicMock()

        with (
            patch.object(spotify_module, "get_spotify_client", return_value=client),
            patch.object(spotify_module, "_last_call_time", 0.0),
        ):
            result = spotify_module.spotify_control(
                {"action": "play", "uri": "spotify:track:679"}, player=player
            )

        self.assertEqual(result, "No active device.")
        player.set_spotify_playback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
