"""
tests/test_enroll_voice_cli.py — Tests for CLI enrollment utility.
"""

import unittest
from pathlib import Path
import tempfile
import shutil
import numpy as np

from core.speaker.profile_store import ProfileStore
from core.speaker.extractor import FakeSpeakerEmbeddingExtractor
from core.speaker.enrollment import SpeakerEnrollmentManager


class TestEnrollVoiceCLI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.store = ProfileStore(storage_dir=self.temp_dir)
        self.extractor = FakeSpeakerEmbeddingExtractor(dimension=512)
        self.manager = SpeakerEnrollmentManager(
            profile_store=self.store,
            embedding_extractor=self.extractor,
            min_samples=2,
            target_samples=3,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_enroll_from_wav_files(self):
        import scipy.io.wavfile as wavfile
        sr = 16000
        t = np.linspace(0, 1.2, int(1.2 * sr), endpoint=False)
        audio = (0.5 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)

        wav1 = self.temp_dir / "sample1.wav"
        wav2 = self.temp_dir / "sample2.wav"
        wav3 = self.temp_dir / "sample3.wav"
        wavfile.write(str(wav1), sr, audio)
        wavfile.write(str(wav2), sr, audio)
        wavfile.write(str(wav3), sr, audio)

        from tools.enroll_voice import enroll_from_files
        res = enroll_from_files(
            user_name="AlfredTester",
            wav_paths=[str(wav1), str(wav2), str(wav3)],
            profile_store=self.store,
            extractor=self.extractor,
        )
        self.assertTrue(res.success)
        self.assertIsNotNone(self.store.get_profile("AlfredTester"))

    def test_list_and_delete_profiles(self):
        from tools.enroll_voice import enroll_from_files, list_enrolled_profiles, delete_enrolled_profile
        import scipy.io.wavfile as wavfile

        sr = 16000
        t = np.linspace(0, 1.2, int(1.2 * sr), endpoint=False)
        audio = (0.5 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
        wav1 = self.temp_dir / "s1.wav"
        wav2 = self.temp_dir / "s2.wav"
        wavfile.write(str(wav1), sr, audio)
        wavfile.write(str(wav2), sr, audio)

        enroll_from_files("Tester1", [str(wav1), str(wav2)], self.store, self.extractor)
        profiles = list_enrolled_profiles(self.store)
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0].user_name, "Tester1")

        deleted = delete_enrolled_profile("Tester1", self.store)
        self.assertTrue(deleted)
        self.assertEqual(len(list_enrolled_profiles(self.store)), 0)


if __name__ == "__main__":
    unittest.main()
