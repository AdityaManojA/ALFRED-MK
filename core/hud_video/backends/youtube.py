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

# Format priority:
#   1. Best progressive single-file stream with combined audio & video (itag 18, 22, etc.)
#   2. Best video + best audio adaptive streams (dual streams returned as video_url, audio_url)
#   3. Fallback best available stream
YTDLP_FORMAT: str = (
    "best[vcodec!=none][acodec!=none]/"
    "18/22/"
    "bestvideo[vcodec^=vp9][height<=1080]+bestaudio[acodec=opus]/"
    "bestvideo[vcodec^=avc][height<=1080][ext=mp4]+bestaudio[ext=m4a]/"
    "bestvideo[height<=1080]+bestaudio/"
    "best"
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


def extract_stream_url(watch_url: str) -> tuple[str, str | None]:
    """Extract direct CDN stream URL(s) from a YouTube watch URL.

    Uses yt-dlp subprocess. Run in a thread pool — this is blocking.

    Returns:
        tuple[str, str | None]: (video_url, audio_url). audio_url is None for
        progressive streams where audio is multiplexed into the video stream.

    Raises YouTubeResolveError if yt-dlp is unavailable or extraction fails.
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
                "--extractor-args", "youtube:player_client=android,ios,web",
                "--get-url",
                "--format", YTDLP_FORMAT,
                "--no-playlist",
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

        video_url = urls[0]
        audio_url = urls[1] if len(urls) > 1 else None

        from urllib.parse import urlparse
        host = urlparse(video_url).netloc
        log.info("[hud_video] yt-dlp resolved %d URL(s); stream host: %s", len(urls), host)
        return video_url, audio_url

    except subprocess.TimeoutExpired:
        raise YouTubeResolveError("yt-dlp timed out resolving the stream URL.")
    except YouTubeResolveError:
        raise
    except Exception as exc:
        raise YouTubeResolveError(f"Unexpected error from yt-dlp: {exc}") from exc
