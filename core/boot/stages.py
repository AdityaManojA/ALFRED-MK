"""core/boot/stages.py — Declarative boot stage definitions and data models.

Provides typed BootStage dataclass and stage registry for decomposing startup
into a non-blocking directed acyclic graph (DAG).
"""

from __future__ import annotations

import dataclasses
from typing import Any, Callable, List, Optional

# ── Boot Stage Constants ─────────────────────────────────────────────────────
BOOT_STAGE_TIMEOUT_DEFAULT_S: float = 10.0  # Per-stage timeout ceiling
BOOT_TOTAL_BUDGET_S: float = 30.0           # Overall boot budget ceiling

# Thread affinities
THREAD_MAIN: str = "main"       # Must execute on Qt GUI thread
THREAD_WORKER: str = "worker"   # Executes in background thread pool


@dataclasses.dataclass
class BootStage:
    """A declared, isolated stage in the application boot lifecycle."""

    name: str
    init_fn: Callable[[Any], Any]
    dependencies: List[str] = dataclasses.field(default_factory=list)
    is_critical: bool = False
    thread_affinity: str = THREAD_WORKER
    timeout_s: float = BOOT_STAGE_TIMEOUT_DEFAULT_S
    description: str = ""

    def __post_init__(self) -> None:
        if self.thread_affinity not in (THREAD_MAIN, THREAD_WORKER):
            raise ValueError(
                f"Invalid thread affinity '{self.thread_affinity}' for stage '{self.name}'. "
                f"Must be '{THREAD_MAIN}' or '{THREAD_WORKER}'."
            )
