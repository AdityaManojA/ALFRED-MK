from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass(frozen=True)
class ImageResult:
    fetch_handle: str
    attribution: str
    licence: str
    is_local: bool

class ImageSource(ABC):
    @abstractmethod
    def search(self, query: str, limit: int) -> list[ImageResult]: ...
