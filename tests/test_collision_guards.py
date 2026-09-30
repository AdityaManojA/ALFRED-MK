"""
tests/test_collision_guards.py — Unit tests for Intent Precedence, Collision Guards, and Netflix Pilot.
"""
import unittest
from unittest.mock import MagicMock, patch

from actions.hud_video import hud_video
from actions.spotify_control import spotify_control
from actions.computer_settings import _detect_action
from actions.netflix_pilot import netflix_pilot
from core.hud_video.intent import classify_hud_intent
from core.pilots.netflix.detector import NetflixState, ProfileSlot


class TestCollisionGuardsAndRouting(unittest.TestCase):
    @patch("core.pilots.netflix.actions.NetflixActions.play_netflix")
    def test_play_on_netflix_routes_away_from_hud_video(self, mock_play_netflix):
        mock_play_netflix.return_value = "Playing 'Inception', sir."
        
        # Call hud_video with explicit 'on Netflix' target
        res = hud_video(parameters={"action": "play", "target": "play Inception on Netflix"})
        
        self.assertEqual(res, "Playing 'Inception', sir.")
        mock_play_netflix.assert_called_once_with("Inception")

    @patch("core.pilots.netflix.actions.NetflixActions.play_netflix")
    def test_play_on_netflix_routes_away_from_spotify(self, mock_play_netflix):
        mock_play_netflix.return_value = "Playing 'Inception', sir."
        
        # Call spotify_control with 'on Netflix' query
        res = spotify_control(parameters={"action": "play", "query": "Inception on Netflix"})
        
        self.assertEqual(res, "Playing 'Inception', sir.")
        mock_play_netflix.assert_called_once_with("Inception")

    @patch("actions.hud_video.hud_video")
    def test_play_trailer_diverts_from_spotify_to_hud_video(self, mock_hud_video):
        mock_hud_video.return_value = "Visual HUD resolving trailer"
        
        res = spotify_control(parameters={"action": "play", "query": "Inception trailer"})
        
        self.assertEqual(res, "Visual HUD resolving trailer")
        mock_hud_video.assert_called_once()
        args, kwargs = mock_hud_video.call_args
        self.assertEqual(kwargs["parameters"]["target"], "Inception trailer")

    @patch("actions.spotify_control.get_spotify_client")
    def test_play_soundtrack_stays_on_spotify(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.play.return_value = {"status": "playing", "track": "Inception Soundtrack", "artist": "Hans Zimmer"}
        mock_get_client.return_value = mock_client
        
        res = spotify_control(parameters={"action": "play", "query": "Inception soundtrack"})
        
        self.assertIn("Inception Soundtrack", res)
        self.assertIn("Spotify", res)
        mock_client.play.assert_called_once()

    def test_close_tab_never_collides_with_close_window(self):
        phrases = ["close tab", "close this tab", "shut this tab", "kill tab", "close active tab"]
        for phrase in phrases:
            matched = _detect_action(phrase)
            self.assertEqual(
                matched.get("action"),
                "close_tab",
                f"Collision: '{phrase}' resolved to '{matched.get('action')}' instead of 'close_tab'",
            )

    def test_close_tab_never_collides_with_hud_close(self):
        # Even with video loaded and visible, "close tab" must not close Visual HUD
        res = classify_hud_intent("close tab", video_loaded=True, video_visible=True)
        self.assertEqual(res.action, "none")

        res_this = classify_hud_intent("close this tab", video_loaded=True, video_visible=True)
        self.assertEqual(res_this.action, "none")

    def test_close_visual_hud_intent(self):
        res = classify_hud_intent("close visual hud", video_loaded=True, video_visible=True)
        self.assertEqual(res.action, "stop")

    @patch("core.pilots.netflix.actions.NetflixActions.open_netflix")
    @patch("core.pilots.netflix.actions.NetflixActions.search_netflix")
    @patch("core.pilots.netflix.actions.NetflixActions.play_netflix")
    @patch("core.pilots.netflix.actions.NetflixActions.browse_genre")
    def test_netflix_pilot_tool_actions(self, mock_browse, mock_play, mock_search, mock_open):
        mock_open.return_value = "Opened Netflix, sir."
        mock_search.return_value = "Searching Netflix for 'Interstellar', sir."
        mock_play.return_value = "Playing 'Dune', sir."
        mock_browse.return_value = "Browsing Sci-Fi on Netflix, sir."

        # Open
        self.assertEqual(netflix_pilot({"action": "open"}), "Opened Netflix, sir.")
        mock_open.assert_called_once()

        # Search
        self.assertEqual(netflix_pilot({"action": "search", "query": "Interstellar"}), "Searching Netflix for 'Interstellar', sir.")
        mock_search.assert_called_once_with("Interstellar")

        # Play
        self.assertEqual(netflix_pilot({"action": "play", "title": "Dune"}), "Playing 'Dune', sir.")
        mock_play.assert_called_once_with("Dune")

        # Browse
        self.assertEqual(netflix_pilot({"action": "browse", "query": "Sci-Fi"}), "Browsing Sci-Fi on Netflix, sir.")
        mock_browse.assert_called_once_with("Sci-Fi")


if __name__ == "__main__":
    unittest.main()
