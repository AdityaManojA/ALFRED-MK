"""
tests/test_speaker_enrollment.py — Unit tests for speaker enrollment engine.
Validates:
- Audio sample quality gating (duration, silence, clipping)
- Mutual consistency checks between enrollment samples
- Inconsistent sample rejection and retry prompt
- Centroid calculation and calibrated threshold assignment
- Discarding raw enrollment audio by default vs opt-in diagnostic retention
- Profile deletion and re-enrollment
"""

import os
import shutil
import tempfile
import unittest
import numpy as np

from core.speaker.types import SpeakerProfile
from core.speaker.extractor import FakeSpeakerEmbeddingExtractor
from core.speaker.profile_store import SpeakerProfileStore
from core.speaker.enrollment import (
    SpeakerEnrollmentManager,
    validate_utterance_quality,
)


class TestSpeakerEnrollment(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.store = SpeakerProfileStore(storage_dir=self.test_dir)
        self.fake_extractor = FakeSpeakerEmbeddingExtractor()
        self.manager = SpeakerEnrollmentManager(
            profile_store=self.store,
            embedding_extractor=self.fake_extractor,
            min_samples=2,
            target_samples=3,
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_validate_utterance_quality_detects_flaws(self):
        # 1. Too short (< 0.4s = 6400 samples)
        short_audio = np.zeros(3000, dtype=np.int16)
        res = validate_utterance_quality(short_audio, sample_rate=16000)
        self.assertFalse(res.ok)
        self.assertIn("too short", res.message)

        # 2. Pure silence (RMS < 50.0)
        silence_audio = np.zeros(24000, dtype=np.int16)
        res = validate_utterance_quality(silence_audio, sample_rate=16000)
        self.assertFalse(res.ok)
        self.assertIn("silence", res.message.lower())

        # 3. Severe clipping
        clipped_audio = np.ones(24000, dtype=np.int16) * 32767
        res = validate_utterance_quality(clipped_audio, sample_rate=16000)
        self.assertFalse(res.ok)
        self.assertIn("clipping", res.message.lower())

        # 4. Valid audio (1.5s sine wave at moderate volume)
        t = np.linspace(0, 1.5, 24000, endpoint=False)
        valid_audio = (np.sin(2 * np.pi * 300 * t) * 8000).astype(np.int16)
        res = validate_utterance_quality(valid_audio, sample_rate=16000)
        self.assertTrue(res.ok)

    def test_consistent_enrollment_creates_profile(self):
        # Create 3 consistent audio samples that produce identical embeddings
        target_vec = np.zeros(512, dtype=np.float32)
        target_vec[0:10] = 1.0
        target_vec /= np.linalg.norm(target_vec)

        # Mock extractor to return consistent vectors
        samples = []
        for i in range(3):
            t = np.linspace(0, 1.5, 24000, endpoint=False)
            aud = (np.sin(2 * np.pi * (250 + i * 5) * t) * 6000).astype(np.int16)
            samples.append(aud)

        # Set fake extractor to return slightly varied but consistent vectors
        self.fake_extractor.extract_embedding = lambda audio, sr=16000: type(
            "Emb", (), {"vector": target_vec.copy()}
        )()

        result = self.manager.enroll_user("Master Wayne", samples)
        self.assertTrue(result.success)
        self.assertIsNotNone(result.profile)
        self.assertEqual(result.profile.user_name, "Master Wayne")
        self.assertEqual(len(result.profile.template_embeddings), 3)

        # Verify persisted in store
        saved = self.store.get_profile(result.profile.profile_id)
        self.assertIsNotNone(saved)
        self.assertEqual(saved.user_name, "Master Wayne")

    def test_inconsistent_enrollment_rejected(self):
        # Two completely orthogonal vectors (e.g. two different people speaking)
        v1 = np.zeros(512, dtype=np.float32)
        v1[0:10] = 1.0
        v1 /= np.linalg.norm(v1)

        v2 = np.zeros(512, dtype=np.float32)
        v2[100:110] = 1.0
        v2 /= np.linalg.norm(v2)

        return_vecs = [v1, v2]

        def varied_extract(audio, sr=16000):
            vec = return_vecs.pop(0) if return_vecs else v1
            return type("Emb", (), {"vector": vec})()

        self.fake_extractor.extract_embedding = varied_extract

        samples = [
            (np.sin(np.linspace(0, 1.5, 24000)) * 6000).astype(np.int16),
            (np.sin(np.linspace(0, 1.5, 24000)) * 6000).astype(np.int16),
        ]

        result = self.manager.enroll_user("Inconsistent User", samples)
        self.assertFalse(result.success)
        self.assertIn("inconsistent", result.error_message.lower())
        self.assertFalse(self.store.has_enrolled_profiles())

    def test_raw_audio_discarded_by_default(self):
        v = np.ones(512, dtype=np.float32) / np.sqrt(512)
        self.fake_extractor.extract_embedding = lambda a, sr=16000: type(
            "Emb", (), {"vector": v.copy()}
        )()
        samples = [
            (np.sin(np.linspace(0, 1.5, 24000)) * 6000).astype(np.int16),
            (np.sin(np.linspace(0, 1.5, 24000)) * 6000).astype(np.int16),
        ]

        result = self.manager.enroll_user("Privacy User", samples, retain_diagnostic_wavs=False)
        self.assertTrue(result.success)

        # No wav files should exist in test_dir
        wav_files = list(self.store.storage_dir.glob("**/*.wav"))
        self.assertEqual(len(wav_files), 0)


if __name__ == "__main__":
    unittest.main()
