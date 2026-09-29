"""
core/hud_video/transport.py — Visual HUD transport state, constants, and utilities.

Enforces:
- Named constants at top of file
- Strict VideoState whitelist: loaded, status, position_s, duration_s, seekable
- Privacy: enums, bools, and seconds only (no stream URLs in state)
- Seek clamping to [0, duration - END_MARGIN_S]
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

STATE_EMIT_HZ: float = 4.0          # Max status/position emit rate while PLAYING (Hz)
END_MARGIN_S: float = 0.5           # Safety buffer before duration end for seeks (seconds)
RERESOLVE_RETRIES: int = 1          # Max re-resolve attempts upon signed URL stream expiry
SKIP_S: float = 10.0                # Default skip step for relative seeks (seconds)
PAUSE_ON_MINIMISE: bool = True      # Pause playback when app is minimised to mini HUD


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class VideoStatus(str, Enum):
    """Lifecycle status of the Visual HUD player."""
    IDLE = "IDLE"
    RESOLVING = "RESOLVING"
    LOADING = "LOADING"
    PLAYING = "PLAYING"
    PAUSED = "PAUSED"
    ENDED = "ENDED"
    ERROR = "ERROR"


class SeekRejectReason(str, Enum):
    """Reason enum when a seek request cannot be fulfilled."""
    NOT_SEEKABLE = "NOT_SEEKABLE"
    NOT_LOADED = "NOT_LOADED"
    OUT_OF_RANGE = "OUT_OF_RANGE"


# ---------------------------------------------------------------------------
# Whitelisted Client-Visible State
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VideoState:
    """Whitelisted snapshot of playback state.

    Privacy guarantee: contains only enums, bools, and seconds.
    Never contains stream URLs, file paths, or private metadata.
    """
    loaded: bool = False
    status: VideoStatus = VideoStatus.IDLE
    position_s: float = 0.0
    duration_s: float = 0.0
    seekable: bool = False

    def __call__(self) -> VideoState:
        """Allow controller.state() call syntax as well as controller.state property."""
        return self

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, VideoStatus):
            return self.status == other
        if isinstance(other, str):
            return self.status.value == other or self.status.name == other
        return super().__eq__(other)

    # Class-level aliases for backward compatibility with `state == VideoState.PLAYING`
    IDLE = VideoStatus.IDLE
    RESOLVING = VideoStatus.RESOLVING
    LOADING = VideoStatus.LOADING
    PLAYING = VideoStatus.PLAYING
    PAUSED = VideoStatus.PAUSED
    ENDED = VideoStatus.ENDED
    ERROR = VideoStatus.ERROR


# ---------------------------------------------------------------------------
# Pure Helper Functions
# ---------------------------------------------------------------------------

def clamp_seek(target_s: float, duration_s: float, end_margin_s: float = END_MARGIN_S) -> float:
    """Clamp seek target to [0.0, max(0.0, duration_s - end_margin_s)]."""
    if math.isnan(target_s) or math.isinf(target_s):
        return 0.0
    if duration_s <= 0.0:
        return max(0.0, target_s)
    max_pos = max(0.0, duration_s - end_margin_s)
    return max(0.0, min(target_s, max_pos))


def format_timestamp(seconds: float) -> str:
    """Format seconds into M:SS or H:MM:SS format."""
    if math.isnan(seconds) or math.isinf(seconds) or seconds < 0:
        return "0:00"
    s = int(seconds)
    hours = s // 3600
    minutes = (s % 3600) // 60
    secs = s % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"
