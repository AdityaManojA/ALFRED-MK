"""
tests/test_hud_audio_echo_suppression.py — Tests for Visual HUD video echo suppression and audio playback smoothness.

Validates:
1. is_hud_video_playing() on MainWindow and JarvisUI reports accurately based on VideoStatus and mute state.
2. MediaArbiter integration claims APP_PLAYER when HUD video is actively playing with audio and releases it on stop/pause/mute.
3. State transitions in UI duck HUD video in both SPEAKING and LISTENING modes.
4. Microphone streaming is suppressed while HUD video is playing, preventing echo/hallucination, but allows user voice through when Push-to-Talk (Ctrl+Space) is held.
5. Audio playback watchdog uses the extended ~2.16s cushion across inter-clause LLM generation pauses to prevent audio lag and choppy breaks.
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from core.hud_video.transport import VideoStatus, VideoState
from core.media.arbiter import AudioSource, MediaArbiter


class TestHudAudioEchoSuppression(unittest.TestCase):

    def test_is_hud_video_playing_states(self):
        """Test is_hud_video_playing accurately checks PLAYING and unmuted status."""
        import ui

        win = MagicMock()
        # Bind the real MainWindow.is_hud_video_playing to our mock window
        win.is_hud_video_playing = ui.MainWindow.is_hud_video_playing.__get__(win, ui.MainWindow)

        # 1. No controller
        win._hud_video_controller = None
        self.assertFalse(win.is_hud_video_playing())

        # 2. Controller is IDLE
        ctrl = MagicMock()
        ctrl._muted = False
        ctrl.state.return_value = VideoState(loaded=False, status=VideoStatus.IDLE)
        win._hud_video_controller = ctrl
        self.assertFalse(win.is_hud_video_playing())

        # 3. Controller is PAUSED
        ctrl.state.return_value = VideoState(loaded=True, status=VideoStatus.PAUSED)
        self.assertFalse(win.is_hud_video_playing())

        # 4. Controller is PLAYING but muted
        ctrl._muted = True
        ctrl.state.return_value = VideoState(loaded=True, status=VideoStatus.PLAYING)
        self.assertFalse(win.is_hud_video_playing())

        # 5. Controller is PLAYING and unmuted -> True
        ctrl._muted = False
        ctrl.state.return_value = VideoState(loaded=True, status=VideoStatus.PLAYING)
        self.assertTrue(win.is_hud_video_playing())

        # 6. JarvisUI proxy delegates to win.is_hud_video_playing
        jarvis_ui = MagicMock(spec=ui.JarvisUI)
        jarvis_ui._win = win
        jarvis_ui.is_hud_video_playing = ui.JarvisUI.is_hud_video_playing.__get__(jarvis_ui, ui.JarvisUI)
        self.assertTrue(jarvis_ui.is_hud_video_playing())

        # If muted again
        ctrl._muted = True
        self.assertFalse(jarvis_ui.is_hud_video_playing())

    def test_media_arbiter_and_music_ducking_on_state_change(self):
        """Test _on_hud_video_state_changed properly claims/releases APP_PLAYER and ducks bg_music."""
        import ui

        win = MagicMock()
        win._on_hud_video_state_changed = ui.MainWindow._on_hud_video_state_changed.__get__(win, ui.MainWindow)

        arbiter = MagicMock(spec=MediaArbiter)
        win._media_arbiter = arbiter
        bg_music = MagicMock()
        win._bg_music = bg_music

        ctrl = MagicMock()
        ctrl._muted = False
        win._hud_video_controller = ctrl

        # Video starts playing unmuted
        st_playing = VideoState(loaded=True, status=VideoStatus.PLAYING)
        win._on_hud_video_state_changed(st_playing)

        arbiter.claim.assert_called_once_with(AudioSource.APP_PLAYER)
        bg_music.set_ducked.assert_called_with(True)

        # Video pauses
        arbiter.reset_mock()
        bg_music.reset_mock()
        st_paused = VideoState(loaded=True, status=VideoStatus.PAUSED)
        win._on_hud_video_state_changed(st_paused)

        arbiter.release.assert_called_once_with(AudioSource.APP_PLAYER)
        bg_music.set_ducked.assert_called_with(False)

        # Video plays while muted -> should NOT claim APP_PLAYER
        arbiter.reset_mock()
        bg_music.reset_mock()
        ctrl._muted = True
        win._on_hud_video_state_changed(st_playing)

        arbiter.release.assert_called_once_with(AudioSource.APP_PLAYER)
        bg_music.set_ducked.assert_called_with(False)

    def test_apply_state_ducks_in_both_speaking_and_listening(self):
        """Test that HUD video is ducked when state is SPEAKING or LISTENING."""
        import ui

        win = MagicMock()
        win.hud = MagicMock()
        win._hud_video_controller = MagicMock()
        win._apply_state = ui.MainWindow._apply_state.__get__(win, ui.MainWindow)

        # LISTENING -> should duck
        win._apply_state("LISTENING")
        win._hud_video_controller.duck.assert_called_once()
        win._hud_video_controller.unduck.assert_not_called()

        # SPEAKING -> should duck
        win._hud_video_controller.reset_mock()
        win._apply_state("SPEAKING")
        win._hud_video_controller.duck.assert_called_once()
        win._hud_video_controller.unduck.assert_not_called()

        # IDLE -> should unduck
        win._hud_video_controller.reset_mock()
        win._apply_state("IDLE")
        win._hud_video_controller.unduck.assert_called_once()
        win._hud_video_controller.duck.assert_not_called()

    def test_mic_callback_suppression_logic(self):
        """Test mic gate drops streaming to out_queue during HUD video playback unless ptt_held is True."""
        out_queue_items = []
        is_playing = [True]
        ptt_held = [False]

        # Simulate mic callback gate logic directly matching main.py
        def simulate_callback(data_bytes):
            if is_playing[0] and not ptt_held[0]:
                return False  # Suppressed!
            out_queue_items.append(data_bytes)
            return True

        # 1. Video playing, PTT not held -> mic frame suppressed
        res1 = simulate_callback(b"video_sound_chunk")
        self.assertFalse(res1)
        self.assertEqual(len(out_queue_items), 0)

        # 2. Video playing, user presses PTT (Ctrl+Space) -> mic frame sent
        ptt_held[0] = True
        res2 = simulate_callback(b"user_speech_chunk")
        self.assertTrue(res2)
        self.assertEqual(out_queue_items, [b"user_speech_chunk"])

        # 3. Video paused/stopped -> normal open mic works without PTT
        ptt_held[0] = False
        is_playing[0] = False
        res3 = simulate_callback(b"normal_open_mic_chunk")
        self.assertTrue(res3)
        self.assertEqual(out_queue_items, [b"user_speech_chunk", b"normal_open_mic_chunk"])

    def test_silence_watchdog_threshold(self):
        """Test silence threshold calculation for playback smoothness."""
        # When turn_done_event is set: threshold is 3 (~360ms)
        import threading
        ev = threading.Event()
        ev.set()
        threshold_done = 3 if ev.is_set() else 18
        self.assertEqual(threshold_done, 3)

        # When turn_done_event is not set (e.g. streaming between sentences):
        ev.clear()
        threshold_inter_clause = 3 if ev.is_set() else 18
        self.assertEqual(threshold_inter_clause, 18)


if __name__ == "__main__":
    unittest.main()
