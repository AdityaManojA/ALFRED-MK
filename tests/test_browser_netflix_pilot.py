"""
tests/test_browser_netflix_pilot.py
Master test suite for Browser Suite & Netflix Pilot.
"""
import unittest
from unittest.mock import MagicMock, patch

from core.browser.controller import (
    BrowserController,
    close_active_tab,
    new_tab,
    switch_tab,
    reopen_closed_tab,
    close_window,
    MSG_TAB_CLOSED,
    MSG_NEW_TAB_OPENED,
    MSG_TAB_SWITCHED,
    MSG_TAB_REOPENED,
    MSG_WINDOW_CLOSED,
)
from core.browser.platform.mac import MacBrowserDriver
from core.browser.platform.linux import LinuxBrowserDriver
from core.browser.platform.win import WinBrowserDriver
from core.pilots.netflix.detector import (
    NetflixDetector,
    NetflixState,
    ProfileSlot,
)
from core.pilots.netflix.actions import (
    NetflixActions,
    match_profile_selection,
    PROMPT_WHICH_PROFILE,
    MSG_ACCESSING_PROFILE,
    MSG_NOT_LOGGED_IN,
    MSG_SEARCHING,
    MSG_PLAYING,
    MSG_BROWSE_GENRE,
    ANSWER_WINDOW_S,
)
from actions.browser_control import browser_control
from actions.computer_settings import _detect_action
from actions.hud_video import hud_video
from actions.spotify_control import spotify_control
from actions.netflix_pilot import netflix_pilot
from core.hud_video.intent import classify_hud_intent


class TestMasterBrowserSuiteAndNetflixPilot(unittest.TestCase):
    # ── 1. Browser Controller Key Combos & Scripts ───────────────────────────
    @patch("subprocess.run")
    def test_mac_driver_script_targeting(self, mock_run):
        def mock_osascript(cmd, **kwargs):
            script = cmd[2] if len(cmd) > 2 else ""
            if "bundle identifier" in script:
                return MagicMock(returncode=0, stdout="com.google.Chrome\n")
            return MagicMock(returncode=0, stdout="")

        mock_run.side_effect = mock_osascript
        driver = MacBrowserDriver()
        self.assertEqual(driver.get_frontmost_browser(), "Google Chrome")
        self.assertTrue(driver.close_active_tab())
        args, _ = mock_run.call_args
        self.assertIn("close active tab of front window", args[0][2])

    @patch("subprocess.run")
    def test_linux_driver_key_targeting(self, mock_run):
        driver = LinuxBrowserDriver()
        def mock_sub(cmd, **kwargs):
            if cmd[:2] == ["xdotool", "getactivewindow"]:
                return MagicMock(returncode=0, stdout="445566\n")
            if "WM_CLASS" in cmd:
                return MagicMock(returncode=0, stdout='"brave-browser", "Brave-browser"\n')
            return MagicMock(returncode=0, stdout="")

        mock_run.side_effect = mock_sub
        self.assertEqual(driver.get_frontmost_browser(), "Brave")
        self.assertTrue(driver.close_active_tab())

    def test_windows_driver_constants(self):
        driver = WinBrowserDriver()
        for expected in ("chrome.exe", "msedge.exe", "brave.exe", "firefox.exe"):
            self.assertIn(expected, driver.KNOWN_WIN_BROWSERS)

    # ── 2. State Detector Pattern Matcher ────────────────────────────────────
    def test_state_detector_patterns(self):
        detector = NetflixDetector()

        # Gate
        gate_tokens = [
            ("Who's watching?", 0.98, (0.50, 0.15)),
            ("Profile A", 0.95, (0.30, 0.50)),
            ("Profile B", 0.95, (0.70, 0.50)),
        ]
        s_gate, profs = detector.detect_state_from_tokens(gate_tokens)
        self.assertEqual(s_gate, NetflixState.PROFILE_GATE)
        self.assertEqual(len(profs), 2)
        self.assertEqual(profs[0].name, "Profile A")
        self.assertEqual(profs[0].slot_index, 1)

        # Login
        login_tokens = [
            ("Sign In", 0.99, (0.9, 0.1)),
            ("Unlimited movies, TV shows, and more", 0.95, (0.5, 0.4)),
        ]
        s_login, _ = detector.detect_state_from_tokens(login_tokens)
        self.assertEqual(s_login, NetflixState.NOT_LOGGED_IN)

        # Browse Home
        browse_tokens = [
            ("Home", 0.95, (0.1, 0.05)),
            ("TV Shows", 0.95, (0.2, 0.05)),
            ("Movies", 0.95, (0.3, 0.05)),
        ]
        s_browse, _ = detector.detect_state_from_tokens(browse_tokens)
        self.assertEqual(s_browse, NetflixState.BROWSE_HOME)

        # Playing
        play_tokens = [
            ("Skip Intro", 0.99, (0.85, 0.9)),
            ("Audio & Subtitles", 0.95, (0.9, 0.95)),
        ]
        s_play, _ = detector.detect_state_from_tokens(play_tokens)
        self.assertEqual(s_play, NetflixState.PLAYING)

    # ── 3. Profile Name Fuzzy & Ordinal Matcher ──────────────────────────────
    def test_profile_fuzzy_and_ordinals(self):
        profiles = [
            ProfileSlot(name="Sarah", slot_index=1, center_norm=(0.3, 0.5)),
            ProfileSlot(name="John", slot_index=2, center_norm=(0.5, 0.5)),
            ProfileSlot(name="Family", slot_index=3, center_norm=(0.7, 0.5)),
        ]
        # Ordinal
        self.assertEqual(match_profile_selection("first", profiles).name, "Sarah")
        self.assertEqual(match_profile_selection("second", profiles).name, "John")
        self.assertEqual(match_profile_selection("3rd", profiles).name, "Family")

        # Fuzzy
        self.assertEqual(match_profile_selection("sara", profiles).name, "Sarah")
        self.assertEqual(match_profile_selection("johnny", profiles).name, "John")

    # ── 4. Precedence & Collision Guard Table ────────────────────────────────
    @patch("core.pilots.netflix.actions.NetflixActions.play_netflix")
    def test_routing_table_netflix_play(self, mock_play):
        mock_play.return_value = "Playing 'Interstellar', sir."
        
        # Sent via hud_video
        res_hud = hud_video(parameters={"action": "play", "target": "play Interstellar on Netflix"})
        self.assertEqual(res_hud, "Playing 'Interstellar', sir.")

        # Sent via spotify
        res_spot = spotify_control(parameters={"action": "play", "query": "Interstellar on Netflix"})
        self.assertEqual(res_spot, "Playing 'Interstellar', sir.")

    @patch("actions.hud_video.hud_video")
    def test_routing_table_trailer(self, mock_hud):
        mock_hud.return_value = "Playing trailer"
        res = spotify_control(parameters={"action": "play", "query": "Dune trailer"})
        self.assertEqual(res, "Playing trailer")

    @patch("actions.spotify_control.get_spotify_client")
    def test_routing_table_soundtrack(self, mock_client):
        mock_cli = MagicMock()
        mock_cli.play.return_value = {"status": "playing", "track": "Dune OST"}
        mock_client.return_value = mock_cli
        res = spotify_control(parameters={"action": "play", "query": "Dune soundtrack"})
        self.assertIn("Dune OST", res)

    def test_routing_table_tab_vs_window_vs_hud(self):
        # Tab close
        self.assertEqual(_detect_action("close tab").get("action"), "close_tab")
        self.assertEqual(_detect_action("close this tab").get("action"), "close_tab")
        self.assertEqual(_detect_action("shut this tab").get("action"), "close_tab")
        self.assertEqual(_detect_action("kill tab").get("action"), "close_tab")

        # Window close
        self.assertEqual(_detect_action("close window").get("action"), "close_window")
        self.assertEqual(_detect_action("close this").get("action"), "close_window")

        # Visual HUD close
        hud_res = classify_hud_intent("close the visual hud", video_loaded=True, video_visible=True)
        self.assertEqual(hud_res.action, "stop")


if __name__ == "__main__":
    unittest.main()
