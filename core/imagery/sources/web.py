from __future__ import annotations
import requests
from .base import ImageResult, ImageSource

WEB_IMAGE_TIMEOUT_S = 6
WEB_RESULTS_LIMIT = 8
IMAGE_MAX_DOWNLOAD_MB = 15

class WebSource(ImageSource):
    def search(self, query: str, limit: int = WEB_RESULTS_LIMIT) -> list[ImageResult]:
        try:
            data = requests.get("https://api.openverse.org/v1/images", params={"q": query, "page_size": min(limit, WEB_RESULTS_LIMIT)}, timeout=WEB_IMAGE_TIMEOUT_S).json()
        except Exception:
            return []
        return [ImageResult(item.get("url", ""), item.get("creator", "Openverse"), item.get("license", ""), False) for item in data.get("results", []) if item.get("url")]
