"""core/audio/stream.py — Single shared 16kHz audio input stream and pre-roll buffer.

Guarantees & Invariants:
- Exactly ONE sounddevice.InputStream runs for the whole process.
- Audio is captured at 16,000 Hz, 16-bit mono PCM in chunks of 512 samples (~32 ms).
- Maintains a 2.0-second pre-roll circular buffer in RAM for speech onset capture.
- Distributes incoming chunks to up to MAX_SUBSCRIBERS subscribers (Gemini uplink,
  wake-word detector, VAD, Whisper shadow, and HUD waveform) without contention.
- Fail-open: if audio hardware is absent or busy, provides a running stream that
  accepts mock/external audio or silent fallback without crashing.
"""

from __future__ import annotations

import collections
import logging
import threading
import time
from typing import Any, Callable, Dict, Optional, Union

import numpy as np

# ── Audio Stream Constants ───────────────────────────────────────────────────
SAMPLE_RATE: int = 16000          # 16 kHz sample rate (Gemini Live & Speech models)
CHUNK_SAMPLES: int = 512          # 512 samples per chunk (32 ms window)
CHANNELS: int = 1                 # Mono channel
PREROLL_S: float = 2.0            # 2.0 seconds pre-roll window
MAX_SUBSCRIBERS: int = 8          # Maximum concurrent audio stream subscribers
STREAM_LATENCY: str = "low"       # PortAudio low latency driver configuration

_LOGGER = logging.getLogger("core.audio.stream")

SubscriberFn = Callable[[bytes, np.ndarray], None]
Subscriber = Union[SubscriberFn, Any]  # Callable or object with put_nowait(bytes)


class SharedAudioStream:
    """Process-wide shared audio capture stream with circular pre-roll history."""

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        chunk_samples: int = CHUNK_SAMPLES,
        preroll_s: float = PREROLL_S,
        max_subscribers: int = MAX_SUBSCRIBERS,
    ) -> None:
        self.sample_rate = sample_rate
        self.chunk_samples = chunk_samples
        self.preroll_s = preroll_s
        self.max_subscribers = max_subscribers

        self._max_preroll_chunks = max(1, int(round((sample_rate * preroll_s) / chunk_samples)))
        self._preroll_buffer: collections.deque[bytes] = collections.deque(maxlen=self._max_preroll_chunks)
        self._preroll_lock = threading.Lock()

        self._subscribers: Dict[int, Subscriber] = {}
        self._sub_lock = threading.Lock()
        self._sub_seq = 0

        self._stream = None
        self._running = False
        self._stream_lock = threading.Lock()
        self._device = None

        self._last_chunk_time: float = 0.0
        self._chunks_received: int = 0
        self._zero_chunk_count: int = 0
        self._zero_warned: bool = False

    def is_running(self) -> bool:
        """Check if audio capture stream is actively open."""
        with self._stream_lock:
            return self._running

    def subscribe(self, sub: Subscriber) -> int:
        """Register a subscriber (queue or callback) to receive audio chunks.

        Returns a subscriber ID token for unsubscribing.
        """
        with self._sub_lock:
            if len(self._subscribers) >= self.max_subscribers:
                raise RuntimeError(
                    f"Maximum audio stream subscribers ({self.max_subscribers}) exceeded"
                )
            self._sub_seq += 1
            token = self._sub_seq
            self._subscribers[token] = sub
            return token

    def unsubscribe(self, token: int) -> bool:
        """Remove a previously registered subscriber."""
        with self._sub_lock:
            return self._subscribers.pop(token, None) is not None

    def subscriber_count(self) -> int:
        """Return the current number of active subscribers."""
        with self._sub_lock:
            return len(self._subscribers)

    def snapshot_preroll(self) -> bytes:
        """Retrieve the concatenated PCM bytes in the pre-roll window."""
        with self._preroll_lock:
            return b"".join(self._preroll_buffer)

    def clear_preroll(self) -> None:
        """Clear the current pre-roll history."""
        with self._preroll_lock:
            self._preroll_buffer.clear()

    def feed_chunk(self, data: bytes | np.ndarray) -> None:
        """Manually feed an audio chunk (for testing or proxy ingestion)."""
        if isinstance(data, bytes):
            pcm_bytes = data
            pcm_array = np.frombuffer(pcm_bytes, dtype=np.int16)
        else:
            pcm_array = data
            pcm_bytes = pcm_array.tobytes()

        # Update pre-roll circular history
        with self._preroll_lock:
            self._preroll_buffer.append(pcm_bytes)

        self._last_chunk_time = time.monotonic()
        self._chunks_received += 1

        # On macOS, zero signal typically indicates missing TCC microphone permission
        if not self._zero_warned and self._chunks_received <= 50:
            if np.max(np.abs(pcm_array)) == 0:
                self._zero_chunk_count += 1
                if self._zero_chunk_count >= 50:
                    import platform
                    if platform.system() == "Darwin":
                        _LOGGER.warning(
                            "macOS Audio: Microphone input stream is returning 100%% silent zeros. "
                            "Please ensure Terminal/Python/ALFRED has Microphone permission in "
                            "System Settings > Privacy & Security > Microphone."
                        )
                    self._zero_warned = True
            else:
                self._zero_warned = True

        # Fan out to all active subscribers safely
        with self._sub_lock:
            subs = list(self._subscribers.values())

        for sub in subs:
            try:
                if callable(sub):
                    sub(pcm_bytes, pcm_array)
                elif hasattr(sub, "put_nowait"):
                    sub.put_nowait(pcm_bytes)
                elif hasattr(sub, "put"):
                    sub.put(pcm_bytes, block=False)
            except Exception:
                # Subscriber queue full or callback threw — never break distribution
                pass

    def start(self, device: Optional[Union[str, int]] = None) -> bool:
        """Open and start the shared sounddevice InputStream."""
        with self._stream_lock:
            if self._running:
                return True

            self._device = device
            try:
                try:
                    import sounddevice as sd
                except OSError as e:
                    from core.audio_portaudio import handle_portaudio_os_error
                    handle_portaudio_os_error(e)
                    raise

                def _audio_callback(indata, frames, time_info, status):
                    # Sounddevice provides float32 or int16. We use int16.
                    chunk_bytes = indata.tobytes()
                    self.feed_chunk(chunk_bytes)

                self._stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=CHANNELS,
                    dtype="int16",
                    blocksize=self.chunk_samples,
                    device=self._device,
                    latency=STREAM_LATENCY,
                    callback=_audio_callback,
                )
                self._stream.start()
                self._running = True
                _LOGGER.info(
                    "SharedAudioStream started at %d Hz (blocksize=%d, device=%s)",
                    self.sample_rate,
                    self.chunk_samples,
                    self._device,
                )
                return True
            except Exception as exc:
                _LOGGER.warning("Could not start shared sounddevice stream: %s (fail-open)", exc)
                self._stream = None
                self._running = False
                return False

    def stop(self) -> None:
        """Stop and close the hardware audio stream."""
        with self._stream_lock:
            if not self._running:
                return
            self._running = False
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
            _LOGGER.info("SharedAudioStream stopped.")


_STREAM_INSTANCE: Optional[SharedAudioStream] = None
_STREAM_INIT_LOCK = threading.Lock()


def get_shared_audio_stream() -> SharedAudioStream:
    """Retrieve or create the process singleton SharedAudioStream."""
    global _STREAM_INSTANCE
    with _STREAM_INIT_LOCK:
        if _STREAM_INSTANCE is None:
            from core.registry import lookup, register
            existing = lookup("shared_audio_stream")
            if existing is not None and isinstance(existing, SharedAudioStream):
                _STREAM_INSTANCE = existing
            else:
                _STREAM_INSTANCE = SharedAudioStream()
                register("shared_audio_stream", _STREAM_INSTANCE)
        return _STREAM_INSTANCE
