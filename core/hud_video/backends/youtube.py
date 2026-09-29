"""
core/hud_video/backends/youtube.py — YouTube backend.

PHASE 3 STOP POINT — requires yt-dlp.

Phase 1+2: raises NotImplementedError with a clear message so the action
handler can fall back to browser and tell the user to install yt-dlp.

Phase 3: installs yt-dlp stream URL extraction via subprocess, then passes
the CDN URL to LocalUrlBackend.

Usage pattern:
    stream_url = extract_stream_url(watch_url)  # blocking, run in thread pool
    ref.uri = stream_url
    ref.kind = "direct_url"
    # Then pass to LocalUrlBackend.load()
"""

from __future__ import annotations

import logging
import subprocess
import sys

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

# Format priority (AV1 excluded — no reliable software decoder in FFmpeg/Qt on Windows):
#   1. VP9 video (webm) + opus audio — best quality, full FFmpeg software support
#   2. H.264 video (mp4) + AAC audio — widest hw-decode compat fallback
#   3. Any non-AV1 bestvideo+bestaudio merge
#   4. Single-file best (last resort)
YTDLP_FORMAT: str = (
    "bestvideo[vcodec^=vp9][height<=1080]+bestaudio[acodec=opus]/"
    "bestvideo[vcodec^=avc][height<=1080][ext=mp4]+bestaudio[ext=m4a]/"
    "bestvideo[vcodec!=av01][height<=1080]+bestaudio[acodec!=av01]/"
    "best[vcodec!=av01]"
)
YTDLP_TIMEOUT_S: int = 30    # yt-dlp subprocess hard timeout


class YouTubeResolveError(Exception):
    """Raised when stream URL cannot be extracted from a YouTube watch URL."""


def _ytdlp_available() -> bool:
    """Check whether yt-dlp is importable or on PATH."""
    try:
        import yt_dlp  # noqa: F401
        return True
    except ImportError:
        pass
    try:
        subprocess.run(
            ["yt-dlp", "--version"],
            capture_output=True, timeout=5, check=True,
        )
        return True
    except Exception:
        return False


def extract_stream_url(watch_url: str) -> str:
    """Extract a direct CDN stream URL from a YouTube watch URL.

    Uses yt-dlp subprocess. Run in a thread pool — this is blocking.

    Raises YouTubeResolveError if yt-dlp is unavailable or extraction fails.

    Phase 3 activation: install yt-dlp and this function becomes live.
    Until then, raises YouTubeResolveError("yt-dlp not installed").
    """
    if not _ytdlp_available():
        raise YouTubeResolveError(
            "yt-dlp not installed. "
            "Run: pip install yt-dlp  to enable in-HUD YouTube playback."
        )

    try:
        import os as _os
        env = _os.environ.copy()
        # Silence FFmpeg AV1 hwaccel failure spam on systems without D3D11/NVDEC AV1
        env.setdefault("AV_LOG_FORCE_NOCOLOR", "1")
        env["FFREPORT"] = ""   # disable per-run FFmpeg report file

        result = subprocess.run(
            [
                sys.executable, "-m", "yt_dlp",
                "--get-url",
                "--format", YTDLP_FORMAT,
                "--no-playlist",
                "--merge-output-format", "mp4",
                watch_url,
            ],
            capture_output=True,
            text=True,
            timeout=YTDLP_TIMEOUT_S,
            env=env,
        )
        if result.returncode != 0:
            err = (result.stderr or "unknown error").strip()[:120]
            raise YouTubeResolveError(f"yt-dlp error: {err}")

        urls = [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
        if not urls:
            raise YouTubeResolveError("yt-dlp returned no stream URL.")

        # For merged VP9+opus webm/mkv, yt-dlp --get-url returns two lines
        # (video URL, audio URL). QMediaPlayer can't multiplex two streams;
        # return just the video URL — audio is baked in for most formats.
        # If only one URL is returned it already contains both tracks.
        stream_url = urls[0]
        log.info("[hud_video] yt-dlp resolved %d URL(s); using stream: %s…",
                 len(urls), stream_url[:60])
        return stream_url

    except subprocess.TimeoutExpired:
        raise YouTubeResolveError("yt-dlp timed out resolving the stream URL.")
    except YouTubeResolveError:
        raise
    except Exception as exc:
        raise YouTubeResolveError(f"Unexpected error from yt-dlp: {exc}") from exc
