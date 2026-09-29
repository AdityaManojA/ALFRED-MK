from __future__ import annotations
from pathlib import Path
import os
import time
from .base import ImageResult, ImageSource

LOCAL_IMAGE_ROOTS = (Path.home() / "Pictures", Path.home() / "Downloads", Path.home() / "Desktop")
LOCAL_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
LOCAL_INDEX_TTL_S = 300

class LocalSource(ImageSource):
    def __init__(self, roots=LOCAL_IMAGE_ROOTS) -> None:
        self.roots, self._index, self._indexed_at = tuple(Path(p) for p in roots), [], 0.0
    def _refresh(self) -> None:
        if self._index and time.monotonic() - self._indexed_at < LOCAL_INDEX_TTL_S: return
        self._index = [p for root in self.roots if root.exists() for p in root.rglob("*") if p.is_file() and p.suffix.lower() in LOCAL_IMAGE_EXTS]
        self._indexed_at = time.monotonic()
    def search(self, query: str, limit: int) -> list[ImageResult]:
        path = Path(query).expanduser()
        if path.is_file() and path.suffix.lower() in LOCAL_IMAGE_EXTS:
            return [ImageResult(str(path), path.name, "local", True)]
        self._refresh(); tokens = {item for item in query.lower().split() if item}
        matches = [p for p in self._index if tokens <= set(p.as_posix().lower().replace("_", " ").split())]
        return [ImageResult(str(p), p.name, "local", True) for p in matches[:limit]]
