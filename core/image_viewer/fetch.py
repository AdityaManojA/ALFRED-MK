"""
core/image_viewer/fetch.py — Off-thread image fetching, validation, and candidate cycling.

Enforces:
- Constant timeouts and size limits: FETCH_TIMEOUT_S, FETCH_MAX_MB
- Content-type allowlist
- Validation with QImageReader before display
- Host-only logging for privacy
- Candidate cycling for "another one / next"
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence
from urllib.parse import urlparse

import requests
from PyQt6.QtCore import QBuffer, QByteArray
from PyQt6.QtGui import QImageReader

from core.image_viewer.cache import ImageViewerCache
from core.imagery.sources.base import ImageResult
from core.imagery.sources.local import LocalSource
from core.imagery.sources.web import WebSource

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named Constants
# ---------------------------------------------------------------------------
FETCH_TIMEOUT_S: float = 8.0
FETCH_MAX_MB: int = 15
ALLOWED_CONTENT_TYPES: tuple[str, ...] = (
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/bmp",
    "image/gif",
)
USER_AGENT: str = "Alfred-Mark-VIII/1.0 (Desktop Assistant)"


@dataclass(frozen=True)
class FetchResult:
    """Outcome of an image fetch operation."""
    success: bool
    data: bytes | None = None
    file_path: str = ""
    host: str = ""
    attribution: str = ""
    width: int = 0
    height: int = 0
    error: str = ""


def extract_host(uri: str) -> str:
    """Extract domain host only for privacy-safe logs and state."""
    try:
        parsed = urlparse(uri)
        if parsed.netloc:
            return parsed.netloc.lower()
        if Path(uri).exists():
            return "Local File"
        return "Unknown"
    except Exception:
        return "Unknown"


def validate_image_bytes(data: bytes) -> tuple[bool, int, int]:
    """Validate image bytes with QImageReader without full bitmap allocation."""
    if not data or len(data) < 16:
        return (False, 0, 0)
    try:
        q_bytes = QByteArray(data)
        buffer = QBuffer(q_bytes)
        buffer.open(QBuffer.OpenModeFlag.ReadOnly)
        reader = QImageReader(buffer)
        if not reader.canRead():
            buffer.close()
            return (False, 0, 0)
        size = reader.size()
        buffer.close()
        if size.isValid() and size.width() > 0 and size.height() > 0:
            return (True, size.width(), size.height())
        return (False, 0, 0)
    except Exception as exc:
        log.debug("[ImageViewerFetch] validation error: %s", exc)
        return (False, 0, 0)


def fetch_image(
    uri_or_path: str,
    cache: Optional[ImageViewerCache] = None,
    timeout_s: float = FETCH_TIMEOUT_S,
    max_mb: int = FETCH_MAX_MB,
    attribution: str = "",
) -> FetchResult:
    """Fetch an image from local filesystem or web, validate, and cache it."""
    uri_or_path = uri_or_path.strip()
    if not uri_or_path:
        return FetchResult(success=False, error="empty_query")

    host = extract_host(uri_or_path)
    max_bytes = max_mb * 1024 * 1024

    # 1. Local file path check
    local_p = Path(uri_or_path).expanduser()
    if local_p.is_file():
        try:
            if local_p.stat().st_size > max_bytes:
                return FetchResult(success=False, error="file_too_large", host="Local File")
            data = local_p.read_bytes()
            valid, w, h = validate_image_bytes(data)
            if not valid:
                return FetchResult(success=False, error="invalid_image_format", host="Local File")
            return FetchResult(
                success=True,
                data=data,
                file_path=str(local_p),
                host="Local File",
                attribution=attribution or local_p.name,
                width=w,
                height=h,
            )
        except Exception as exc:
            log.warning("[ImageViewerFetch] local read error: %s", exc)
            return FetchResult(success=False, error=str(exc), host="Local File")

    # 2. Web URL check
    parsed = urlparse(uri_or_path)
    if parsed.scheme in ("http", "https"):
        # Check disk cache first
        if cache is not None:
            cached_data = cache.get(uri_or_path)
            if cached_data is not None:
                valid, w, h = validate_image_bytes(cached_data)
                if valid:
                    return FetchResult(
                        success=True,
                        data=cached_data,
                        file_path=str(cache.path_for(uri_or_path)),
                        host=host,
                        attribution=attribution,
                        width=w,
                        height=h,
                    )

        # Download from network
        try:
            log.info("[ImageViewerFetch] fetching image from host: %s", host)
            headers = {"User-Agent": USER_AGENT}
            response = requests.get(
                uri_or_path,
                headers=headers,
                timeout=timeout_s,
                stream=True,
            )
            response.raise_for_status()

            # Verify content-type
            content_type = response.headers.get("Content-Type", "").lower().split(";")[0].strip()
            if content_type and not any(content_type == act for act in ALLOWED_CONTENT_TYPES):
                log.warning("[ImageViewerFetch] rejected content-type: %s", content_type)
                return FetchResult(success=False, error="unsupported_content_type", host=host)

            # Check declared content-length
            content_length = response.headers.get("Content-Length")
            if content_length and content_length.isdigit() and int(content_length) > max_bytes:
                return FetchResult(success=False, error="oversize_download", host=host)

            # Read content with byte cap
            buf = bytearray()
            for chunk in response.iter_content(chunk_size=65536):
                buf.extend(chunk)
                if len(buf) > max_bytes:
                    return FetchResult(success=False, error="oversize_download", host=host)

            data = bytes(buf)
            valid, w, h = validate_image_bytes(data)
            if not valid:
                return FetchResult(success=False, error="corrupt_or_unsupported_image", host=host)

            # Cache on success
            file_path = str(local_p)
            if cache is not None:
                cached_path = cache.put(uri_or_path, data)
                file_path = str(cached_path)

            return FetchResult(
                success=True,
                data=data,
                file_path=file_path,
                host=host,
                attribution=attribution,
                width=w,
                height=h,
            )

        except requests.Timeout:
            log.warning("[ImageViewerFetch] timeout downloading from %s", host)
            return FetchResult(success=False, error="fetch_timeout", host=host)
        except Exception as exc:
            log.warning("[ImageViewerFetch] download error from %s: %s", host, exc)
            return FetchResult(success=False, error="fetch_failed", host=host)

    return FetchResult(success=False, error="not_found", host=host)


class ReferenceImageSession:
    """Manages search resolution and candidate cycling for reference images."""

    def __init__(
        self,
        local_source: Optional[LocalSource] = None,
        web_source: Optional[WebSource] = None,
        cache: Optional[ImageViewerCache] = None,
    ) -> None:
        self._local_source = local_source or LocalSource()
        self._web_source = web_source or WebSource()
        self._cache = cache or ImageViewerCache()
        self._candidates: list[ImageResult] = []
        self._current_idx: int = 0
        self._last_query: str = ""

    @property
    def current_index(self) -> int:
        return self._current_idx

    @property
    def total_candidates(self) -> int:
        return len(self._candidates)

    def search(self, query: str) -> FetchResult:
        """Resolve query into candidate results and fetch the first match."""
        query = query.strip()
        if not query:
            return FetchResult(success=False, error="empty_query")

        self._last_query = query
        self._candidates = []
        self._current_idx = 0

        # 1. Search local files first
        try:
            local_matches = self._local_source.search(query, limit=5)
            if local_matches:
                self._candidates.extend(local_matches)
        except Exception as exc:
            log.debug("[ReferenceImageSession] local search error: %s", exc)

        # 2. Search web sources if fewer than 5 candidates
        if len(self._candidates) < 5:
            try:
                web_matches = self._web_source.search(query, limit=8)
                if web_matches:
                    self._candidates.extend(web_matches)
            except Exception as exc:
                log.debug("[ReferenceImageSession] web search error: %s", exc)

        if not self._candidates:
            return FetchResult(success=False, error="no_results_found")

        return self._fetch_current()

    def next_candidate(self) -> FetchResult:
        """Cycle to next candidate image ('another one / next')."""
        if not self._candidates:
            return FetchResult(success=False, error="no_candidates")
        self._current_idx = (self._current_idx + 1) % len(self._candidates)
        return self._fetch_current()

    def previous_candidate(self) -> FetchResult:
        """Cycle to previous candidate image."""
        if not self._candidates:
            return FetchResult(success=False, error="no_candidates")
        self._current_idx = (self._current_idx - 1) % len(self._candidates)
        return self._fetch_current()

    def _fetch_current(self) -> FetchResult:
        """Fetch the candidate at current_idx."""
        if not self._candidates or not (0 <= self._current_idx < len(self._candidates)):
            return FetchResult(success=False, error="out_of_bounds")

        cand = self._candidates[self._current_idx]
        attr = f"{cand.attribution} · {cand.licence}".strip(" ·")
        return fetch_image(
            cand.fetch_handle,
            cache=self._cache,
            attribution=attr,
        )
