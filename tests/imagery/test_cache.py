from core.imagery.cache import ImageCache


def test_cache_uses_hashed_key_and_evicts_oldest(tmp_path):
    cache = ImageCache(tmp_path, max_mb=1)
    path = cache.put("zq-vortex-8813", b"image")
    assert "zq-vortex-8813" not in path.name
    assert cache.get("zq-vortex-8813") == b"image"
