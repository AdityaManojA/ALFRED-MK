"""
core/speaker/types.py — Type definitions and data structures for speaker verification.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Dict, List, Optional
import numpy as np


@dataclasses.dataclass(frozen=True)
class WakeCandidateAudio:
    """Represents a time-aligned audio snippet extracted from the ring buffer upon phrase detection."""

    audio_pcm: np.ndarray      # 16-bit PCM mono array (int16), 16 kHz
    sample_rate: int = 16000   # Default 16 kHz
    start_ts: float = 0.0      # Monotonic start timestamp
    end_ts: float = 0.0        # Monotonic end timestamp
    confidence: float = 0.0    # Phrase detector score (e.g. 0.0 to 1.0)
    source: str = "acoustic"   # "acoustic" | "whisper"
    speaker_tag: Optional[str] = None

    @property
    def duration_s(self) -> float:
        if self.sample_rate <= 0:
            return 0.0
        return float(len(self.audio_pcm)) / float(self.sample_rate)

    @property
    def rms_energy(self) -> float:
        if len(self.audio_pcm) == 0:
            return 0.0
        return float(np.sqrt(np.mean(self.audio_pcm.astype(np.float32) ** 2)))


@dataclasses.dataclass(frozen=True)
class SpeakerEmbedding:
    """L2-normalized speaker embedding vector."""

    vector: np.ndarray         # 1D float32 normalized vector
    model_name: str = "campplus"
    dimension: int = 512

    def cosine_similarity(self, other: "SpeakerEmbedding") -> float:
        if self.vector.shape != other.vector.shape:
            raise ValueError(f"Shape mismatch: {self.vector.shape} vs {other.vector.shape}")
        return float(np.dot(self.vector, other.vector))


@dataclasses.dataclass
class SpeakerProfile:
    """Enrolled speaker profile with templates, centroid, and calibrated threshold."""

    profile_id: str
    user_name: str
    enrolled_at: float
    template_embeddings: List[List[float]]
    centroid_embedding: List[float]
    threshold: float = 0.52
    sample_count: int = 1
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)
    schema_version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "profile_id": self.profile_id,
            "user_name": self.user_name,
            "enrolled_at": self.enrolled_at,
            "template_embeddings": self.template_embeddings,
            "centroid_embedding": self.centroid_embedding,
            "threshold": self.threshold,
            "sample_count": self.sample_count,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SpeakerProfile":
        return cls(
            profile_id=str(data.get("profile_id", "")),
            user_name=str(data.get("user_name", "")),
            enrolled_at=float(data.get("enrolled_at", 0.0)),
            template_embeddings=list(data.get("template_embeddings", [])),
            centroid_embedding=list(data.get("centroid_embedding", [])),
            threshold=float(data.get("threshold", 0.52)),
            sample_count=int(data.get("sample_count", len(data.get("template_embeddings", [])))),
            metadata=dict(data.get("metadata", {})),
            schema_version=int(data.get("schema_version", 1)),
        )


@dataclasses.dataclass(frozen=True)
class VerificationDecision:
    """Result of speaker verification on a wake candidate."""

    is_match: bool
    score: float
    threshold: float
    matched_profile_id: Optional[str] = None
    matched_user: Optional[str] = None
    reject_reason: Optional[str] = None

    @property
    def verified(self) -> bool:
        return self.is_match

    @property
    def similarity_score(self) -> float:
        return self.score

    @property
    def profile_id(self) -> Optional[str]:
        return self.matched_profile_id
