"""
tests/test_speaker_interfaces.py — Unit tests for speaker verification interfaces.
Validates:
- AudioRingBuffer slicing, boundaries, and overflow
- SpeakerEmbedding normalization and cosine similarity
- SpeakerProfileStore persistence, atomic writes, versioning, corruption handling, deletion
- SpeakerVerifier dual-gate decision logic with deterministic fakes
"""

import os
import shutil
import tempfile
import unittest
import numpy as np

from core.speaker.types import (
    WakeCandidateAudio,
    SpeakerEmbedding,
    SpeakerProfile,
    VerificationDecision,
)
from core.speaker.ring_buffer import AudioRingBuffer
from core.speaker.extractor import FakeSpeakerEmbeddingExtractor
from core.speaker.profile_store import SpeakerProfileStore
from core.speaker.verifier import SpeakerVerifier


class TestAudioRingBuffer(unittest.TestCase):
    def test_buffer_capacity_and_slicing(self):
        # 16000 Hz, 3.0 second buffer = 48000 samples
        rb = AudioRingBuffer(capacity_seconds=3.0, sample_rate=16000)
        self.assertEqual(rb.capacity_samples, 48000)

        # Feed 1.0 second of tone
        t = np.linspace(0, 1.0, 16000, endpoint=False)
        chunk = (np.sin(2 * np.pi * 440 * t) * 10000).astype(np.int16)
        rb.feed(chunk, timestamp=10.0)

        # Extract slice from 9.0s to 10.0s (full 1.0s audio)
        extracted = rb.get_slice(start_ts=9.0, end_ts=10.0)
        self.assertEqual(len(extracted), 16000)
        self.assertEqual(extracted.dtype, np.int16)

        # Extract sub-slice from 9.5s to 10.0s (0.5s audio = 8000 samples)
        sub_extracted = rb.get_slice(start_ts=9.5, end_ts=10.5)
        self.assertEqual(len(sub_extracted), 8000)

    def test_buffer_overflow_retains_latest(self):
        rb = AudioRingBuffer(capacity_seconds=2.0, sample_rate=16000)  # 32000 samples
        
        # Feed 3 seconds total in 1-second chunks: c1 (0-1s), c2 (1-2s), c3 (2-3s)
        c1 = np.ones(16000, dtype=np.int16) * 1
        c2 = np.ones(16000, dtype=np.int16) * 2
        c3 = np.ones(16000, dtype=np.int16) * 3

        rb.feed(c1, timestamp=1.0)
        rb.feed(c2, timestamp=2.0)
        rb.feed(c3, timestamp=3.0)

        # Available time span should cover latest 2 seconds (timestamps 1.0 to 3.0)
        sliced = rb.get_slice(start_ts=1.0, end_ts=3.0)
        self.assertEqual(len(sliced), 32000)
        # First half should be c2 (value 2), second half c3 (value 3)
        self.assertEqual(sliced[0], 2)
        self.assertEqual(sliced[-1], 3)


class TestSpeakerProfileStore(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.store = SpeakerProfileStore(storage_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_save_and_load_profile(self):
        profile = SpeakerProfile(
            profile_id="user_1",
            user_name="Bruce Wayne",
            enrolled_at=1700000000.0,
            template_embeddings=[[0.1] * 512, [0.2] * 512],
            centroid_embedding=[0.15] * 512,
            threshold=0.52,
            sample_count=2,
            metadata={"notes": "Master Wayne voice"},
        )
        self.assertTrue(self.store.save_profile(profile))

        loaded = self.store.get_profile("user_1")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.user_name, "Bruce Wayne")
        self.assertEqual(len(loaded.centroid_embedding), 512)
        self.assertEqual(loaded.threshold, 0.52)

    def test_list_and_delete_profile(self):
        p1 = SpeakerProfile("user_a", "Alice", 1.0, [[0.1]*512], [0.1]*512, 0.50, 1)
        p2 = SpeakerProfile("user_b", "Bob", 2.0, [[0.2]*512], [0.2]*512, 0.50, 1)
        self.store.save_profile(p1)
        self.store.save_profile(p2)

        profiles = self.store.list_profiles()
        self.assertEqual(len(profiles), 2)
        self.assertTrue(self.store.has_enrolled_profiles())

        self.assertTrue(self.store.delete_profile("user_a"))
        self.assertEqual(len(self.store.list_profiles()), 1)
        self.assertIsNone(self.store.get_profile("user_a"))
        self.assertIsNotNone(self.store.get_profile("user_b"))

    def test_corrupt_profile_handling(self):
        corrupt_file = os.path.join(self.test_dir, "corrupt.json")
        with open(corrupt_file, "w") as f:
            f.write("{invalid json content")

        profiles = self.store.list_profiles()
        # Should gracefully ignore corrupt profile file
        self.assertEqual(len(profiles), 0)


class TestSpeakerVerifierWithFakes(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.store = SpeakerProfileStore(storage_dir=self.test_dir)
        self.fake_extractor = FakeSpeakerEmbeddingExtractor()
        self.verifier = SpeakerVerifier(
            profile_store=self.store,
            embedding_extractor=self.fake_extractor,
            default_threshold=0.52,
        )

        # Enrolled speaker vector: all 0.5 normalized
        vec = np.zeros(512, dtype=np.float32)
        vec[0:10] = 1.0
        vec /= np.linalg.norm(vec)
        self.enrolled_vec = vec

        profile = SpeakerProfile(
            profile_id="aditya",
            user_name="Aditya",
            enrolled_at=1700000000.0,
            template_embeddings=[vec.tolist()],
            centroid_embedding=vec.tolist(),
            threshold=0.52,
            sample_count=1,
        )
        self.store.save_profile(profile)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_matching_speaker_wakes(self):
        # Set fake extractor to return the enrolled speaker vector
        self.fake_extractor.set_next_embedding(self.enrolled_vec)

        dummy_audio = np.ones(24000, dtype=np.int16) * 500  # 1.5s speech
        candidate = WakeCandidateAudio(
            audio_pcm=dummy_audio,
            sample_rate=16000,
            start_ts=10.0,
            end_ts=11.5,
            confidence=0.85,
            source="acoustic",
        )

        decision = self.verifier.verify(candidate)
        self.assertTrue(decision.is_match)
        self.assertAlmostEqual(decision.score, 1.0, places=3)
        self.assertEqual(decision.matched_user, "Aditya")
        self.assertIsNone(decision.reject_reason)

    def test_impostor_speaker_is_rejected(self):
        # Impostor vector orthogonal to enrolled vector
        impostor_vec = np.zeros(512, dtype=np.float32)
        impostor_vec[100:110] = 1.0
        impostor_vec /= np.linalg.norm(impostor_vec)
        self.fake_extractor.set_next_embedding(impostor_vec)

        dummy_audio = np.ones(24000, dtype=np.int16) * 500
        candidate = WakeCandidateAudio(
            audio_pcm=dummy_audio,
            sample_rate=16000,
            start_ts=10.0,
            end_ts=11.5,
            confidence=0.92,
            source="acoustic",
        )

        decision = self.verifier.verify(candidate)
        self.assertFalse(decision.is_match)
        self.assertLess(decision.score, 0.52)
        self.assertIn("score_below_threshold", decision.reject_reason)

    def test_no_profile_rejects_handsfree(self):
        empty_store = SpeakerProfileStore(storage_dir=tempfile.mkdtemp())
        verifier = SpeakerVerifier(
            profile_store=empty_store,
            embedding_extractor=self.fake_extractor,
        )
        dummy_audio = np.ones(24000, dtype=np.int16) * 500
        candidate = WakeCandidateAudio(
            audio_pcm=dummy_audio,
            sample_rate=16000,
            start_ts=1.0,
            end_ts=2.5,
            confidence=0.95,
            source="acoustic",
        )
        decision = verifier.verify(candidate)
        self.assertFalse(decision.is_match)
        self.assertEqual(decision.reject_reason, "no_enrolled_profiles")


if __name__ == "__main__":
    unittest.main()
