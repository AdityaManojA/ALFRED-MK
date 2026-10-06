"""
core/speaker/ring_buffer.py — Bounded, thread-safe audio ring buffer with timestamps.
"""

from __future__ import annotations

import collections
import threading
from typing import Optional, Tuple
import numpy as np


class AudioRingBuffer:
    """Thread-safe bounded ring buffer for 16 kHz int16 audio with timestamps.

    Maintains sample-accurate time alignment so any wake-word candidate can
    slice its exact preceding and succeeding audio (pre-roll and post-roll).
    """

    def __init__(self, capacity_seconds: float = 4.0, sample_rate: int = 16000) -> None:
        self.capacity_seconds = max(1.0, float(capacity_seconds))
        self.sample_rate = sample_rate
        self.capacity_samples = int(self.capacity_seconds * self.sample_rate)

        self._lock = threading.Lock()
        # Ring buffer storing (pcm_array_chunk, start_ts, end_ts)
        self._chunks: collections.deque[Tuple[np.ndarray, float, float]] = collections.deque()
        self._total_samples: int = 0

    def feed(self, chunk: np.ndarray, timestamp: Optional[float] = None) -> None:
        """Feed a PCM chunk (int16 1D) into the buffer with its end timestamp."""
        import time

        if chunk is None or len(chunk) == 0:
            return

        arr = np.asarray(chunk, dtype=np.int16)
        if arr.ndim > 1:
            arr = arr[:, 0].flatten()
        else:
            arr = arr.flatten()

        end_ts = timestamp if timestamp is not None else time.monotonic()
        duration_s = float(len(arr)) / float(self.sample_rate)
        start_ts = end_ts - duration_s

        with self._lock:
            self._chunks.append((arr, start_ts, end_ts))
            self._total_samples += len(arr)

            # Prune oldest chunks exceeding capacity
            while self._total_samples > self.capacity_samples and self._chunks:
                oldest_arr, _, _ = self._chunks.popleft()
                self._total_samples -= len(oldest_arr)

    def get_slice(self, start_ts: float, end_ts: float) -> np.ndarray:
        """Extract a continuous PCM audio slice between start_ts and end_ts.

        Clamps to available buffered history.
        """
        if end_ts <= start_ts:
            return np.empty(0, dtype=np.int16)

        with self._lock:
            if not self._chunks:
                return np.empty(0, dtype=np.int16)

            matched_parts = []
            for arr, c_start, c_end in self._chunks:
                # Check overlap: max(start_ts, c_start) < min(end_ts, c_end)
                if c_end <= start_ts or c_start >= end_ts:
                    continue

                chunk_dur = c_end - c_start
                if chunk_dur <= 0:
                    continue

                # Relative slice bounds inside this chunk
                t0 = max(start_ts, c_start)
                t1 = min(end_ts, c_end)

                idx0 = int(round((t0 - c_start) * self.sample_rate))
                idx1 = int(round((t1 - c_start) * self.sample_rate))
                idx0 = max(0, min(len(arr), idx0))
                idx1 = max(idx0, min(len(arr), idx1))

                if idx1 > idx0:
                    matched_parts.append(arr[idx0:idx1])

            if not matched_parts:
                return np.empty(0, dtype=np.int16)
            return np.concatenate(matched_parts)

    def get_recent(self, duration_s: float) -> np.ndarray:
        """Extract the most recent duration_s of audio."""
        if duration_s <= 0:
            return np.empty(0, dtype=np.int16)

        with self._lock:
            if not self._chunks:
                return np.empty(0, dtype=np.int16)
            latest_end = self._chunks[-1][2]

        return self.get_slice(start_ts=latest_end - duration_s, end_ts=latest_end)

    def clear(self) -> None:
        """Reset and discard all buffered audio."""
        with self._lock:
            self._chunks.clear()
            self._total_samples = 0
