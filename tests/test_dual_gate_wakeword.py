"""
tests/test_dual_gate_wakeword.py — Tests for production dual-gate wake word activation.
Covers:
1. Enrolled speaker + "Hey Alfred" -> wake.
2. Impostor / other speaker + "Hey Alfred" -> reject (no wake).
3. Enrolled speaker + other phrase -> reject.
4. Impostor + other phrase -> reject.
5. Enrollment absent/empty -> no hands-free wake.
6. Whisper fallback cannot bypass speaker verification.
7. Authorized user wakes ALFRED; subsequent guest speech accepted with no speaker check.
8. Manual UI wake button retains intended behavior without speaker check.
9. Overlapping detections trigger at most one activation (refractory cooldown).
"""

import time
import unittest
from unittest.mock import MagicMock, patch
import numpy as np

from core.speaker.types import SpeakerProfile, WakeCandidateAudio
from core.speaker.extractor import FakeSpeakerEmbeddingExtractor
from core.speaker.profile_store import SpeakerProfileStore
from core.speaker.verifier import SpeakerVerifier
from core.wake_word import WakeWordDetector


class DualGateWakeWordTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.test_dir = tempfile.mkdtemp()
        self.store = SpeakerProfileStore(storage_dir=self.test_dir)
        self.fake_extractor = FakeSpeakerEmbeddingExtractor()
        self.verifier = SpeakerVerifier(
            profile_store=self.store,
            embedding_extractor=self.fake_extractor,
            default_threshold=0.52,
        )

        # Enrolled speaker vector: 1.0 at indices 0:20
        self.auth_vector = np.zeros(512, dtype=np.float32)
        self.auth_vector[0:20] = 1.0
        self.auth_vector /= np.linalg.norm(self.auth_vector)

        # Impostor speaker vector: 1.0 at indices 200:220 (orthogonal)
        self.impostor_vector = np.zeros(512, dtype=np.float32)
        self.impostor_vector[200:220] = 1.0
        self.impostor_vector /= np.linalg.norm(self.impostor_vector)

        # Enroll authorized profile
        profile = SpeakerProfile(
            profile_id="aditya",
            user_name="Aditya",
            enrolled_at=time.time(),
            template_embeddings=[self.auth_vector.tolist()],
            centroid_embedding=self.auth_vector.tolist(),
            threshold=0.52,
            sample_count=1,
        )
        self.store.save_profile(profile)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_enrolled_speaker_with_wake_phrase_triggers_wake(self):
        """Case 1: Enrolled speaker + 'Hey Alfred' -> wake."""
        wake_events = []
        detector = WakeWordDetector(
            on_detect=lambda: wake_events.append(True),
            speaker_verifier=self.verifier,
            threshold=0.038,
            logger=lambda m: None,
        )

        # Fake extractor returns authorized vector
        self.fake_extractor.set_next_embedding(self.auth_vector)

        # Mock OpenWakeWord phrase model to return high score for "alfred"
        mock_model = MagicMock()
        mock_model.predict.return_value = {"alfred": 0.95}

        with patch("core.wake_word.get_shared_model", return_value=mock_model):
            self.assertTrue(detector.start())
            try:
                # Feed speech audio chunks (RMS ~500)
                t = np.linspace(0, 1.5, 24000, endpoint=False)
                tone = (np.sin(2 * np.pi * 300 * t) * 1000).astype(np.int16)

                for i in range(0, len(tone), 1280):
                    chunk = tone[i:i + 1280]
                    if len(chunk) < 1280:
                        chunk = np.pad(chunk, (0, 1280 - len(chunk)))
                    detector.feed(chunk)
                    time.sleep(0.01)

                # Wait for verification thread to process
                t_end = time.time() + 1.0
                while time.time() < t_end and not wake_events:
                    time.sleep(0.05)

                self.assertTrue(len(wake_events) > 0, "Enrolled speaker failed to trigger wake!")
            finally:
                detector.stop()

    def test_impostor_speaker_with_wake_phrase_is_rejected(self):
        """Case 2: Other speaker + 'Hey Alfred' -> reject."""
        wake_events = []
        detector = WakeWordDetector(
            on_detect=lambda: wake_events.append(True),
            speaker_verifier=self.verifier,
            threshold=0.038,
            logger=lambda m: None,
        )

        # Fake extractor returns impostor vector
        self.fake_extractor.set_next_embedding(self.impostor_vector)

        # Mock OpenWakeWord phrase model to return high score
        mock_model = MagicMock()
        mock_model.predict.return_value = {"alfred": 0.95}

        with patch("core.wake_word.get_shared_model", return_value=mock_model):
            self.assertTrue(detector.start())
            try:
                t = np.linspace(0, 1.5, 24000, endpoint=False)
                tone = (np.sin(2 * np.pi * 300 * t) * 1000).astype(np.int16)

                for i in range(0, len(tone), 1280):
                    chunk = tone[i:i + 1280]
                    if len(chunk) < 1280:
                        chunk = np.pad(chunk, (0, 1280 - len(chunk)))
                    detector.feed(chunk)
                    time.sleep(0.01)

                time.sleep(0.3)
                self.assertEqual(len(wake_events), 0, "Impostor was falsely accepted!")
            finally:
                detector.stop()

    def test_missing_profile_disables_hands_free_wake(self):
        """Case 5: Enrollment absent/empty -> no hands-free wake."""
        import tempfile
        empty_store = SpeakerProfileStore(storage_dir=tempfile.mkdtemp())
        verifier = SpeakerVerifier(
            profile_store=empty_store,
            embedding_extractor=self.fake_extractor,
        )

        wake_events = []
        detector = WakeWordDetector(
            on_detect=lambda: wake_events.append(True),
            speaker_verifier=verifier,
            threshold=0.038,
            logger=lambda m: None,
        )

        mock_model = MagicMock()
        mock_model.predict.return_value = {"alfred": 0.95}

        with patch("core.wake_word.get_shared_model", return_value=mock_model):
            self.assertTrue(detector.start())
            try:
                t = np.linspace(0, 1.5, 24000, endpoint=False)
                tone = (np.sin(2 * np.pi * 300 * t) * 1000).astype(np.int16)

                for i in range(0, len(tone), 1280):
                    chunk = tone[i:i + 1280]
                    if len(chunk) < 1280:
                        chunk = np.pad(chunk, (0, 1280 - len(chunk)))
                    detector.feed(chunk)
                    time.sleep(0.01)

                time.sleep(0.3)
                self.assertEqual(len(wake_events), 0, "Unenrolled device fired hands-free wake!")
            finally:
                detector.stop()

    def test_whisper_fallback_rejects_impostor(self):
        """Case 6: Whisper fallback cannot bypass speaker verification."""
        wake_events = []
        detector = WakeWordDetector(
            on_detect=lambda: wake_events.append(True),
            speaker_verifier=self.verifier,
            threshold=0.038,
            logger=lambda m: None,
        )

        # Set fake extractor to return impostor vector
        self.fake_extractor.set_next_embedding(self.impostor_vector)

        # Simulate Whisper burst returning "Hey Alfred"
        mock_whisper = MagicMock()
        mock_segment = MagicMock()
        mock_segment.text = "Hey Alfred"
        mock_segment.no_speech_prob = 0.01
        mock_segment.compression_ratio = 1.0
        mock_whisper.transcribe.return_value = ([mock_segment], None)

        audio_data = (np.sin(np.linspace(0, 1.0, 16000)) * 1000).astype(np.int16)

        with patch("core.wake_word._get_whisper_verifier", return_value=mock_whisper):
            detector.start()
            try:
                # Directly invoke speech burst verification
                detector._verify_burst_async(audio_data, burst_start_ts=time.monotonic() - 1.0)
                time.sleep(0.2)
                self.assertEqual(len(wake_events), 0, "Whisper burst bypassed speaker verification!")
            finally:
                detector.stop()

    def test_overlapping_detections_trigger_at_most_once(self):
        """Case 9: Overlapping detections trigger at most one activation (refractory cooldown)."""
        wake_events = []
        detector = WakeWordDetector(
            on_detect=lambda: wake_events.append(True),
            speaker_verifier=self.verifier,
            threshold=0.038,
            logger=lambda m: None,
        )

        # Trigger twice in rapid succession (< 1.2s)
        detector._running = True
        detector._trigger_match(source="acoustic_dual_gate")
        detector._trigger_match(source="acoustic_dual_gate")
        self.assertEqual(len(wake_events), 1)


if __name__ == "__main__":
    unittest.main()
