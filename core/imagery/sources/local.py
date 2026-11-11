from __future__ import annotations
from pathlib import Path
import os
import time
from .base import ImageResult, ImageSource

LOCAL_IMAGE_ROOTS = (Path.home() / "Pictures", Path.home() / "Downloads", Path.home() / "Desktop")
LOCAL_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
LOCAL_INDEX_TTL_S = 300

class LocalSource(ImageSource):
    """Image source that searches files under local roots by path or filename tokens."""
    def __init__(self, roots=LOCAL_IMAGE_ROOTS) -> None:
        """Store the search roots and start with an empty file index."""
        self.roots, self._index, self._indexed_at = tuple(Path(p) for p in roots), [], 0.0
    def _refresh(self) -> None:
        """Rebuild the index of image files under the roots unless it is still within its TTL."""
        if self._index and time.monotonic() - self._indexed_at < LOCAL_INDEX_TTL_S: return
        self._index = [p for root in self.roots if root.exists() for p in root.rglob("*") if p.is_file() and p.suffix.lower() in LOCAL_IMAGE_EXTS]
        self._indexed_at = time.monotonic()
    def search(self, query: str, limit: int) -> list[ImageResult]:
        """Return the query itself if it is an image path, else indexed files whose path contains every query token."""
        path = Path(query).expanduser()
        if path.is_file() and path.suffix.lower() in LOCAL_IMAGE_EXTS:
            return [ImageResult(str(path), path.name, "local", True)]
        self._refresh(); tokens = {item for item in query.lower().split() if item}
        matches = [p for p in self._index if tokens <= set(p.as_posix().lower().replace("_", " ").split())]
        return [ImageResult(str(p), p.name, "local", True) for p in matches[:limit]]
