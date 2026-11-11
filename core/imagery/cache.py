"""Byte-only, query-free disk cache for image fetches."""

from __future__ import annotations

import hashlib
from pathlib import Path


IMAGE_CACHE_MAX_MB = 100
IMAGE_CACHE_DIR = Path("data/image_cache")


class ImageCache:
    """Size-capped on-disk byte cache for images, keyed by a hash of a string."""
    def __init__(self, root: Path = IMAGE_CACHE_DIR, max_mb: int = IMAGE_CACHE_MAX_MB) -> None:
        """Set the cache root and size cap, creating the root directory."""
        self.root = root
        self.max_bytes = max_mb * 1024 * 1024
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def key(value: str) -> str:
        """Return the first 16 hex chars of the SHA-256 of ``value``."""
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]

    def path_for(self, value: str) -> Path:
        """Return the cache file path for ``value``."""
        return self.root / f"{self.key(value)}.img"

    def get(self, value: str) -> bytes | None:
        """Return cached bytes for ``value`` (touching the file), or None if absent."""
        path = self.path_for(value)
        if not path.exists():
            return None
        path.touch()
        return path.read_bytes()

    def put(self, value: str, data: bytes) -> Path:
        """Write ``data`` to the cache for ``value``, evict over-limit entries and return the path."""
        path = self.path_for(value)
        path.write_bytes(data)
        self._evict()
        return path

    def _evict(self) -> None:
        """Delete least-recently-accessed cache files until total size fits ``max_bytes``."""
        entries = sorted(self.root.glob("*.img"), key=lambda item: item.stat().st_atime)
        total = sum(item.stat().st_size for item in entries)
        for item in entries:
            if total <= self.max_bytes:
                break
            total -= item.stat().st_size
            item.unlink(missing_ok=True)
