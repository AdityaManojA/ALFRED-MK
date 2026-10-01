"""core/boot/lazy.py — First-use lazy factory pattern for non-critical subsystems.

Guarantees & Invariants:
- Defers instantiation, heavy imports, and thread allocations of Sentry, Scheduler,
  Visual HUD video backend, and Image Viewers until first explicit invocation.
- Thread-safe LazyService[T] transparent proxy.
- Eliminates unnecessary boot-time CPU and mark-and-sweep GC churn.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Generic, Optional, TypeVar

_LOGGER = logging.getLogger("core.boot.lazy")

T = TypeVar("T")


class LazyService(Generic[T]):
    """Thread-safe transparent proxy that delays object construction until first access."""

    def __init__(self, factory: Callable[[], T], name: str = "AnonymousService") -> None:
        self._factory = factory
        self._name = name
        self._instance: Optional[T] = None
        self._lock = threading.Lock()

    def is_instantiated(self) -> bool:
        """Check if the underlying service has been created yet."""
        with self._lock:
            return self._instance is not None

    def get(self) -> T:
        """Retrieve or create the underlying service."""
        if self._instance is not None:
            return self._instance

        with self._lock:
            if self._instance is None:
                _LOGGER.info("[LAZY] Instantiating deferred service '%s' on first access", self._name)
                self._instance = self._factory()
            return self._instance

    def __getattr__(self, item: str) -> Any:
        target = self.get()
        return getattr(target, item)

    def __repr__(self) -> str:
        status = "instantiated" if self.is_instantiated() else "uninstantiated"
        return f"<LazyService name='{self._name}' status='{status}'>"


def create_lazy_scheduler(speak_fn: Callable[[str], Any], notify_fn: Callable[[str], Any]) -> LazyService:
    """Create a lazy SchedulerEngine proxy."""
    def _factory():
        from core.scheduler import SchedulerEngine
        return SchedulerEngine(speak=speak_fn, notify=notify_fn)

    return LazyService(_factory, name="SchedulerEngine")


def create_lazy_sentry_mgr() -> LazyService:
    """Create a lazy SentryModeManager proxy."""
    def _factory():
        from core.sentry.mode_manager import get_sentry_mode_manager
        return get_sentry_mode_manager()

    return LazyService(_factory, name="SentryModeManager")


def create_lazy_monitor_controller() -> LazyService:
    """Create a lazy MonitorController proxy."""
    def _factory():
        from core.sentry.monitor.controller import get_monitor_controller
        return get_monitor_controller()

    return LazyService(_factory, name="MonitorController")


def create_lazy_hud_video_controller() -> LazyService:
    """Create a lazy HudVideoController proxy."""
    def _factory():
        from core.hud_video.controller import get_hud_video_controller
        return get_hud_video_controller()

    return LazyService(_factory, name="HudVideoController")
