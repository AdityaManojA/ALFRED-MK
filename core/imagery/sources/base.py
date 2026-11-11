from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass(frozen=True)
class ImageResult:
    """A single image search hit: fetch handle, attribution, licence and whether it is a local file."""
    fetch_handle: str
    attribution: str
    licence: str
    is_local: bool

class ImageSource(ABC):
    """Abstract base for image sources that can be searched by text query."""
    @abstractmethod
    def search(self, query: str, limit: int) -> list[ImageResult]:
        """Return up to ``limit`` image results matching ``query``."""
        ...
