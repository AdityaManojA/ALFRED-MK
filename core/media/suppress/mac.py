"""macOS placeholder for the Phase 3 AppleScript backend."""

from .base import NullSuppressor


class MacSuppressor(NullSuppressor):
    """Placeholder macOS backend; behaves as NullSuppressor until AppleScript lands."""

    pass
