"""core/audio/gate.py — Additive acoustic output gate and self-trigger shield.

Rules & Guarantees:
- Gate reasons are additive: audio flows upstream only when the reasons set is empty
  and the reverb/driver tail delay has fully elapsed.
- The wake-word detector inspects GATE_TTS specifically: while ALFRED speaks,
  wake-word inference is suppressed to prevent self-trigger feedback.
- Thread-safe process singleton registered in core.registry under 'audio_gate'.
"""
from __future__ import annotations

import contextlib
import logging
import threading
import time
from typing import Generator, Set

# ── Gate Reason Constants ───────────────────────────────────────────────────
GATE_TTS: str = "tts"                  # ALFRED is speaking
GATE_MEDIA: str = "media"              # Visual HUD / background audio playing
GATE_AUTOMATION: str = "automation"    # scheduler RUN job driving keyboard
GATE_RESOLVING: str = "resolving"      # tool is resolving media URL / yt-dlp

# Duration (ms) audio remains gated after the last reason releases to absorb
# acoustic reverb and soundcard DAC/buffer flush in the room.
GATE_RELEASE_DELAY_MS: int = 250

_LOGGER = logging.getLogger("core.audio.gate")


class AudioGate:
    """Additive acoustic gate controlling upstream mic flow and wake-word gating."""

    def __init__(self, release_delay_ms: int = GATE_RELEASE_DELAY_MS) -> None:
        self._lock = threading.Lock()
        self._reasons: Set[str] = set()
        self._release_delay_s: float = max(0.0, release_delay_ms / 1000.0)
        self._gated_until: float = 0.0

    def hold(self, reason: str) -> None:
        """Add a gate reason. Blocks upstream mic audio immediately."""
        with self._lock:
            self._reasons.add(reason)
            self._gated_until = 0.0

    def release(self, reason: str) -> None:
        """Remove a gate reason. Starts release tail delay when reasons become empty."""
        with self._lock:
            self._reasons.discard(reason)
            if not self._reasons:
                self._gated_until = time.monotonic() + self._release_delay_s

    @contextlib.contextmanager
    def holding(self, reason: str) -> Generator[None, None, None]:
        """Context manager holding a reason for a scoped block."""
        self.hold(reason)
        try:
            yield
        finally:
            self.release(reason)

    def is_open(self) -> bool:
        """Return True if no reasons are held and the release tail has elapsed."""
        with self._lock:
            if self._reasons:
                return False
            return time.monotonic() >= self._gated_until

    def is_reason_held(self, reason: str) -> bool:
        """Check if a specific reason is currently held (e.g. GATE_TTS for wake word)."""
        with self._lock:
            return reason in self._reasons

    def active_reasons(self) -> Set[str]:
        """Return a snapshot of active gate reasons."""
        with self._lock:
            return set(self._reasons)

    def reset(self) -> None:
        """Clear all active reasons and release delays."""
        with self._lock:
            self._reasons.clear()
            self._gated_until = 0.0


_GATE_INSTANCE: AudioGate | None = None
_GATE_INIT_LOCK = threading.Lock()


def get_audio_gate() -> AudioGate:
    """Retrieve or create the process singleton AudioGate."""
    global _GATE_INSTANCE
    with _GATE_INIT_LOCK:
        if _GATE_INSTANCE is None:
            from core.registry import lookup, register
            existing = lookup("audio_gate")
            if existing is not None and isinstance(existing, AudioGate):
                _GATE_INSTANCE = existing
            else:
                _GATE_INSTANCE = AudioGate()
                register("audio_gate", _GATE_INSTANCE)
        return _GATE_INSTANCE
