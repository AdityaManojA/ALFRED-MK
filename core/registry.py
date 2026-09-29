"""
core/registry.py — Lightweight process-wide service registry.

Solves the `__main__` vs `main` module-identity split that occurs when
`python main.py` is run directly: `sys.modules['__main__']` and
`sys.modules['main']` are different objects, so any attribute written via
`import main; main.x = y` from inside `ui.py` lands on a ghost copy that
action modules importing `main` may or may not see depending on import order.

This module is imported by both sides without that ambiguity:
    - `ui.py` → `register("hud_video_controller", ctrl)`
    - `actions/hud_video.py` → `lookup("hud_video_controller")`

Thread-safety: dict writes under a threading.Lock; reads are lock-free
(GIL guarantees atomicity for single-key dict lookups in CPython).
"""

from __future__ import annotations

import logging
import threading
from typing import Any

_log = logging.getLogger(__name__)
_lock = threading.Lock()
_store: dict[str, Any] = {}


def register(key: str, value: Any) -> None:
    """Register *value* under *key*. Overwrites silently (re-init safe)."""
    with _lock:
        _store[key] = value
    _log.debug("[registry] registered: %s (%s)", key, type(value).__name__)


def lookup(key: str, default: Any = None) -> Any:
    """Return the registered value for *key*, or *default* if absent."""
    return _store.get(key, default)


def unregister(key: str) -> None:
    """Remove *key* from the registry (teardown / test cleanup)."""
    with _lock:
        _store.pop(key, None)


def all_keys() -> list[str]:
    """Return a snapshot of all registered keys (diagnostics only)."""
    return list(_store.keys())
