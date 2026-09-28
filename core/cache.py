"""
core/cache.py — Centralized Caching Layer for ALFRED Mark-II.

Provides high-throughput in-memory and optional Redis caching with:
- Cache-aside execution pattern.
- Deterministic key generation with collision-resistant SHA-256 hashing.
- Configurable TTL (Time-To-Live, default 15 minutes / 900 seconds).
- LRU & expiration eviction under memory bounds.
- Graceful fail-open fallback if external cache stores fail or timeout.
- Prefix-based bulk invalidation hooks for mutations.
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple


class CentralizedCache:
    """Thread-safe centralized cache supporting in-memory storage with optional Redis backend."""

    def __init__(
        self,
        default_ttl: int = 900,  # 15 minutes
        max_entries: int = 5000,
        redis_url: Optional[str] = None,
    ):
        self.default_ttl = default_ttl
        self.max_entries = max_entries
        self._lock = threading.RLock()
        self._memory_store: Dict[str, Dict[str, Any]] = {}
        self._redis = None
        self._redis_failed = False

        # Attempt to initialize Redis if URL provided or found in environment
        redis_target = redis_url or os.environ.get("REDIS_URL")
        if redis_target:
            self._init_redis(redis_target)

    def _init_redis(self, url: str) -> None:
        try:
            import redis
            self._redis = redis.Redis.from_url(url, socket_timeout=1.5, socket_connect_timeout=1.5)
            # Test ping
            self._redis.ping()
        except Exception as e:
            # Graceful degradation: disable Redis and use in-memory store
            print(f"[Cache] ⚠️ Redis initialization bypassed ({e}) — using in-memory store.")
            self._redis = None
            self._redis_failed = True

    def build_key(self, prefix: str, *args, **kwargs) -> str:
        """Generates a deterministic, collision-resistant cache key using canonical JSON serialization
        and SHA-256 hashing.
        """
        def _canonicalize(obj: Any) -> Any:
            if isinstance(obj, dict):
                return sorted((k, _canonicalize(v)) for k, v in obj.items())
            if isinstance(obj, (list, tuple, set)):
                return [_canonicalize(x) for x in obj]
            if hasattr(obj, "__dict__"):
                return _canonicalize(vars(obj))
            return str(obj)

        canonical_payload = {
            "args": [_canonicalize(a) for a in args],
            "kwargs": {k: _canonicalize(v) for k, v in sorted(kwargs.items())},
        }

        try:
            serialized = json.dumps(canonical_payload, sort_keys=True, ensure_ascii=False)
        except Exception:
            serialized = str(canonical_payload)

        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:24]
        clean_prefix = prefix.strip(": ")
        return f"{clean_prefix}:{digest}"

    def get(self, key: str) -> Optional[Any]:
        """Retrieves value from cache. Returns None if key is absent or expired.
        Fails open gracefully if any error occurs.
        """
        try:
            # 1. Try Redis if available
            if self._redis and not self._redis_failed:
                try:
                    raw = self._redis.get(key)
                    if raw is not None:
                        return json.loads(raw)
                except Exception:
                    pass

            # 2. In-memory lookup with expiration check
            with self._lock:
                if self._memory_store is None:
                    return None
                entry = self._memory_store.get(key)
                if entry is None:
                    return None

                now = time.time()
                if now > entry.get("expires_at", 0):
                    self._memory_store.pop(key, None)
                    return None

                entry["accessed_at"] = now
                return entry["value"]
        except Exception as e:
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Stores value in cache with TTL. Fails open gracefully if storage fails."""
        try:
            duration = ttl if ttl is not None else self.default_ttl
            now = time.time()
            expires_at = now + duration

            # 1. Try Redis
            if self._redis and not self._redis_failed:
                try:
                    self._redis.setex(key, duration, json.dumps(value, ensure_ascii=False))
                except Exception:
                    pass

            # 2. In-memory storage with LRU eviction guard
            with self._lock:
                if self._memory_store is None:
                    return False
                if len(self._memory_store) >= self.max_entries:
                    self._evict_oldest()

                self._memory_store[key] = {
                    "value": value,
                    "expires_at": expires_at,
                    "accessed_at": now,
                }
            return True
        except Exception:
            return False

    def delete(self, key: str) -> bool:
        """Deletes a key from cache. Fails open gracefully."""
        try:
            if self._redis and not self._redis_failed:
                try:
                    self._redis.delete(key)
                except Exception:
                    pass

            with self._lock:
                if self._memory_store is None:
                    return False
                return self._memory_store.pop(key, None) is not None
        except Exception:
            return False

    def invalidate_prefix(self, prefix: str) -> int:
        """Invalidates all keys starting with prefix. Useful for mutation hooks."""
        try:
            clean_prefix = prefix.strip()
            count = 0

            # In-memory bulk purge
            with self._lock:
                if self._memory_store is not None:
                    keys_to_remove = [k for k in self._memory_store if k.startswith(clean_prefix)]
                    for k in keys_to_remove:
                        self._memory_store.pop(k, None)
                        count += 1

            # Redis pattern purge
            if self._redis and not self._redis_failed:
                try:
                    pattern = f"{clean_prefix}*"
                    cursor = 0
                    while True:
                        cursor, keys = self._redis.scan(cursor=cursor, match=pattern, count=100)
                        if keys:
                            self._redis.delete(*keys)
                        if cursor == 0:
                            break
                except Exception:
                    pass

            return count
        except Exception:
            return 0

    def clear(self) -> None:
        """Clears all cached entries."""
        with self._lock:
            self._memory_store.clear()

        if self._redis and not self._redis_failed:
            try:
                self._redis.flushdb()
            except Exception:
                pass

    def _evict_oldest(self) -> None:
        """Evicts expired entries first; if none expired, evicts least recently accessed."""
        now = time.time()
        expired = [k for k, v in self._memory_store.items() if now > v["expires_at"]]
        if expired:
            for k in expired:
                self._memory_store.pop(k, None)
            return

        # LRU eviction
        if self._memory_store:
            oldest_key = min(self._memory_store.keys(), key=lambda k: self._memory_store[k]["accessed_at"])
            self._memory_store.pop(oldest_key, None)

    def cached(
        self,
        prefix: str,
        ttl: Optional[int] = None,
        key_builder: Optional[Callable[..., str]] = None,
    ) -> Callable:
        """Decorator implementing the cache-aside pattern with automatic fallback."""
        def decorator(fn: Callable) -> Callable:
            @functools.wraps(fn)
            def wrapper(*args, **kwargs) -> Any:
                # 1. Build deterministic cache key
                try:
                    if key_builder:
                        cache_key = key_builder(*args, **kwargs)
                    else:
                        cache_key = self.build_key(prefix, *args, **kwargs)
                except Exception:
                    # Fallback to direct execution on key generation failure
                    return fn(*args, **kwargs)

                # 2. Check cache first
                try:
                    cached_val = self.get(cache_key)
                    if cached_val is not None:
                        return cached_val
                except Exception:
                    # Fail open
                    pass

                # 3. On miss, execute underlying logic
                result = fn(*args, **kwargs)

                # 4. Store in cache (if not None)
                if result is not None:
                    try:
                        self.set(cache_key, result, ttl=ttl)
                    except Exception:
                        pass

                return result

            # Attach cache control helpers to function wrapper
            wrapper.cache_key = lambda *a, **kw: self.build_key(prefix, *a, **kw)
            wrapper.invalidate = lambda *a, **kw: self.delete(self.build_key(prefix, *a, **kw))
            wrapper.invalidate_all = lambda: self.invalidate_prefix(prefix)
            return wrapper

        return decorator


# Centralized global singleton
_GLOBAL_CACHE: Optional[CentralizedCache] = None
_CACHE_LOCK = threading.Lock()


def get_cache(default_ttl: int = 900) -> CentralizedCache:
    """Returns the centralized cache client singleton."""
    global _GLOBAL_CACHE
    if _GLOBAL_CACHE is None:
        with _CACHE_LOCK:
            if _GLOBAL_CACHE is None:
                _GLOBAL_CACHE = CentralizedCache(default_ttl=default_ttl)
    return _GLOBAL_CACHE
