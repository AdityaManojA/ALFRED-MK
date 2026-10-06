"""
core/speaker/extractor.py — Speaker embedding extractors (CAM++ ONNX and Fake).
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Optional, Protocol
import numpy as np

from core.speaker.types import SpeakerEmbedding

_LOGGER = logging.getLogger("core.speaker.extractor")

DEFAULT_MODEL_PATH = Path(__file__).resolve().parent.parent.parent / "models" / "speaker_verifier.onnx"
DEFAULT_MODEL_URL = "https://huggingface.co/csukuangfj/speaker-embedding-models/resolve/main/wespeaker_en_voxceleb_CAM++.onnx"


class SpeakerEmbeddingExtractor(Protocol):
    """Protocol for extracting normalized speaker embeddings from raw PCM audio."""

    def extract_embedding(self, audio_pcm: np.ndarray, sample_rate: int = 16000) -> SpeakerEmbedding:
        ...

    def is_available(self) -> bool:
        ...


class CampplusOnnxExtractor:
    """Pretrained CAM++ TDNN speaker embedding model running via ONNX Runtime on CPU.

    Input: 16 kHz mono int16 PCM audio (recommended 0.4s to 3.5s).
    Acoustic features: 80-dimensional Kaldi fbank features (time-mean normalized).
    Output: 512-dimensional L2-normalized speaker embedding vector.
    """

    def __init__(self, model_path: Optional[Path | str] = None) -> None:
        self.model_path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
        self._session = None
        self._input_name = "feats"
        self._output_name = "embs"

    def is_available(self) -> bool:
        return self.model_path.is_file() and self.model_path.stat().st_size > 1000000

    def _ensure_session(self) -> None:
        if self._session is not None:
            return

        if not self.is_available():
            raise FileNotFoundError(
                f"Speaker verifier model not found at {self.model_path}. "
                "Download or bundle models/speaker_verifier.onnx before enrollment."
            )

        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 2
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        self._session = ort.InferenceSession(
            str(self.model_path), sess_options=opts, providers=["CPUExecutionProvider"]
        )
        self._input_name = self._session.get_inputs()[0].name
        self._output_name = self._session.get_outputs()[0].name

    def _compute_fbank(self, audio_pcm: np.ndarray, sample_rate: int) -> np.ndarray:
        """Compute 80-dimensional mean-normalized filterbank features."""
        # Convert to 1D float32 waveform and ensure canonical 16-bit PCM amplitude scale [-32768, 32767]
        raw = np.asarray(audio_pcm, dtype=np.float32).flatten()
        if len(raw) > 0 and np.max(np.abs(raw)) <= 1.05:
            audio_float = raw * 32767.0
        else:
            audio_float = raw

        # Pad very short utterances to at least 400ms (6400 samples)
        min_samples = int(sample_rate * 0.4)
        if len(audio_float) < min_samples:
            pad_len = min_samples - len(audio_float)
            audio_float = np.pad(audio_float, (0, pad_len), mode="constant")

        try:
            import torch
            import torchaudio.compliance.kaldi as kaldi

            tensor = torch.from_numpy(audio_float).unsqueeze(0)
            fb = kaldi.fbank(tensor, num_mel_bins=80, sample_frequency=sample_rate, dither=0.0)
            # Time-domain mean normalization
            fb = fb - fb.mean(dim=0, keepdim=True)
            return fb.unsqueeze(0).numpy().astype(np.float32)
        except Exception:
            # Fallback pure-numpy/scipy fbank calculation if torchaudio not present
            return self._compute_numpy_fbank(audio_float, sample_rate)

    def _compute_numpy_fbank(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Lightweight numpy-based 80-mel filterbank."""
        from scipy.fft import rfft

        frame_len = int(sr * 0.025)   # 25ms
        frame_step = int(sr * 0.010)  # 10ms
        n_fft = 512

        # Framing
        num_frames = 1 + int((len(audio) - frame_len) / frame_step)
        if num_frames <= 0:
            num_frames = 1
            audio = np.pad(audio, (0, frame_len - len(audio)))

        indices = np.tile(np.arange(0, frame_len), (num_frames, 1)) + np.tile(
            np.arange(0, num_frames * frame_step, frame_step), (frame_len, 1)
        ).T
        frames = audio[indices]
        frames = frames * np.hamming(frame_len)

        # Power spectrum
        mag = np.abs(rfft(frames, n=n_fft))
        pow_frames = (1.0 / n_fft) * (mag ** 2)

        # Mel filterbanks
        low_freq_mel = 0
        high_freq_mel = 2595 * np.log10(1 + (sr / 2) / 700)
        mel_points = np.linspace(low_freq_mel, high_freq_mel, 82)
        hz_points = 700 * (10 ** (mel_points / 2595) - 1)
        bin_points = np.floor((n_fft + 1) * hz_points / sr).astype(int)

        fbank = np.zeros((80, int(n_fft / 2 + 1)))
        for m in range(1, 81):
            f_m_minus = bin_points[m - 1]
            f_m = bin_points[m]
            f_m_plus = bin_points[m + 1]
            for k in range(f_m_minus, f_m):
                fbank[m - 1, k] = (k - bin_points[m - 1]) / (bin_points[m] - bin_points[m - 1] + 1e-9)
            for k in range(f_m, f_m_plus):
                fbank[m - 1, k] = (bin_points[m + 1] - k) / (bin_points[m + 1] - bin_points[m] + 1e-9)

        filter_banks = np.dot(pow_frames, fbank.T)
        filter_banks = np.where(filter_banks == 0, np.finfo(float).eps, filter_banks)
        filter_banks = 10 * np.log10(filter_banks)

        # Mean normalization
        filter_banks -= np.mean(filter_banks, axis=0, keepdims=True)
        return np.expand_dims(filter_banks.astype(np.float32), axis=0)

    def extract_embedding(self, audio_pcm: np.ndarray, sample_rate: int = 16000) -> SpeakerEmbedding:
        """Extract a 512-dim normalized speaker embedding from audio PCM."""
        self._ensure_session()
        feats = self._compute_fbank(audio_pcm, sample_rate)

        outputs = self._session.run([self._output_name], {self._input_name: feats})
        emb = outputs[0][0].astype(np.float32)

        norm = np.linalg.norm(emb)
        if norm > 1e-9:
            emb = emb / norm
        else:
            emb = np.zeros_like(emb)

        return SpeakerEmbedding(vector=emb, model_name="campplus", dimension=len(emb))


class FakeSpeakerEmbeddingExtractor:
    """Deterministic fake extractor for fast, hermetic unit tests."""

    def __init__(self, dimension: int = 512) -> None:
        self.dimension = dimension
        self._next_embedding: Optional[np.ndarray] = None
        self._registry: dict[str, np.ndarray] = {}
        self.default_tag: Optional[str] = None

    def register_fake(self, tag: str, vec: np.ndarray) -> None:
        """Register a tagged speaker embedding vector for deterministic matching."""
        arr = np.asarray(vec, dtype=np.float32).flatten()
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr = arr / norm
        self._registry[tag] = arr

    def set_next_embedding(self, vec: np.ndarray) -> None:
        arr = np.asarray(vec, dtype=np.float32).flatten()
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr = arr / norm
        self._next_embedding = arr

    def is_available(self) -> bool:
        return True

    def extract_embedding(self, audio_pcm: np.ndarray, sample_rate: int = 16000) -> SpeakerEmbedding:
        if self._next_embedding is not None:
            vec = self._next_embedding.copy()
            self._next_embedding = None
            return SpeakerEmbedding(vector=vec, model_name="fake", dimension=self.dimension)

        tag = getattr(audio_pcm, "speaker_tag", None) or self.default_tag
        if tag and tag in self._registry:
            vec = self._registry[tag].copy()
            return SpeakerEmbedding(vector=vec, model_name="fake", dimension=self.dimension)

        # Hash audio content to generate consistent pseudo-random unit vector
        h = hashlib.sha256(audio_pcm.tobytes()).digest()
        seed = int.from_bytes(h[:4], "little")
        rng = np.random.RandomState(seed)
        vec = rng.randn(self.dimension).astype(np.float32)
        vec /= np.linalg.norm(vec)

        return SpeakerEmbedding(vector=vec, model_name="fake", dimension=self.dimension)
