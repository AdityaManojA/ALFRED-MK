"""Focused contracts for the speech-reactive HUD animation state."""
from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication

from ui import HudCanvas, ReactiveMicButton
from memory import config_manager


class TestHudReactivity(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.hud = HudCanvas("", "ALFRED")
        self.hud._tmr.stop()

    def tearDown(self) -> None:
        self.hud.close()

    def test_speech_energy_accelerates_then_decays(self):
        self.hud.state = "SPEAKING"
        self.hud.speaking = True
        self.hud._live_amp = 0.8
        self.hud._step_t = time.time() - 0.05

        self.hud._step()

        speaking_energy = self.hud._speech_energy
        self.assertGreater(speaking_energy, 0.0)
        self.assertGreater(self.hud._core_phase, 0.05)

        self.hud.state = "LISTENING"
        self.hud.speaking = False
        self.hud._step_t = time.time() - 0.10
        self.hud._step()

        self.assertLess(self.hud._speech_energy, speaking_energy)

    def test_sleep_fades_particles_and_wake_triggers_burst(self):
        self.hud.state = "SLEEPING"
        self.hud._step_t = time.time() - 0.10
        self.hud._step()
        sleeping_visibility = self.hud._particle_visibility

        self.assertLess(sleeping_visibility, 1.0)

        self.hud.state = "LISTENING"
        self.hud._step_t = time.time() - 0.10
        before = self.hud._wake_burst_t
        self.hud._step()

        self.assertGreater(self.hud._wake_burst_t, before)
        self.assertEqual(self.hud._state_transition_from, "SLEEPING")

    def test_listening_level_reaches_accessible_acoustic_control(self):
        button = ReactiveMicButton("Sensors")
        self.hud.on_visual_level = button.set_reactivity
        self.hud.state = "LISTENING"
        self.hud._live_amp = 0.7
        self.hud._paint_tick = 1
        self.hud._step_t = time.time() - 0.05

        self.hud._step()

        self.assertTrue(button._react_active)
        self.assertGreater(button._react_level, 0.0)
        button.setAccessibleName("Acoustic sensors")
        self.assertEqual(button.accessibleName(), "Acoustic sensors")
        button.close()

    def test_reactive_mode_is_default_and_legacy_styles_migrate(self):
        with patch.object(config_manager, "load_api_keys", return_value={}):
            self.assertEqual(config_manager.get_hud_style(), "reactive")
        with patch.object(config_manager, "load_api_keys", return_value={"hud_style": "face"}):
            self.assertEqual(config_manager.get_hud_style(), "reactive")
        with patch.object(config_manager, "load_api_keys", return_value={"hud_style": "classic"}):
            self.assertEqual(config_manager.get_hud_style(), "reactive")

    def test_hud_has_no_classic_mode_switch(self):
        self.assertEqual(self.hud.hud_style, "reactive")
        self.assertFalse(hasattr(self.hud, "reactive_enabled"))

    def test_saving_any_hud_style_is_coerced_to_reactive(self):
        with patch.object(config_manager, "_save_flag") as save:
            config_manager.save_hud_style("classic")
        save.assert_called_once_with("hud_style", "reactive")


if __name__ == "__main__":
    unittest.main()
