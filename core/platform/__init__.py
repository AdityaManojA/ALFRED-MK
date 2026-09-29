"""
core/platform/__init__.py — Cross-platform backend factory and dispatcher.
"""
from __future__ import annotations

import sys
from typing import Optional

from core.platform.base import PlatformBackend

_CURRENT_BACKEND: Optional[PlatformBackend] = None


def get_backend() -> PlatformBackend:
    """Return the active PlatformBackend instance for the host operating system."""
    global _CURRENT_BACKEND
    if _CURRENT_BACKEND is not None:
        return _CURRENT_BACKEND

    if sys.platform == "win32":
        from core.platform.win import WindowsPlatformBackend
        _CURRENT_BACKEND = WindowsPlatformBackend()
    elif sys.platform == "darwin":
        from core.platform.mac import MacPlatformBackend
        _CURRENT_BACKEND = MacPlatformBackend()
    else:
        from core.platform.linux import LinuxPlatformBackend
        _CURRENT_BACKEND = LinuxPlatformBackend()

    return _CURRENT_BACKEND


__all__ = ["PlatformBackend", "get_backend"]
