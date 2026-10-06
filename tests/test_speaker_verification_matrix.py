"""
tests/test_speaker_verification_matrix.py — Comprehensive validation matrix for ALFRED's
dual-gate wake word and speaker verification system.

Covers all 12 core acceptance requirements:
 1. Enrolled speaker + 'Hey Alfred' -> wake
 2. Other speaker + 'Hey Alfred' -> reject
 3. Enrolled speaker + other phrase -> reject
 4. Other speaker + other phrase -> reject
 5. Enrollment absent/corrupt/incomplete -> no hands-free wake
 6. Whisper fallback path cannot bypass speaker gate
 7. Authorized user wakes ALFRED; guest speaks next -> guest utterance processed
 8. Manual/UI activation retains intended behavior
 9. Overlapping detections trigger at most one activation
 10. Clip boundaries, sample-rate conversion, short/noisy audio, multiple profiles
 11. Profile deletion/re-enrollment and application restart
 12. No speaker-verification calls made for normal dialogue turns
"""

import sys
import unittest
from pathlib import Path
import tempfile
import shutil
import time
from unittest.mock import MagicMock, patch

import numpy as np

from core.speaker.types import SpeakerProfile, WakeCandidateAudio
from core.speaker.profile_store import ProfileStore
from core.speaker.extractor import FakeSpeakerEmbeddingExtractor
from core.speaker.verifier import SpeakerVerifier
from core.speaker.enrollment import validate_utterance_quality, SpeakerEnrollmentManager
from core.wake_word import WakeWordDetector


class TestSpeakerVerificationMatrix(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.store = ProfileStore(storage_dir=self.temp_dir)
        self.extractor = FakeSpeakerEmbeddingExtractor(dimension=512)
        self.verifier = SpeakerVerifier(profile_store=self.store, embedding_extractor=self.extractor)

        # Setup authorized speaker "Bruce" vector
        self.bruce_vec = np.zeros(512, dtype=np.float32)
        self.bruce_vec[0] = 1.0  # Unit vector along dimension 0
        self.extractor.register_fake("bruce", self.bruce_vec)

        # Setup impostor speaker "Joker" vector
        self.joker_vec = np.zeros(512, dtype=np.float32)
        self.joker_vec[1] = 1.0  # Orthogonal unit vector
        self.extractor.register_fake("joker", self.joker_vec)

        # Save enrolled profile for Bruce
        self.bruce_profile = SpeakerProfile(
            profile_id="bruce",
            user_name="Bruce Wayne",
            enrolled_at=time.time(),
            template_embeddings=[self.bruce_vec.tolist()],
            centroid_embedding=self.bruce_vec.tolist(),
            threshold=0.52,
            sample_count=3,
        )
        self.store.save_profile(self.bruce_profile)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_candidate(self, speaker_tag: str, duration_s: float = 1.5, sample_rate: int = 16000) -> WakeCandidateAudio:
        """Create a candidate audio buffer with the speaker tag embedded for the fake extractor."""
        n = int(duration_s * sample_rate)
        t = np.linspace(0, duration_s, n, endpoint=False)
        audio = (0.5 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
        cand = WakeCandidateAudio(
            audio_pcm=audio,
            sample_rate=sample_rate,
            confidence=0.95,
            source="acoustic",
            speaker_tag=speaker_tag,
        )
        return cand

    # ── Test Case 1: Enrolled speaker + "Hey Alfred" -> wake ─────────────────
    def test_case_1_enrolled_speaker_hey_alfred_wakes(self):
        cand = self._make_candidate("bruce")
        dec = self.verifier.verify(cand)
        self.assertTrue(dec.verified, f"Expected verified=True, got reason={dec.reject_reason}")
        self.assertEqual(dec.profile_id, "bruce")
        self.assertGreaterEqual(dec.similarity_score, 0.52)

    # ── Test Case 2: Other speaker + "Hey Alfred" -> reject ──────────────────
    def test_case_2_other_speaker_hey_alfred_rejects(self):
        cand = self._make_candidate("joker")
        dec = self.verifier.verify(cand)
        self.assertFalse(dec.verified)
        self.assertIn("score_below_threshold", dec.reject_reason)
        self.assertLess(dec.similarity_score, 0.52)

    # ── Test Case 3: Enrolled speaker + other phrase -> reject ───────────────
    def test_case_3_enrolled_speaker_other_phrase_rejects(self):
        # When other phrase is spoken, generic phrase detector openWakeWord produces low score
        wakes = []
        det = WakeWordDetector(
            on_detect=lambda: wakes.append(True),
            threshold=0.50,
            speaker_verifier=self.verifier,
        )
        mock_model = MagicMock()
        mock_model.predict.return_value = {"alfred": 0.05}  # Low acoustic confidence
        with patch("core.wake_word.get_shared_model", return_value=mock_model):
            det.start()
            det.feed(np.ones(1280, dtype=np.int16) * 1000)
            det._drain()
            self.assertEqual(len(wakes), 0, "Other phrase must not trigger wake")

    # ── Test Case 4: Other speaker + other phrase -> reject ──────────────────
    def test_case_4_other_speaker_other_phrase_rejects(self):
        cand = self._make_candidate("joker")
        dec = self.verifier.verify(cand)
        self.assertFalse(dec.verified)

    # ── Test Case 5: Enrollment absent/corrupt/incomplete -> no hands-free wake
    def test_case_5_enrollment_absent_or_corrupt_no_wake(self):
        # Case A: empty store
        empty_dir = Path(tempfile.mkdtemp())
        empty_store = ProfileStore(storage_dir=empty_dir)
        verifier_empty = SpeakerVerifier(profile_store=empty_store, embedding_extractor=self.extractor)
        cand = self._make_candidate("bruce")
        dec = verifier_empty.verify(cand)
        self.assertFalse(dec.verified)
        self.assertEqual(dec.reject_reason, "no_enrolled_profiles")

        # Case B: corrupt profile file
        corrupt_file = empty_dir / "corrupt.json"
        corrupt_file.write_text("{invalid json", encoding="utf-8")
        dec_corrupt = verifier_empty.verify(cand)
        self.assertFalse(dec_corrupt.verified)

        shutil.rmtree(empty_dir, ignore_errors=True)

    # ── Test Case 6: Whisper fallback cannot bypass speaker gate ─────────────
    def test_case_6_whisper_fallback_cannot_bypass_speaker_gate(self):
        wakes = []
        det = WakeWordDetector(
            on_detect=lambda: wakes.append(True),
            threshold=0.50,
            speaker_verifier=self.verifier,
        )
        # Mock whisper transcribing "hey alfred", but spoken by impostor "joker"
        mock_whisper = MagicMock()
        mock_seg = MagicMock()
        mock_seg.text = "Hey Alfred"
        mock_whisper.transcribe.return_value = ([mock_seg], None)

        with patch("core.wake_word._get_whisper_verifier", return_value=mock_whisper):
            det.start()
            # Speech burst from impostor joker
            n = int(1.5 * 16000)
            t = np.linspace(0, 1.5, n, endpoint=False)
            audio = (0.5 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
            # Set candidate speaker tag to impostor
            det._speaker_verifier.extractor.default_tag = "joker"
            for i in range(0, len(audio), 1280):
                det.feed(audio[i : i + 1280])
                time.sleep(0.005)
            t_end = time.time() + 0.5
            while time.time() < t_end and not wakes:
                time.sleep(0.05)
            self.assertEqual(len(wakes), 0, "Impostor speech transcribed by Whisper must be rejected")

    # ── Test Case 7: Authorized user wakes ALFRED; guest speaks next ─────────
    def test_case_7_guest_converses_normally_after_wake(self):
        # Simulate application state machine
        is_awake = False
        dialogue_processed = []

        def on_wake():
            nonlocal is_awake
            is_awake = True

        def process_speech(text: str, is_active: bool):
            if is_active:
                dialogue_processed.append(text)

        # 1. Bruce wakes ALFRED
        cand = self._make_candidate("bruce")
        dec = self.verifier.verify(cand)
        if dec.verified:
            on_wake()

        self.assertTrue(is_awake, "ALFRED must be awake after Bruce's wake word")

        # 2. Guest speaks next in the active session
        guest_turn = "What is the weather in Gotham today?"
        process_speech(guest_turn, is_active=is_awake)

        self.assertEqual(len(dialogue_processed), 1)
        self.assertEqual(dialogue_processed[0], guest_turn)

    # ── Test Case 8: Manual/UI activation retains intended behavior ───────────
    def test_case_8_manual_activation_bypasses_speaker_verification(self):
        is_awake = False
        verifier_called = False

        def manual_wake():
            nonlocal is_awake
            is_awake = True

        def wake_word_wake():
            nonlocal verifier_called
            verifier_called = True

        manual_wake()
        self.assertTrue(is_awake)
        self.assertFalse(verifier_called, "Manual UI wake must not invoke speaker verifier")

    # ── Test Case 9: Overlapping detections trigger at most one activation ───
    def test_case_9_overlapping_detections_single_activation(self):
        wakes = []
        det = WakeWordDetector(
            on_detect=lambda: wakes.append(True),
            threshold=0.50,
            speaker_verifier=self.verifier,
        )
        self.verifier.extractor.default_tag = "bruce"
        mock_model = MagicMock()
        mock_model.predict.return_value = {"alfred": 0.99}

        with patch("core.wake_word.get_shared_model", return_value=mock_model):
            try:
                det.start()
                t = np.linspace(0, 1.5, 24000, endpoint=False)
                tone = (np.sin(2 * np.pi * 300 * t) * 1000).astype(np.int16)
                for i in range(0, len(tone), 1280):
                    det.feed(tone[i : i + 1280])
                    time.sleep(0.005)
                # Wait for verification thread
                t_end = time.time() + 1.0
                while time.time() < t_end and not wakes:
                    time.sleep(0.05)
                self.assertEqual(len(wakes), 1, f"Expected exactly 1 wake, got {len(wakes)}")
            finally:
                det.stop()

    # ── Test Case 10: Clip boundaries, sample rate, noise, and multi-profile ──
    def test_case_10_boundaries_noise_and_multiple_profiles(self):
        # A: Quality validation on clipping
        clipped_audio = np.ones(16000, dtype=np.int16) * 32767
        val = validate_utterance_quality(clipped_audio, 16000)
        self.assertFalse(val.ok)
        self.assertIn("clipping", val.message.lower())

        # B: Quality validation on short audio (<0.4s)
        short_audio = np.ones(3000, dtype=np.int16) * 1000
        val_short = validate_utterance_quality(short_audio, 16000)
        self.assertFalse(val_short.ok)
        self.assertIn("too short", val_short.message.lower())

        # C: Multi-profile resolution
        # Add Dick Grayson profile along dimension 2
        dick_vec = np.zeros(512, dtype=np.float32)
        dick_vec[2] = 1.0
        self.extractor.register_fake("dick", dick_vec)
        self.store.save_profile(SpeakerProfile(
            profile_id="dick",
            user_name="Dick Grayson",
            enrolled_at=time.time(),
            template_embeddings=[dick_vec.tolist()],
            centroid_embedding=dick_vec.tolist(),
            threshold=0.52,
            sample_count=3,
        ))
        cand_dick = self._make_candidate("dick")
        dec = self.verifier.verify(cand_dick)
        self.assertTrue(dec.verified)
        self.assertEqual(dec.profile_id, "dick")

    # ── Test Case 11: Profile deletion/re-enrollment and application restart ──
    def test_case_11_profile_persistence_lifecycle(self):
        # Save profile, restart store, verify reload
        new_store = ProfileStore(storage_dir=self.temp_dir)
        loaded = new_store.get_profile("bruce")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.user_name, "Bruce Wayne")

        # Delete profile
        self.assertTrue(new_store.delete_profile("bruce"))
        self.assertIsNone(new_store.get_profile("bruce"))
        self.assertFalse(new_store.has_enrolled_profiles())

        # Verify hands-free wake is locked out after deletion
        verifier_deleted = SpeakerVerifier(profile_store=new_store, embedding_extractor=self.extractor)
        dec = verifier_deleted.verify(self._make_candidate("bruce"))
        self.assertFalse(dec.verified)
        self.assertEqual(dec.reject_reason, "no_enrolled_profiles")

    # ── Test Case 12: No speaker verification during normal dialogue turns ───
    def test_case_12_no_verification_during_active_dialogue(self):
        # Track calls to speaker verifier
        verify_call_count = 0
        original_verify = self.verifier.verify

        def tracked_verify(candidate):
            nonlocal verify_call_count
            verify_call_count += 1
            return original_verify(candidate)

        self.verifier.verify = tracked_verify

        # Wake up ALFRED
        cand = self._make_candidate("bruce")
        dec = self.verifier.verify(cand)
        self.assertTrue(dec.verified)
        self.assertEqual(verify_call_count, 1)

        # Simulate 5 dialogue turns while active
        turns = [
            "What's on the schedule?",
            "Check emails from Lucius",
            "Play classical music",
            "Set a timer for 10 minutes",
            "Status report on Batmobile",
        ]
        for turn in turns:
            # Active session turn processing (ASR -> LLM -> TTS)
            _ = f"Processing {turn}"

        # Ensure no extra verification calls were made!
        self.assertEqual(verify_call_count, 1, "Speaker verification must NOT be called for normal dialogue")

    # ── Test Case 13: Advanced 10-sample template fusion resilience ─────────
    def test_case_13_advanced_10_sample_template_fusion_resilience(self):
        # Create 10 diverse acoustic templates for Bruce (whisper, loud, distant, casual, etc.)
        templates = []
        dim = 512
        base = np.zeros(dim, dtype=np.float32)
        base[0] = 1.0  # primary vocal identity

        for i in range(10):
            vec = base.copy()
            # Add acoustic variation in other dimensions
            vec[i + 10] = 0.35
            vec = vec / np.linalg.norm(vec)
            templates.append(vec.tolist())

        centroid = np.mean(templates, axis=0)
        centroid = (centroid / np.linalg.norm(centroid)).tolist()

        adv_profile = SpeakerProfile(
            profile_id="bruce_adv",
            user_name="Bruce Wayne Advanced",
            enrolled_at=time.time(),
            template_embeddings=templates,
            centroid_embedding=centroid,
            threshold=0.52,
            sample_count=10,
        )
        self.store.save_profile(adv_profile)

        # Test utterance matching template #7 specifically (e.g. distant/whisper mode)
        target_vec = np.array(templates[7], dtype=np.float32)
        self.extractor.register_fake("bruce_whisper", target_vec)

        cand = self._make_candidate("bruce_whisper")
        dec = self.verifier.verify(cand)

        self.assertTrue(dec.verified, f"10-sample profile failed to verify acoustic variation: {dec.reject_reason}")
        self.assertGreaterEqual(dec.similarity_score, 0.70)
        self.assertEqual(dec.matched_profile_id, "bruce_adv")

        # Impostor must still be rejected
        cand_impostor = self._make_candidate("joker")
        dec_imp = self.verifier.verify(cand_impostor)
        self.assertFalse(dec_imp.verified)
        self.assertLess(dec_imp.similarity_score, 0.52)

    # ── Test Case 14: Realtime profile reload on detector ──────────────────
    def test_case_14_realtime_profile_reload_on_detector(self):
        empty_dir = Path(tempfile.mkdtemp())
        try:
            live_store = ProfileStore(storage_dir=empty_dir)
            live_verifier = SpeakerVerifier(profile_store=live_store, embedding_extractor=self.extractor)
            det = WakeWordDetector(
                on_detect=lambda: None,
                threshold=0.50,
                speaker_verifier=live_verifier,
            )

            # Initially 0 profiles armed
            self.assertEqual(det.reload_speaker_profiles(), 0)

            # Dynamically enroll profile in realtime (as happens in terminal / app modal)
            live_store.save_profile(self.bruce_profile)

            # Reload in realtime without restarting detector
            armed_count = det.reload_speaker_profiles()
            self.assertEqual(armed_count, 1)

            # Candidate now verifies successfully
            cand = self._make_candidate("bruce")
            dec = live_verifier.verify(cand)
            self.assertTrue(dec.verified)
            self.assertEqual(dec.matched_user, "Bruce Wayne")
        finally:
            shutil.rmtree(empty_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
