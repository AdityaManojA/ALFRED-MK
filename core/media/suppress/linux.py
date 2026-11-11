"""Linux placeholder for the Phase 3 MPRIS backend."""

from .base import NullSuppressor


class LinuxSuppressor(NullSuppressor):
    """Placeholder Linux backend; behaves as NullSuppressor until MPRIS lands."""

    pass
