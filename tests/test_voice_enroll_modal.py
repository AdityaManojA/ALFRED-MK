import sys
import unittest
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication

# Ensure QApplication exists for Qt tests
app = QApplication.instance() or QApplication(sys.argv)

from core.speaker.profile_store import ProfileStore
from core.speaker.extractor import FakeSpeakerEmbeddingExtractor
from core.speaker.enrollment import SpeakerEnrollmentManager
from core.ui.voice_enroll_modal import VoiceEnrollModal


class TestVoiceEnrollModal(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path("test_voice_modal_profiles")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.store = ProfileStore(storage_dir=self.temp_dir)
        self.extractor = FakeSpeakerEmbeddingExtractor(dimension=512)

    def tearDown(self):
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_modal_initialization(self):
        modal = VoiceEnrollModal(
            profile_store=self.store,
            extractor=self.extractor,
            default_user="Bruce",
        )
        self.assertEqual(modal._name_input.text(), "Bruce")
        self.assertEqual(modal._current_step, 1)
        self.assertIn("Sample 1 of 3", modal._step_label.text())
        self.assertTrue(modal._record_btn.isEnabled())

    def test_modal_success_flow_3_samples(self):
        modal = VoiceEnrollModal(
            profile_store=self.store,
            extractor=self.extractor,
            default_user="Bruce",
        )
        # Generate clean synthetic speech-like tone
        sr = 16000
        t = np.linspace(0, 1.2, int(1.2 * sr), endpoint=False)
        audio = 0.5 * np.sin(2 * np.pi * 440 * t)

        # Process sample 1
        ok, msg = modal.process_audio_sample(audio, sr)
        self.assertTrue(ok)
        self.assertEqual(modal._current_step, 2)
        self.assertIn("Sample 2 of 3", modal._step_label.text())

        # Process sample 2
        ok, msg = modal.process_audio_sample(audio, sr)
        self.assertTrue(ok)
        self.assertEqual(modal._current_step, 3)
        self.assertIn("Sample 3 of 3", modal._step_label.text())

        # Process sample 3
        enrolled_user = []
        modal.profile_enrolled.connect(lambda name: enrolled_user.append(name))
        ok, msg = modal.process_audio_sample(audio, sr)
        self.assertTrue(ok)
        self.assertEqual(len(enrolled_user), 1)
        self.assertEqual(enrolled_user[0], "Bruce")

        # Verify saved in profile store
        saved = self.store.load_profile("Bruce")
        self.assertIsNotNone(saved)
        self.assertEqual(saved.user_name, "Bruce")

    def test_modal_rejects_silent_sample(self):
        modal = VoiceEnrollModal(
            profile_store=self.store,
            extractor=self.extractor,
            default_user="Bruce",
        )
        # Silent audio
        silent = np.zeros(16000, dtype=np.float32)
        ok, msg = modal.process_audio_sample(silent, 16000)
        self.assertFalse(ok)
        self.assertIn("silence", msg.lower())
        # Should stay at step 1
        self.assertEqual(modal._current_step, 1)

    def test_modal_delete_existing_profile(self):
        # First enroll Bruce
        from core.speaker.types import SpeakerProfile
        v = (np.ones(512, dtype=np.float32) / np.sqrt(512)).tolist()
        self.store.save_profile(SpeakerProfile(
            profile_id="bruce",
            user_name="Bruce",
            enrolled_at=1700000000.0,
            template_embeddings=[v],
            centroid_embedding=v,
            threshold=0.52,
            sample_count=3,
        ))
        modal = VoiceEnrollModal(
            profile_store=self.store,
            extractor=self.extractor,
            default_user="Bruce",
        )
        self.assertFalse(modal._delete_btn.isHidden())

        deleted = []
        modal.profile_deleted.connect(lambda: deleted.append(True))
        modal._delete_profile()
        self.assertTrue(deleted)
        self.assertIsNone(self.store.load_profile("Bruce"))

    def test_modal_theme_application_and_listener(self):
        from core.ui.themes import ThemeChrome
        from core.ui.themes.catalog import ALL_THEMES
        modal = VoiceEnrollModal(
            profile_store=self.store,
            extractor=self.extractor,
            default_user="Bruce",
        )
        pal = ThemeChrome.get_active().palette
        self.assertIn(pal.panel, modal.styleSheet())

        # Switch theme in ThemeChrome
        alt_theme = [t for t in ALL_THEMES if t.id != ThemeChrome.get_active().id][0]
        ThemeChrome.set_active(alt_theme)

        # Verify modal stylesheet updated to alt_theme palette
        self.assertIn(alt_theme.palette.panel, modal.styleSheet())
        self.assertEqual(modal._last_status_type, "ready")

        # Reject/close cleans up listener
        modal.reject()
        self.assertNotIn(modal._on_theme_changed, ThemeChrome._listeners)

    def test_modal_advanced_mode_selection(self):
        modal = VoiceEnrollModal(
            profile_store=self.store,
            extractor=self.extractor,
            default_user="Bruce",
        )
        self.assertEqual(modal._target_steps, 3)
        self.assertIn("Sample 1 of 3", modal._step_label.text())

        # Switch to advanced mode
        modal.set_mode("advanced")
        self.assertEqual(modal._target_steps, 10)
        self.assertEqual(modal._mode, "advanced")
        self.assertIn("Sample 1 of 10", modal._step_label.text())
        self.assertIn("10", modal._mode_info_label.text())
        self.assertIn("wake success", modal._mode_info_label.text().lower())

        # Switch back to standard mode
        modal.set_mode("standard")
        self.assertEqual(modal._target_steps, 3)
        self.assertEqual(modal._mode, "standard")
        self.assertIn("Sample 1 of 3", modal._step_label.text())

    def test_modal_success_flow_10_samples_advanced(self):
        modal = VoiceEnrollModal(
            profile_store=self.store,
            extractor=self.extractor,
            default_user="Bruce Wayne",
            default_mode="advanced",
        )
        self.assertEqual(modal._target_steps, 10)
        self.assertEqual(modal._current_step, 1)
        self.assertIn("Sample 1 of 10", modal._step_label.text())

        sr = 16000
        t = np.linspace(0, 1.2, int(1.2 * sr), endpoint=False)
        audio = 0.5 * np.sin(2 * np.pi * 440 * t)

        enrolled_user = []
        modal.profile_enrolled.connect(lambda name: enrolled_user.append(name))

        # Feed 10 consecutive samples
        for step in range(1, 11):
            ok, msg = modal.process_audio_sample(audio, sr)
            self.assertTrue(ok, f"Step {step} failed: {msg}")
            if step < 10:
                self.assertEqual(modal._current_step, step + 1)
                self.assertIn(f"Sample {step + 1} of 10", modal._step_label.text())

        # Verify completion after 10 samples
        self.assertEqual(len(enrolled_user), 1)
        self.assertEqual(enrolled_user[0], "Bruce Wayne")

        # Verify saved in profile store with 10 samples
        saved = self.store.load_profile("Bruce Wayne")
        self.assertIsNotNone(saved)
        self.assertEqual(saved.user_name, "Bruce Wayne")
        self.assertEqual(saved.sample_count, 10)
        self.assertEqual(len(saved.template_embeddings), 10)
        self.assertGreater(saved.threshold, 0.40)


if __name__ == "__main__":
    unittest.main()

