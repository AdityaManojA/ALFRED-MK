"""
tests/test_netflix_actions.py — Unit tests for Netflix Actions, Profile Gate, and Playback.
"""
import unittest
from unittest.mock import MagicMock, patch

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
from core.pilots.netflix.detector import NetflixState, ProfileSlot


class TestNetflixActions(unittest.TestCase):
    def setUp(self):
        self.profiles = [
            ProfileSlot(name="Aditya", slot_index=1, center_norm=(0.32, 0.50)),
            ProfileSlot(name="Guest", slot_index=2, center_norm=(0.50, 0.50)),
            ProfileSlot(name="Kids", slot_index=3, center_norm=(0.68, 0.50)),
        ]
        self.mock_speak = MagicMock()
        self.mock_detector = MagicMock()
        self.actions = NetflixActions(
            detector=self.mock_detector,
            speak_fn=self.mock_speak,
        )

    def test_match_profile_selection_by_name(self):
        matched = match_profile_selection("Aditya", self.profiles)
        self.assertIsNotNone(matched)
        self.assertEqual(matched.name, "Aditya")

        # Case insensitive & partial
        matched_partial = match_profile_selection("select aditya please", self.profiles)
        self.assertIsNotNone(matched_partial)
        self.assertEqual(matched_partial.name, "Aditya")

    def test_match_profile_selection_by_slot_number(self):
        # By ordinal string
        self.assertEqual(match_profile_selection("first", self.profiles).name, "Aditya")
        self.assertEqual(match_profile_selection("second", self.profiles).name, "Guest")
        self.assertEqual(match_profile_selection("third", self.profiles).name, "Kids")

        # By digit
        self.assertEqual(match_profile_selection("1", self.profiles).name, "Aditya")
        self.assertEqual(match_profile_selection("2", self.profiles).name, "Guest")
        self.assertEqual(match_profile_selection("3", self.profiles).name, "Kids")

    def test_match_profile_selection_fuzzy(self):
        matched = match_profile_selection("Adit", self.profiles)
        self.assertIsNotNone(matched)
        self.assertEqual(matched.name, "Aditya")

        none_matched = match_profile_selection("Stranger", self.profiles)
        self.assertIsNone(none_matched)

    @patch("pyautogui.click")
    def test_handle_profile_gate_flow(self, mock_click):
        mock_ans_win = MagicMock()
        mock_ans_win.request_answer_sync.return_value = "Aditya"

        ok, msg = self.actions.handle_profile_gate(
            self.profiles,
            answer_window=mock_ans_win,
        )

        self.assertTrue(ok)
        mock_ans_win.request_answer_sync.assert_called_once_with(
            prompt_speech=PROMPT_WHICH_PROFILE,
            timeout_s=ANSWER_WINDOW_S,
        )
        self.assertEqual(msg, MSG_ACCESSING_PROFILE.format(profile="Aditya"))
        self.mock_speak.assert_called_with(msg)
        mock_click.assert_called_once()

    @patch("webbrowser.open")
    def test_open_netflix_not_logged_in_flow(self, mock_wb):
        self.mock_detector.inspect_state.return_value = (NetflixState.NOT_LOGGED_IN, [])

        with patch("time.sleep"):
            res = self.actions.open_netflix()

        self.assertEqual(res, MSG_NOT_LOGGED_IN)
        self.mock_speak.assert_called_with(MSG_NOT_LOGGED_IN)
        mock_wb.assert_called_once()

    @patch("pyautogui.typewrite")
    @patch("pyautogui.press")
    def test_search_netflix_flow(self, mock_press, mock_type):
        self.mock_detector.is_netflix_frontmost.return_value = True

        msg = self.actions.search_netflix("Interstellar")
        self.assertEqual(msg, MSG_SEARCHING.format(query="Interstellar"))
        self.mock_speak.assert_called_with(msg)
        mock_press.assert_any_call("/")
        mock_type.assert_called_once_with("Interstellar", interval=0.025)

    @patch("pyautogui.click")
    @patch("pyautogui.typewrite")
    @patch("pyautogui.press")
    def test_play_netflix_flow(self, mock_press, mock_type, mock_click):
        self.mock_detector.is_netflix_frontmost.return_value = True

        with patch("time.sleep"):
            msg = self.actions.play_netflix("Inception")

        self.assertEqual(msg, MSG_PLAYING.format(title="Inception"))
        self.mock_speak.assert_called_with(msg)
        mock_click.assert_called_once()

    @patch("webbrowser.open")
    def test_browse_genre_flow(self, mock_wb):
        msg = self.actions.browse_genre("Sci-Fi")
        self.assertEqual(msg, MSG_BROWSE_GENRE.format(genre="Sci-fi"))
        mock_wb.assert_called_once_with("https://www.netflix.com/browse/genre/1492")


if __name__ == "__main__":
    unittest.main()
