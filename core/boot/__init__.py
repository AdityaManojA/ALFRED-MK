"""core/boot/__init__.py — Boot stage decomposition package.

Provides declarative BootStage, non-blocking BootPipeline, and BootContext.
"""

from __future__ import annotations

from core.boot.stages import (
    BOOT_STAGE_TIMEOUT_DEFAULT_S,
    BOOT_TOTAL_BUDGET_S,
    THREAD_MAIN,
    THREAD_WORKER,
    BootStage,
)
from core.boot.loader import (
    BootContext,
    BootFailureError,
    BootPipeline,
    build_standard_boot_pipeline,
)
from core.boot.lazy import (
    LazyService,
    create_lazy_scheduler,
    create_lazy_sentry_mgr,
    create_lazy_monitor_controller,
    create_lazy_hud_video_controller,
)

__all__ = [
    "BootStage",
    "BootContext",
    "BootPipeline",
    "BootFailureError",
    "build_standard_boot_pipeline",
    "LazyService",
    "create_lazy_scheduler",
    "create_lazy_sentry_mgr",
    "create_lazy_monitor_controller",
    "create_lazy_hud_video_controller",
    "THREAD_MAIN",
    "THREAD_WORKER",
    "BOOT_STAGE_TIMEOUT_DEFAULT_S",
    "BOOT_TOTAL_BUDGET_S",
]
