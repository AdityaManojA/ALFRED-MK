"""
core/speaker — Per-user local speaker verification for ALFRED wake-word activation.
"""

from core.speaker.types import (
    WakeCandidateAudio,
    SpeakerEmbedding,
    SpeakerProfile,
    VerificationDecision,
)
from core.speaker.ring_buffer import AudioRingBuffer
from core.speaker.extractor import (
    SpeakerEmbeddingExtractor,
    CampplusOnnxExtractor,
    FakeSpeakerEmbeddingExtractor,
)
from core.speaker.profile_store import SpeakerProfileStore
from core.speaker.verifier import SpeakerVerifier, DEFAULT_VERIFICATION_THRESHOLD
from core.speaker.enrollment import (
    SpeakerEnrollmentManager,
    QualityValidationResult,
    EnrollmentResult,
    validate_utterance_quality,
)

__all__ = [
    "WakeCandidateAudio",
    "SpeakerEmbedding",
    "SpeakerProfile",
    "VerificationDecision",
    "AudioRingBuffer",
    "SpeakerEmbeddingExtractor",
    "CampplusOnnxExtractor",
    "FakeSpeakerEmbeddingExtractor",
    "SpeakerProfileStore",
    "SpeakerVerifier",
    "DEFAULT_VERIFICATION_THRESHOLD",
    "SpeakerEnrollmentManager",
    "QualityValidationResult",
    "EnrollmentResult",
    "validate_utterance_quality",
]
