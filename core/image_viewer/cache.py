"""
core/image_viewer/cache.py — LRU disk-backed image cache.

Enforces:
- Size limit capped at IMAGE_CACHE_MAX_MB
- Evicts oldest by access time when full
- Privacy: logs host only, never query parameters or tokens
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named Constants
# ---------------------------------------------------------------------------
IMAGE_CACHE_MAX_MB: int = 100
IMAGE_CACHE_DIR: Path = Path("data/image_cache")
IMAGE_CACHE_MAX_AGE_S: int = 86400 * 7  # 7 days


class ImageViewerCache:
    """Thread-safe disk cache for downloaded reference images."""

    def __init__(self, root: Path = IMAGE_CACHE_DIR, max_mb: int = IMAGE_CACHE_MAX_MB) -> None:
        self.root = root
        self.max_bytes = max_mb * 1024 * 1024
        self._lock = threading.Lock()
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            log.debug("[ImageViewerCache] mkdir failed: %s", exc)

    @staticmethod
    def key(uri: str) -> str:
        """Derive deterministic short SHA-256 hash for cache key."""
        return hashlib.sha256(uri.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def extract_host(uri: str) -> str:
        """Extract host domain only for privacy-safe logging."""
        try:
            parsed = urlparse(uri)
            return parsed.netloc or "local"
        except Exception:
            return "unknown"

    def path_for(self, uri: str) -> Path:
        return self.root / f"{self.key(uri)}.img"

    def get(self, uri: str) -> bytes | None:
        """Retrieve cached bytes if present."""
        path = self.path_for(uri)
        with self._lock:
            if not path.is_file():
                return None
            try:
                # Update atime for LRU tracking
                path.touch()
                return path.read_bytes()
            except Exception as exc:
                log.debug("[ImageViewerCache] read error: %s", exc)
                return None

    def put(self, uri: str, data: bytes) -> Path:
        """Store bytes in cache and enforce LRU eviction."""
        path = self.path_for(uri)
        host = self.extract_host(uri)
        with self._lock:
            try:
                path.write_bytes(data)
                log.debug("[ImageViewerCache] cached %d bytes from %s", len(data), host)
                self._evict_locked()
            except Exception as exc:
                log.debug("[ImageViewerCache] write error: %s", exc)
        return path

    def _evict_locked(self) -> None:
        """Evict oldest entries when cache exceeds capacity."""
        try:
            entries = sorted(self.root.glob("*.img"), key=lambda item: item.stat().st_atime)
            total = sum(item.stat().st_size for item in entries)
            for item in entries:
                if total <= self.max_bytes:
                    break
                sz = item.stat().st_size
                item.unlink(missing_ok=True)
                total -= sz
        except Exception as exc:
            log.debug("[ImageViewerCache] eviction error: %s", exc)

    def clear(self) -> None:
        """Wipe all cached images."""
        with self._lock:
            try:
                for item in self.root.glob("*.img"):
                    item.unlink(missing_ok=True)
            except Exception as exc:
                log.debug("[ImageViewerCache] clear error: %s", exc)
