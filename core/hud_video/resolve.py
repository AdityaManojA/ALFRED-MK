"""
core/hud_video/resolve.py — Resolve any input to a PlayableRef.

Input types handled:
  1. YouTube URL (watch, youtu.be, shorts, embed)
  2. Direct HTTP(S) media URL (mp4, webm, mkv, mov, m3u8, or content-type probe)
  3. Local file path (validated via path_guard)
  4. Free-text description -> YouTube search -> first result

All network I/O is synchronous and should be called from a thread pool,
never from the Qt event loop directly.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

RESOLVE_PROBE_TIMEOUT_MS: int = 5_000   # content-type HTTP probe timeout (ms)
RESOLVE_TIMEOUT_S: int = 30             # overall resolve hard timeout (seconds)
SEARCH_RESULT_LIMIT: int = 1            # take only the top search result

MEDIA_EXTENSIONS: frozenset[str] = frozenset({
    ".mp4", ".webm", ".mkv", ".mov", ".m3u8",
    ".avi", ".flv", ".ogv", ".ts", ".mp2t",
})

MEDIA_CONTENT_TYPES: frozenset[str] = frozenset({
    "video/mp4", "video/webm", "video/x-matroska",
    "video/quicktime", "application/x-mpegurl",
    "video/x-flv", "video/ogg", "video/avi",
})

_YT_PATTERN = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|shorts/|embed/|v/)|youtu\.be/)"
    r"([A-Za-z0-9_-]{11})"
)
_YT_VIDEO_FILTER = "EgIQAQ%3D%3D"


@dataclass
class PlayableRef:
    kind: Literal["youtube", "direct_url", "local_file"]
    uri: str                          # playable URI
    title: str                        # display + TTS (never a raw URL)
    thumb_url: str | None = None
    source_query: str | None = None   # original user text, locus stripped


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent


def _extract_yt_id(url: str) -> str | None:
    m = _YT_PATTERN.search(url)
    return m.group(1) if m else None


def _is_yt_url(text: str) -> bool:
    return bool(_YT_PATTERN.search(text))


def _is_http_url(text: str) -> bool:
    return text.startswith(("http://", "https://"))


def _looks_like_media_url(url: str) -> bool:
    """True if extension is in MEDIA_EXTENSIONS (fast path, no network)."""
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in MEDIA_EXTENSIONS)


def _probe_content_type(url: str, timeout_ms: int = RESOLVE_PROBE_TIMEOUT_MS) -> bool:
    """HEAD request to check Content-Type. Returns True if it's video."""
    try:
        import requests
        r = requests.head(url, timeout=timeout_ms / 1000, allow_redirects=True)
        ct = r.headers.get("Content-Type", "")
        return any(ct.startswith(m) for m in MEDIA_CONTENT_TYPES)
    except Exception:
        return False


def _scrape_yt_video_url(query: str) -> tuple[str, str] | None:
    """Scrape first non-Shorts YouTube video URL for query.

    Returns (watch_url, title) or None on failure.
    Reuses logic from actions/youtube_video.py but returns the title too.
    """
    from urllib.parse import quote_plus

    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        import requests
        search_url = (
            f"https://www.youtube.com/results"
            f"?search_query={quote_plus(query)}"
            f"&sp={_YT_VIDEO_FILTER}"
        )
        r = requests.get(search_url, headers=_HEADERS, timeout=RESOLVE_TIMEOUT_S)
        html = r.text

        video_ids = re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', html)
        titles = re.findall(r'"title":\{"runs":\[\{"text":"([^"]+)"', html)

        seen: set[str] = set()
        for i, vid in enumerate(video_ids):
            if vid in seen:
                continue
            seen.add(vid)
            if f"/shorts/{vid}" in html:
                continue
            watch_url = f"https://www.youtube.com/watch?v={vid}"
            title = titles[i] if i < len(titles) else query
            return watch_url, title

    except Exception as exc:
        import logging
        logging.getLogger(__name__).debug("[resolve] YouTube scrape failed: %s", exc)

    return None


def _scrape_yt_title(video_id: str) -> str:
    """Try to get video title from page HTML. Falls back to video ID."""
    try:
        import requests
        _HEADERS = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        r = requests.get(
            f"https://www.youtube.com/watch?v={video_id}",
            headers=_HEADERS, timeout=10,
        )
        m = re.search(r'"title":\{"runs":\[\{"text":"([^"]+)"', r.text)
        if m:
            return m.group(1)
    except Exception:
        pass
    return video_id


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class ResolveError(Exception):
    """Raised when no playable reference can be produced."""


def resolve(query: str, *, source_query: str = "") -> PlayableRef:
    """Resolve *query* to a PlayableRef.

    Raises ResolveError on failure.  Always run in a thread pool.

    Priority:
    1. YouTube URL -> normalise to video_id, schedule yt-dlp in Phase 3
    2. Other http(s) URL that looks like or probes as media -> direct_url
    3. Local file path (path_guard validated) -> local_file
    4. Free-text description -> YouTube search -> PlayableRef (youtube kind)
    """
    q = query.strip()

    # --- 1. YouTube URL ---
    if _is_yt_url(q):
        video_id = _extract_yt_id(q)
        if not video_id:
            raise ResolveError("Could not extract YouTube video ID.")
        title = _scrape_yt_title(video_id)
        # URI stored as canonical watch URL; youtube backend extracts stream in Phase 3
        return PlayableRef(
            kind="youtube",
            uri=f"https://www.youtube.com/watch?v={video_id}",
            title=title,
            source_query=source_query or q,
        )

    # --- 2. Other HTTP(S) URL ---
    if _is_http_url(q):
        if _looks_like_media_url(q) or _probe_content_type(q):
            title = Path(urlparse(q).path).stem or "Video"
            return PlayableRef(
                kind="direct_url",
                uri=q,
                title=title,
                source_query=source_query or q,
            )
        raise ResolveError("URL does not appear to be a playable media file.")

    # --- 3. Local file path ---
    if any(c in q for c in ("/", "\\", ":")) or Path(q).suffix.lower() in MEDIA_EXTENSIONS:
        from core.path_guard import check_path_access
        ok, err = check_path_access(q)
        if not ok:
            raise ResolveError(err)
        p = Path(q).expanduser().resolve()
        if not p.exists():
            raise ResolveError(f"File not found: {p.name}")
        if p.suffix.lower() not in MEDIA_EXTENSIONS:
            raise ResolveError(f"Not a supported media file: {p.suffix}")
        return PlayableRef(
            kind="local_file",
            uri=str(p),
            title=p.stem,
            source_query=source_query or q,
        )

    # --- 4. Free-text -> YouTube search ---
    result = _scrape_yt_video_url(q)
    if not result:
        raise ResolveError(f"Could not find a video for: {q!r}")

    watch_url, title = result
    video_id = _extract_yt_id(watch_url) or watch_url
    return PlayableRef(
        kind="youtube",
        uri=watch_url,
        title=title,
        source_query=source_query or q,
    )
