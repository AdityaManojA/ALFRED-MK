"""
tests/hud_video/test_destination_prompt.py — Unit tests for Play Destination Prompt flow,
explicit routing, answer classification, deduplication, and preference memory.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch, call
from PyQt6.QtWidgets import QApplication

# Ensure QApplication exists
_APP = QApplication.instance() or QApplication([])

from actions.hud_video import (
    hud_video,
    _single_flight,
    ANSWER_WINDOW_S,
    DEST_REASK_MAX,
    REMEMBER_DEST,
)
from core.hud_video.controller import HudVideoController
from core.hud_video.resolve import PlayableRef
from core.hud_video.destination import (
    PlayDestinationManager,
    get_destination_manager,
    parse_explicit_destination,
    check_preference_command,
    classify_yes_no,
    classify_dest_choice,
    is_known_app,
    execute_destination,
    PROMPT_IN_APP,
    PROMPT_CHOICE,
    PROMPT_WHICH_APP,
    LINE_APP_NOT_FOUND,
    TOAST_CANCELLED,
    TOAST_PREF_SAVED,
    TOAST_PREF_CLEARED,
)
from core.registry import register
from memory.config_manager import save_video_play_destination, get_video_play_destination


class TestPlayDestinationPrompt(unittest.TestCase):

    def setUp(self):
        _single_flight.reset()
        self.dest_mgr = get_destination_manager()
        self.dest_mgr.cancel()
        save_video_play_destination(None)  # Reset preference

        self.ctrl = HudVideoController()
        register("hud_video_controller", self.ctrl)

    def tearDown(self):
        _single_flight.reset()
        self.dest_mgr.cancel()
        save_video_play_destination(None)

    # -----------------------------------------------------------------------
    # 1. Parsing and Classification Tests
    # -----------------------------------------------------------------------

    def test_parse_explicit_destinations(self):
        """Explicit destination phrases are accurately parsed and stripped from query."""
        # Visual HUD / in app
        dest, query, app = parse_explicit_destination("play Dune in the app")
        self.assertEqual(dest, "app")
        self.assertEqual(query, "Dune")

        dest, query, app = parse_explicit_destination("watch Batman on the hud")
        self.assertEqual(dest, "app")
        self.assertEqual(query, "Batman")

        # YouTube
        dest, query, app = parse_explicit_destination("play Dune on YouTube")
        self.assertEqual(dest, "youtube")
        self.assertEqual(query, "Dune")

        dest, query, app = parse_explicit_destination("stream Interstellar in yt")
        self.assertEqual(dest, "youtube")
        self.assertEqual(query, "Interstellar")

        # Default player / browser
        dest, query, app = parse_explicit_destination("play Dune in the default player")
        self.assertEqual(dest, "default")
        self.assertEqual(query, "Dune")

        dest, query, app = parse_explicit_destination("show matrix in browser")
        self.assertEqual(dest, "default")
        self.assertEqual(query, "matrix")

        # Named app / window
        dest, query, app = parse_explicit_destination("play Dune in Chrome")
        self.assertEqual(dest, "window")
        self.assertEqual(query, "Dune")
        self.assertEqual(app, "chrome")

        dest, query, app = parse_explicit_destination("watch Avatar in VLC")
        self.assertEqual(dest, "window")
        self.assertEqual(query, "Avatar")
        self.assertEqual(app, "vlc")

        # No destination
        dest, query, app = parse_explicit_destination("play the new Dune trailer")
        self.assertIsNone(dest)
        self.assertEqual(query, "new Dune trailer")

    def test_classify_yes_no(self):
        """Responses to 'In the app, sir?' are correctly classified."""
        self.assertEqual(classify_yes_no("yes"), "yes")
        self.assertEqual(classify_yes_no("yeah"), "yes")
        self.assertEqual(classify_yes_no("sure"), "yes")
        self.assertEqual(classify_yes_no("in the app"), "yes")
        self.assertEqual(classify_yes_no("app"), "yes")

        self.assertEqual(classify_yes_no("no"), "no")
        self.assertEqual(classify_yes_no("nope"), "no")
        self.assertEqual(classify_yes_no("other"), "no")
        self.assertEqual(classify_yes_no("youtube"), "no")
        self.assertEqual(classify_yes_no("chrome"), "no")

        self.assertIsNone(classify_yes_no("gibberish unrecognised"))

    def test_classify_dest_choice(self):
        """Responses to 'Default player, YouTube, or another window, sir?' are categorized."""
        self.assertEqual(classify_dest_choice("youtube"), ("youtube", None))
        self.assertEqual(classify_dest_choice("on yt"), ("youtube", None))

        self.assertEqual(classify_dest_choice("default player"), ("default", None))
        self.assertEqual(classify_dest_choice("in the browser"), ("default", None))

        self.assertEqual(classify_dest_choice("chrome"), ("window", "chrome"))
        self.assertEqual(classify_dest_choice("firefox"), ("window", "firefox"))
        self.assertEqual(classify_dest_choice("vlc"), ("window", "vlc"))

        self.assertEqual(classify_dest_choice("another window"), ("window", None))
        self.assertEqual(classify_dest_choice("other app"), ("window", None))

        self.assertEqual(classify_dest_choice("random words"), (None, None))

    def test_preference_command_parsing(self):
        """Preference commands accurately update config manager and return toasts."""
        is_cmd, resp, val = check_preference_command("always play in the app")
        self.assertTrue(is_cmd)
        self.assertEqual(val, "app")
        self.assertEqual(resp, TOAST_PREF_SAVED)
        self.assertEqual(get_video_play_destination(), "app")

        is_cmd, resp, val = check_preference_command("ask me again")
        self.assertTrue(is_cmd)
        self.assertIsNone(val)
        self.assertEqual(resp, TOAST_PREF_CLEARED)
        self.assertIsNone(get_video_play_destination())

    # -----------------------------------------------------------------------
    # 2. Routing Table: Explicit Destination vs Prompt
    # -----------------------------------------------------------------------

    def test_routing_explicit_app_skips_prompt(self):
        """'play Dune in the app' immediately triggers Visual HUD without prompting."""
        mock_speak = MagicMock()
        with patch("actions.hud_video.threading.Thread") as mock_thread:
            fake_t = MagicMock()
            mock_thread.return_value = fake_t

            res = hud_video(parameters={"action": "play", "target": "the new Dune trailer in the app"}, speak=mock_speak)
            self.assertEqual(res, "Playing new Dune trailer on the Visual HUD.")
            self.assertFalse(self.dest_mgr.is_prompting)
            mock_thread.assert_called_once()

    def test_routing_explicit_youtube_skips_prompt(self):
        """'play Dune on YouTube' opens browser without prompting."""
        mock_speak = MagicMock()
        with patch("webbrowser.open") as mock_wb:
            res = hud_video(parameters={"action": "play", "target": "Dune 2 trailer on YouTube"}, speak=mock_speak)
            self.assertEqual(res, "Opening Dune 2 trailer on YouTube.")
            self.assertFalse(self.dest_mgr.is_prompting)
            mock_wb.assert_called_once()
            url_called = mock_wb.call_args[0][0]
            self.assertTrue(url_called.startswith("https://www.youtube.com/results?search_query="))

    def test_routing_explicit_window_chrome(self):
        """'play Dune in Chrome' executes Chrome command without prompting."""
        mock_speak = MagicMock()
        with patch("subprocess.Popen") as mock_popen:
            res = hud_video(parameters={"action": "play", "target": "Dune in Chrome"}, speak=mock_speak)
            self.assertEqual(res, "Opening Dune in chrome.")
            self.assertFalse(self.dest_mgr.is_prompting)
            mock_popen.assert_called_once()

    def test_routing_no_destination_starts_prompt(self):
        """'play Dune' with no destination starts destination prompt and returns terminal status."""
        mock_speak = MagicMock()
        with patch.object(self.dest_mgr, "_worker_flow") as mock_worker:
            res = hud_video(parameters={"action": "play", "target": "Dune trailer"}, speak=mock_speak)
            self.assertEqual(res, "Asked destination for Dune trailer.")
            self.assertTrue(self.dest_mgr.is_prompting)

    def test_duplicate_play_during_prompt_is_ignored(self):
        """Duplicate play command while prompt is open is ignored."""
        mock_speak = MagicMock()
        with patch.object(self.dest_mgr, "_worker_flow"):
            res1 = hud_video(parameters={"action": "play", "target": "Dune trailer"}, speak=mock_speak)
            self.assertEqual(res1, "Asked destination for Dune trailer.")
            self.assertTrue(self.dest_mgr.is_prompting)

            # Second request while prompting
            res2 = hud_video(parameters={"action": "play", "target": "Interstellar trailer"}, speak=mock_speak)
            self.assertEqual(res2, "Visual HUD is already asking for play destination.")

    # -----------------------------------------------------------------------
    # 3. Interactive Flow Scenarios
    # -----------------------------------------------------------------------

    def test_flow_yes_plays_in_visual_hud(self):
        """Flow: Prompt Q1 -> 'yes' -> Visual HUD plays."""
        mock_speak = MagicMock()
        mock_ans_win = MagicMock()
        mock_ans_win.request_answer_sync.side_effect = ["yes"]

        with patch.object(self.dest_mgr, "_get_answer_window", return_value=mock_ans_win), \
             patch("actions.hud_video._resolve_and_play") as mock_play:

            self.dest_mgr._is_prompting = True
            self.dest_mgr._worker_flow("Dune trailer", None, self.ctrl, mock_speak)

            self.assertFalse(self.dest_mgr.is_prompting)
            mock_ans_win.request_answer_sync.assert_called_once_with(PROMPT_IN_APP, timeout_s=ANSWER_WINDOW_S)

    def test_flow_no_then_youtube(self):
        """Flow: Prompt Q1 -> 'no' -> Prompt Q2 -> 'YouTube' -> opens YouTube."""
        mock_speak = MagicMock()
        mock_ans_win = MagicMock()
        mock_ans_win.request_answer_sync.side_effect = ["no", "YouTube"]

        with patch.object(self.dest_mgr, "_get_answer_window", return_value=mock_ans_win), \
             patch("webbrowser.open") as mock_wb:

            self.dest_mgr._is_prompting = True
            self.dest_mgr._worker_flow("Dune trailer", None, self.ctrl, mock_speak)

            self.assertFalse(self.dest_mgr.is_prompting)
            self.assertEqual(mock_ans_win.request_answer_sync.call_count, 2)
            mock_wb.assert_called_once()
            self.assertTrue("youtube.com" in mock_wb.call_args[0][0])

    def test_flow_no_then_default(self):
        """Flow: Prompt Q1 -> 'no' -> Prompt Q2 -> 'default player' -> opens default."""
        mock_speak = MagicMock()
        mock_ans_win = MagicMock()
        mock_ans_win.request_answer_sync.side_effect = ["no", "default player"]

        with patch.object(self.dest_mgr, "_get_answer_window", return_value=mock_ans_win), \
             patch("webbrowser.open") as mock_wb:

            self.dest_mgr._is_prompting = True
            self.dest_mgr._worker_flow("Dune trailer", None, self.ctrl, mock_speak)

            self.assertFalse(self.dest_mgr.is_prompting)
            self.assertEqual(mock_ans_win.request_answer_sync.call_count, 2)
            mock_wb.assert_called_once()

    def test_flow_no_then_another_window_then_chrome(self):
        """Flow: Prompt Q1 -> 'no' -> Prompt Q2 -> 'another window' -> Prompt Q3 -> 'Chrome'."""
        mock_speak = MagicMock()
        mock_ans_win = MagicMock()
        mock_ans_win.request_answer_sync.side_effect = ["no", "another window", "chrome"]

        with patch.object(self.dest_mgr, "_get_answer_window", return_value=mock_ans_win), \
             patch("subprocess.Popen") as mock_popen:

            self.dest_mgr._is_prompting = True
            self.dest_mgr._worker_flow("Dune trailer", None, self.ctrl, mock_speak)

            self.assertFalse(self.dest_mgr.is_prompting)
            self.assertEqual(mock_ans_win.request_answer_sync.call_count, 3)
            mock_popen.assert_called_once()

    def test_flow_unknown_app_speaks_failure(self):
        """Flow: Unknown app in Q3 speaks 'Can't find that, sir.'."""
        mock_speak = MagicMock()
        mock_ans_win = MagicMock()
        mock_ans_win.request_answer_sync.side_effect = ["no", "another window", "non_existent_fake_player_999"]

        with patch.object(self.dest_mgr, "_get_answer_window", return_value=mock_ans_win), \
             patch("shutil.which", return_value=None):

            self.dest_mgr._is_prompting = True
            self.dest_mgr._worker_flow("Dune trailer", None, self.ctrl, mock_speak)

            self.assertFalse(self.dest_mgr.is_prompting)
            mock_speak.assert_called_once_with(LINE_APP_NOT_FOUND)

    def test_flow_silence_reasks_once_then_cancels(self):
        """Silence / empty response re-asks once (DEST_REASK_MAX=1), then cancels with toast."""
        mock_speak = MagicMock()
        mock_ans_win = MagicMock()
        # Returns empty string twice (initial + 1 re-ask)
        mock_ans_win.request_answer_sync.side_effect = ["", ""]

        with patch.object(self.dest_mgr, "_get_answer_window", return_value=mock_ans_win), \
             patch.object(self.ctrl, "show_toast") as mock_toast:

            self.dest_mgr._is_prompting = True
            self.dest_mgr._worker_flow("Dune trailer", None, self.ctrl, mock_speak)

            self.assertFalse(self.dest_mgr.is_prompting)
            self.assertEqual(mock_ans_win.request_answer_sync.call_count, 2)
            mock_toast.assert_called_with(TOAST_CANCELLED)

    # -----------------------------------------------------------------------
    # 4. Remembered Preference Tests
    # -----------------------------------------------------------------------

    def test_remembered_preference_skips_prompt(self):
        """Setting 'always play in the app' skips future destination prompts."""
        mock_speak = MagicMock()

        # 1. Save preference
        res_pref = hud_video(parameters={"action": "play", "target": "always play in the app"}, speak=mock_speak)
        self.assertEqual(res_pref, TOAST_PREF_SAVED)
        self.assertEqual(get_video_play_destination(), "app")

        # 2. Subsequent play command with no destination plays in app directly
        with patch("actions.hud_video.threading.Thread") as mock_thread:
            fake_t = MagicMock()
            mock_thread.return_value = fake_t

            res = hud_video(parameters={"action": "play", "target": "Inception trailer"}, speak=mock_speak)
            self.assertEqual(res, "Playing Inception trailer on the Visual HUD.")
            self.assertFalse(self.dest_mgr.is_prompting)
            mock_thread.assert_called_once()

        # 3. Clear preference with 'ask me again'
        res_clear = hud_video(parameters={"action": "play", "target": "ask me again"}, speak=mock_speak)
        self.assertEqual(res_clear, TOAST_PREF_CLEARED)
        self.assertIsNone(get_video_play_destination())

        # 4. Next play prompts again
        with patch.object(self.dest_mgr, "_worker_flow"):
            res_after = hud_video(parameters={"action": "play", "target": "Inception trailer"}, speak=mock_speak)
            self.assertEqual(res_after, "Asked destination for Inception trailer.")
            self.assertTrue(self.dest_mgr.is_prompting)

    # -----------------------------------------------------------------------
    # 5. Loaded Video Transport Commands Not Broken
    # -----------------------------------------------------------------------

    def test_loaded_video_transport_preserves_controls(self):
        """Transport commands on loaded video do not trigger destination prompts."""
        mock_speak = MagicMock()

        # Load video into controller
        ref = PlayableRef(
            kind="direct_url",
            uri="https://cdn.example.com/video.mp4",
            title="Dune 2",
            thumb_url=None,
            source_query="Dune 2",
        )
        self.ctrl.play(ref)
        self.ctrl.on_backend_duration(300.0)
        self.ctrl.on_backend_ready()

        with patch.object(self.ctrl, "seek") as mock_seek, \
             patch.object(self.dest_mgr, "start_flow") as mock_flow:

            res = hud_video(parameters={"action": "play", "target": "play the current video at 2:35"}, speak=mock_speak)
            self.assertEqual(res, "Seeked to 2:35.")
            mock_seek.assert_called_once_with(155.0)
            mock_flow.assert_not_called()


if __name__ == "__main__":
    unittest.main()
