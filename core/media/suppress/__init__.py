"""Platform-selected external media suppressors."""

from __future__ import annotations

import platform

from .base import NullSuppressor, Suppressor


def get_suppressor() -> Suppressor:
    """Return the media suppressor for the current OS, or a NullSuppressor."""
    system = platform.system()
    if system == "Windows":
        from .win import WindowsSuppressor
        return WindowsSuppressor()
    if system == "Darwin":
        from .mac import MacSuppressor
        return MacSuppressor()
    if system == "Linux":
        from .linux import LinuxSuppressor
        return LinuxSuppressor()
    return NullSuppressor()


__all__ = ["Suppressor", "get_suppressor"]
