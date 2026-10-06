"""
core/speaker/enrollment.py — Voice enrollment engine with quality gating and consistency checks.
"""

from __future__ import annotations

import dataclasses
import logging
from pathlib import Path
import time
from typing import Dict, List, Optional, Tuple
import numpy as np

from core.speaker.types import SpeakerProfile
from core.speaker.extractor import SpeakerEmbeddingExtractor, CampplusOnnxExtractor
from core.speaker.profile_store import SpeakerProfileStore

_LOGGER = logging.getLogger("core.speaker.enrollment")

MIN_DURATION_S = 0.40
MAX_DURATION_S = 4.00
MIN_SPEECH_RMS = 50.0
MAX_CLIPPING_RATIO = 0.01
MIN_PAIRWISE_CONSISTENCY = 0.40


@dataclasses.dataclass(frozen=True)
class QualityValidationResult:
    ok: bool
    message: str
    duration_s: float = 0.0
    rms_energy: float = 0.0


@dataclasses.dataclass
class EnrollmentResult:
    success: bool
    profile: Optional[SpeakerProfile] = None
    error_message: Optional[str] = None
    pairwise_similarities: List[float] = dataclasses.field(default_factory=list)


def validate_utterance_quality(
    audio_pcm: np.ndarray, sample_rate: int = 16000
) -> QualityValidationResult:
    """Validate that a recorded utterance contains clean, unclipped, sufficient speech."""
    if audio_pcm is None or len(audio_pcm) == 0:
        return QualityValidationResult(ok=False, message="Empty audio recording.")

    raw = np.asarray(audio_pcm).flatten()
    if np.issubdtype(raw.dtype, np.floating):
        if np.max(np.abs(raw)) <= 1.05:
            arr = np.clip(raw * 32767.0, -32768, 32767).astype(np.int16)
        else:
            arr = np.clip(raw, -32768, 32767).astype(np.int16)
    else:
        arr = raw.astype(np.int16)
    duration_s = float(len(arr)) / float(sample_rate)

    if duration_s < MIN_DURATION_S:
        return QualityValidationResult(
            ok=False,
            message=f"Utterance too short ({duration_s:.2f}s < {MIN_DURATION_S:.2f}s). Speak clearly for the full phrase.",
            duration_s=duration_s,
        )

    if duration_s > MAX_DURATION_S:
        return QualityValidationResult(
            ok=False,
            message=f"Utterance too long ({duration_s:.2f}s > {MAX_DURATION_S:.2f}s).",
            duration_s=duration_s,
        )

    rms = float(np.sqrt(np.mean(arr.astype(np.float32) ** 2)))
    if rms < MIN_SPEECH_RMS:
        return QualityValidationResult(
            ok=False,
            message=f"Recording detected as silence or whisper (RMS={rms:.1f} < {MIN_SPEECH_RMS:.1f}). Please speak up.",
            duration_s=duration_s,
            rms_energy=rms,
        )

    clipped_count = int(np.sum(np.abs(arr) >= 32700))
    clip_ratio = float(clipped_count) / float(len(arr))
    if clip_ratio > MAX_CLIPPING_RATIO:
        return QualityValidationResult(
            ok=False,
            message=f"Microphone clipping detected ({clip_ratio*100:.1f}% samples clipped). Lower microphone input volume.",
            duration_s=duration_s,
            rms_energy=rms,
        )

    return QualityValidationResult(
        ok=True,
        message="Recording quality verified.",
        duration_s=duration_s,
        rms_energy=rms,
    )


class SpeakerEnrollmentManager:
    """Orchestrates 2-3 clip voice enrollment, consistency calibration, and profile generation."""

    def __init__(
        self,
        profile_store: Optional[SpeakerProfileStore] = None,
        embedding_extractor: Optional[SpeakerEmbeddingExtractor] = None,
        extractor: Optional[SpeakerEmbeddingExtractor] = None,
        min_samples: int = 2,
        target_samples: int = 3,
    ) -> None:
        self.store = profile_store or SpeakerProfileStore()
        self.extractor = extractor or embedding_extractor or CampplusOnnxExtractor()
        self.min_samples = max(2, min_samples)
        self.target_samples = max(self.min_samples, target_samples)
        self._sessions: Dict[str, List[np.ndarray]] = {}
        self._session_embeddings: Dict[str, List[np.ndarray]] = {}

    def set_target_samples(self, target_samples: int) -> None:
        """Update target sample count (e.g. 3 for standard, 10 for advanced)."""
        self.target_samples = max(self.min_samples, target_samples)

    def reset_session(self, user_name: str) -> None:
        """Reset incremental enrollment session for a user."""
        clean_name = user_name.strip()
        self._sessions.pop(clean_name, None)
        self._session_embeddings.pop(clean_name, None)

    def add_sample(self, user_name: str, audio: np.ndarray, sample_rate: int = 16000) -> tuple[bool, str]:
        """Validate, extract, and append a single enrollment sample incrementally."""
        clean_name = user_name.strip()
        if not clean_name:
            return False, "User name cannot be empty."

        # Validate quality
        val = validate_utterance_quality(audio, sample_rate)
        if not val.ok:
            return False, val.message

        # Extract embedding
        try:
            emb = self.extractor.extract_embedding(audio, sample_rate)
        except Exception as exc:
            return False, f"Failed to extract speaker embedding: {exc}"

        current_embs = self._session_embeddings.setdefault(clean_name, [])
        # Check consistency against previously accepted samples in this session
        # For advanced multi-sample calibration (e.g. 10 samples), allow acoustic variations (down to 0.32)
        if len(current_embs) >= 6:
            pairwise_min = 0.32
        elif len(current_embs) >= 3:
            pairwise_min = 0.35
        else:
            pairwise_min = MIN_PAIRWISE_CONSISTENCY
        for idx, prev in enumerate(current_embs, start=1):
            sim = float(np.dot(emb.vector, prev))
            if sim < pairwise_min:
                return False, f"Inconsistent with sample {idx} (similarity {sim:.2f} < {pairwise_min:.2f}). Please repeat the phrase."

        current_embs.append(emb.vector)
        self._sessions.setdefault(clean_name, []).append(audio)
        return True, f"Sample {len(current_embs)} accepted."

    def build_profile(self, user_name: str, retain_diagnostic_wavs: bool = False) -> SpeakerProfile:
        """Build and return calibrated SpeakerProfile from accumulated session samples."""
        clean_name = user_name.strip()
        samples = self._sessions.get(clean_name, [])
        if len(samples) < self.min_samples:
            raise ValueError(f"At least {self.min_samples} samples required to build profile (had {len(samples)}).")

        res = self.enroll_user(clean_name, samples, retain_diagnostic_wavs=retain_diagnostic_wavs)
        if not res.success or res.profile is None:
            raise RuntimeError(res.error_message or "Failed to build profile.")
        return res.profile

    def enroll_user(
        self,
        user_name: str,
        audio_samples: List[np.ndarray],
        sample_rate: int = 16000,
        retain_diagnostic_wavs: bool = False,
    ) -> EnrollmentResult:
        """Enroll a user using 2-3 clean 'Hey Alfred' utterances."""
        clean_name = user_name.strip()
        if not clean_name:
            return EnrollmentResult(success=False, error_message="User name cannot be empty.")

        if len(audio_samples) < self.min_samples:
            return EnrollmentResult(
                success=False,
                error_message=f"At least {self.min_samples} samples required for enrollment (received {len(audio_samples)}).",
            )

        # 1. Quality validation on each sample
        for idx, sample in enumerate(audio_samples, start=1):
            val = validate_utterance_quality(sample, sample_rate)
            if not val.ok:
                return EnrollmentResult(
                    success=False,
                    error_message=f"Sample {idx} failed quality check: {val.message}",
                )

        # 2. Extract embeddings
        embeddings = []
        for sample in audio_samples:
            try:
                emb = self.extractor.extract_embedding(sample, sample_rate)
                embeddings.append(emb.vector)
            except Exception as e:
                return EnrollmentResult(
                    success=False,
                    error_message=f"Failed to extract speaker embedding: {e}",
                )

        # 3. Check mutual consistency between samples
        pairwise_sims = []
        n = len(embeddings)
        pairwise_min = 0.32 if n >= 7 else (0.35 if n > 3 else MIN_PAIRWISE_CONSISTENCY)
        for i in range(n):
            for j in range(i + 1, n):
                sim = float(np.dot(embeddings[i], embeddings[j]))
                pairwise_sims.append(sim)
                if sim < pairwise_min:
                    return EnrollmentResult(
                        success=False,
                        error_message=(
                            f"Inconsistent voice samples detected (similarity between sample {i+1} "
                            f"and {j+1} is {sim:.2f} < {pairwise_min:.2f}). "
                            "Ensure the same person speaks all enrollment phrases in a consistent tone."
                        ),
                        pairwise_similarities=pairwise_sims,
                    )

        # 4. Compute centroid embedding
        centroid = np.mean(embeddings, axis=0)
        c_norm = np.linalg.norm(centroid)
        if c_norm > 0:
            centroid = centroid / c_norm

        # 5. Calibrate threshold: based on average consistency, clamped between 0.48 and 0.58
        avg_sim = float(np.mean(pairwise_sims)) if pairwise_sims else 0.55
        calibrated_thresh = float(np.clip(avg_sim * 0.85, 0.48, 0.58))

        profile_id = clean_name.lower().replace(" ", "_")
        profile = SpeakerProfile(
            profile_id=profile_id,
            user_name=clean_name,
            enrolled_at=time.time(),
            template_embeddings=[e.tolist() for e in embeddings],
            centroid_embedding=centroid.tolist(),
            threshold=calibrated_thresh,
            sample_count=len(embeddings),
            metadata={"avg_pairwise_sim": avg_sim, "model": "campplus"},
        )

        # 6. Auto-persist positive enrollment WAVs to training dataset so real-time enrollment
        # organically accumulates positive wake clips without requiring IDE recording tools
        try:
            pos_dir = Path(__file__).resolve().parent.parent.parent / "data" / "wakeword_samples" / "positive"
            pos_dir.mkdir(parents=True, exist_ok=True)
            import scipy.io.wavfile as wavfile
            ts = int(time.time())
            for idx, sample in enumerate(audio_samples, start=1):
                raw = np.asarray(sample).flatten()
                if np.issubdtype(raw.dtype, np.floating):
                    pcm = np.clip(raw * 32767.0, -32768, 32767).astype(np.int16)
                else:
                    pcm = raw.astype(np.int16)
                out_path = pos_dir / f"{profile_id}_enroll_{ts}_{idx:02d}.wav"
                wavfile.write(str(out_path), sample_rate, pcm)
        except Exception as e:
            _LOGGER.debug(f"Could not auto-persist positive training sample: {e}")

        # 7. Opt-in diagnostic storage: raw WAVs in user voice profile folder
        if retain_diagnostic_wavs:
            diag_dir = self.store.storage_dir / "diagnostics" / profile_id
            diag_dir.mkdir(parents=True, exist_ok=True)
            try:
                import scipy.io.wavfile as wavfile
                for idx, sample in enumerate(audio_samples, start=1):
                    wavfile.write(str(diag_dir / f"enroll_{idx:02d}.wav"), sample_rate, sample)
            except Exception as e:
                _LOGGER.warning(f"Could not save diagnostic enrollment wavs: {e}")

        # 8. Persist profile
        saved = self.store.save_profile(profile)
        if not saved:
            return EnrollmentResult(success=False, error_message="Failed to write profile to disk.")

        return EnrollmentResult(
            success=True,
            profile=profile,
            pairwise_similarities=pairwise_sims,
        )
