"""
Unit tests for Phase 1: Engine interface, default engine wrapping, capability reporting,
settings persistence, and CustomizeOverlay UI behavior.
"""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication

from core.tts.engine_base import Capability, TTSEngine
from core.tts.engine_default import EngineDefault
from core.tts.capability import check_jarvis_capability
from memory import config_manager
from ui import CustomizeOverlay

# Ensure QApplication instance exists for widget testing
_app = QApplication.instance() or QApplication([])


class TestJarvisVoicePhase1(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.config_dir = Path(self.temp_dir.name)
        self.config_file = self.config_dir / "api_keys.json"
        self.dir_patch = patch.object(config_manager, "CONFIG_DIR", self.config_dir)
        self.file_patch = patch.object(config_manager, "CONFIG_FILE", self.config_file)
        self.dir_patch.start()
        self.file_patch.start()
        config_manager.invalidate_config_cache()

    def tearDown(self):
        config_manager.invalidate_config_cache()
        self.file_patch.stop()
        self.dir_patch.stop()
        self.temp_dir.cleanup()

    def test_engine_default_interface_compliance(self):
        """Verify EngineDefault implements TTSEngine ABC."""
        fake_engine = MagicMock()
        engine = EngineDefault(concrete_engine=fake_engine)
        self.assertIsInstance(engine, TTSEngine)
        self.assertEqual(engine.name, "default")
        self.assertEqual(engine.is_available(), Capability.OK)

        # Verify speech delegates directly to underlying engine
        engine.speak("Testing default engine")
        fake_engine.speak.assert_called_once_with("Testing default engine")

    def test_settings_persistence_and_restart_roundtrip(self):
        """Verify voice.engine round-trips correctly and invalid values collapse to default."""
        # Initial default
        self.assertEqual(config_manager.get_voice_engine(), "default")

        # Save jarvis
        config_manager.save_voice_engine("jarvis")
        self.assertEqual(config_manager.get_voice_engine(), "jarvis")

        # Simulate fresh process restart by invalidating cache and reloading
        config_manager.invalidate_config_cache()
        self.assertEqual(config_manager.get_voice_engine(), "jarvis")

        # Verify underlying JSON schema has both keys
        raw_data = json.loads(self.config_file.read_text(encoding="utf-8"))
        self.assertEqual(raw_data.get("voice_engine"), "jarvis")
        self.assertEqual(raw_data.get("voice", {}).get("engine"), "jarvis")

        # Invalidate with an invalid string
        config_manager.save_voice_engine("corrupted_value")
        self.assertEqual(config_manager.get_voice_engine(), "default")

    def test_capability_honest_status_on_unmet_deps(self):
        """Verify capability inspector safely returns MISSING_DEPS or NO_CUDA without crashing."""
        cap = check_jarvis_capability(allow_cpu=False)
        self.assertIsInstance(cap, Capability)
        # On this environment, voxcpm is not installed, so MISSING_DEPS is expected
        self.assertIn(cap, (Capability.MISSING_DEPS, Capability.NO_CUDA, Capability.PYTHON_VERSION))
        self.assertFalse(cap.is_usable(allow_cpu=False))
        self.assertTrue(len(cap.display_status()) > 0)

    def test_ui_gate_prevents_selecting_unavailable_jarvis(self):
        """Selecting jarvis when unavailable must keep default active and show why."""
        overlay = CustomizeOverlay(
            assistant_name="Alfred",
            user_name="Bruce",
            ui_color="#8e9bff",
            voice="Charon",
            current_icon="",
            voice_engine="default",
        )
        try:
            # Engine buttons exist
            self.assertIn("default", overlay._engine_btns)
            self.assertIn("jarvis", overlay._engine_btns)
            self.assertEqual(overlay._sel_voice_engine, "default")

            # Mock capability to report MISSING_DEPS
            with patch("core.tts.capability.check_jarvis_capability", return_value=Capability.MISSING_DEPS):
                overlay._on_engine_pick("jarvis")

                # Must not flip into a broken state: default remains active
                self.assertEqual(overlay._sel_voice_engine, "default")
                self.assertIn("BLOCKED", overlay._lbl_engine_status.text())
                self.assertIn("Missing dependencies", overlay._lbl_engine_status.text())

            # Preview button clicked with mock
            overlay.on_preview_voice = MagicMock()
            overlay._btn_preview_voice.click()
            overlay.on_preview_voice.assert_called_once_with("default")
        finally:
            overlay.close()

    def test_ui_allows_selecting_jarvis_when_capable(self):
        """When capability is OK, selecting jarvis succeeds and saves."""
        overlay = CustomizeOverlay(
            assistant_name="Alfred",
            user_name="Bruce",
            ui_color="#8e9bff",
            voice="Charon",
            current_icon="",
            voice_engine="default",
        )
        try:
            with patch("core.tts.capability.check_jarvis_capability", return_value=Capability.OK):
                overlay._on_engine_pick("jarvis")
                self.assertEqual(overlay._sel_voice_engine, "jarvis")
                self.assertIn("ACTIVE: Jarvis Voice", overlay._lbl_engine_status.text())

                overlay._save()
                self.assertEqual(config_manager.get_voice_engine(), "jarvis")
        finally:
            overlay.close()


if __name__ == "__main__":
    unittest.main()
