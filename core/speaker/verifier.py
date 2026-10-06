"""
core/speaker/verifier.py — Evaluates wake candidates against enrolled speaker profiles.
"""

from __future__ import annotations

import logging
from typing import Optional
import numpy as np

from core.speaker.types import (
    WakeCandidateAudio,
    SpeakerEmbedding,
    SpeakerProfile,
    VerificationDecision,
)
from core.speaker.extractor import SpeakerEmbeddingExtractor, CampplusOnnxExtractor
from core.speaker.profile_store import SpeakerProfileStore

_LOGGER = logging.getLogger("core.speaker.verifier")

DEFAULT_VERIFICATION_THRESHOLD = 0.52


class SpeakerVerifier:
    """Verifies whether a wake candidate was uttered by an authorized, enrolled user.

    Computes normalized cosine similarity between the candidate's speech embedding
    and enrolled profile centroids/templates.
    """

    def __init__(
        self,
        profile_store: Optional[SpeakerProfileStore] = None,
        embedding_extractor: Optional[SpeakerEmbeddingExtractor] = None,
        default_threshold: float = DEFAULT_VERIFICATION_THRESHOLD,
    ) -> None:
        self.profile_store = profile_store or SpeakerProfileStore()
        self.extractor = embedding_extractor or CampplusOnnxExtractor()
        self.default_threshold = default_threshold

    def verify(self, candidate: WakeCandidateAudio) -> VerificationDecision:
        """Evaluate a wake candidate utterance against enrolled profiles."""
        profiles = self.profile_store.list_profiles()
        if not profiles:
            return VerificationDecision(
                is_match=False,
                score=0.0,
                threshold=self.default_threshold,
                reject_reason="no_enrolled_profiles",
            )

        # Quality check: audio duration and speech presence
        if candidate.duration_s < 0.30:
            return VerificationDecision(
                is_match=False,
                score=0.0,
                threshold=self.default_threshold,
                reject_reason=f"audio_too_short ({candidate.duration_s:.2f}s < 0.30s)",
            )

        if candidate.rms_energy < 40.0:
            return VerificationDecision(
                is_match=False,
                score=0.0,
                threshold=self.default_threshold,
                reject_reason=f"audio_insufficient_energy (rms={candidate.rms_energy:.1f})",
            )

        try:
            tag = getattr(candidate, "speaker_tag", None)
            if tag is not None and hasattr(self.extractor, "default_tag"):
                self.extractor.default_tag = tag
            cand_emb = self.extractor.extract_embedding(candidate.audio_pcm, candidate.sample_rate)
        except Exception as e:
            _LOGGER.error(f"Speaker embedding extraction error: {e}")
            return VerificationDecision(
                is_match=False,
                score=0.0,
                threshold=self.default_threshold,
                reject_reason=f"extraction_error: {e}",
            )

        best_score = -1.0
        best_profile: Optional[SpeakerProfile] = None
        best_threshold = self.default_threshold

        for p in profiles:
            thresh = p.threshold if p.threshold > 0 else self.default_threshold
            scores = []

            # 1. Similarity with centroid
            if p.centroid_embedding:
                c_vec = np.asarray(p.centroid_embedding, dtype=np.float32)
                c_norm = np.linalg.norm(c_vec)
                if c_norm > 0:
                    c_vec = c_vec / c_norm
                    scores.append(float(np.dot(cand_emb.vector, c_vec)))

            # 2. Max similarity across individual enrollment templates
            for tmpl in p.template_embeddings:
                t_vec = np.asarray(tmpl, dtype=np.float32)
                t_norm = np.linalg.norm(t_vec)
                if t_norm > 0:
                    t_vec = t_vec / t_norm
                    scores.append(float(np.dot(cand_emb.vector, t_vec)))

            if not scores:
                continue

            # Combined score: blend of centroid and highest template match
            max_score = max(scores)
            avg_score = sum(scores) / len(scores)
            combined_score = 0.6 * max_score + 0.4 * avg_score

            if combined_score > best_score:
                best_score = combined_score
                best_profile = p
                best_threshold = thresh

        if best_profile is not None and best_score >= best_threshold:
            return VerificationDecision(
                is_match=True,
                score=best_score,
                threshold=best_threshold,
                matched_profile_id=best_profile.profile_id,
                matched_user=best_profile.user_name,
                reject_reason=None,
            )

        user_hint = f" (closest: {best_profile.user_name})" if best_profile else ""
        return VerificationDecision(
            is_match=False,
            score=max(0.0, best_score),
            threshold=best_threshold,
            reject_reason=f"score_below_threshold ({best_score:.3f} < {best_threshold:.3f}){user_hint}",
        )
