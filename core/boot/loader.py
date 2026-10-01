"""core/boot/loader.py — Non-blocking topological boot executor.

Resolves boot dependencies as a DAG, batches independent stages, runs worker
stages in parallel via ThreadPoolExecutor, and executes main-thread stages
synchronously, reporting per-stage elapsed timings.
"""

from __future__ import annotations

import concurrent.futures
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set

from core.boot.stages import (
    BOOT_STAGE_TIMEOUT_DEFAULT_S,
    BOOT_TOTAL_BUDGET_S,
    THREAD_MAIN,
    THREAD_WORKER,
    BootStage,
)

_LOGGER = logging.getLogger("core.boot.loader")


class BootFailureError(Exception):
    """Raised when a critical boot stage fails to complete."""


class BootContext:
    """Thread-safe context dictionary shared across all boot stages."""

    def __init__(self) -> None:
        self._data: Dict[str, Any] = {}
        self._timings: Dict[str, float] = {}
        self._statuses: Dict[str, str] = {}
        self._errors: Dict[str, Exception] = {}
        self._lock = threading.Lock()

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, default)

    def record_stage(self, name: str, status: str, duration_ms: float, error: Optional[Exception] = None) -> None:
        with self._lock:
            self._statuses[name] = status
            self._timings[name] = duration_ms
            if error is not None:
                self._errors[name] = error

    def timings(self) -> Dict[str, float]:
        with self._lock:
            return dict(self._timings)

    def errors(self) -> Dict[str, Exception]:
        with self._lock:
            return dict(self._errors)

    def is_successful(self, name: str) -> bool:
        with self._lock:
            return self._statuses.get(name) == "success"


class BootPipeline:
    """Topological boot orchestrator managing stage dependencies and parallel execution."""

    def __init__(self, max_workers: int = 4) -> None:
        self._stages: Dict[str, BootStage] = {}
        self._max_workers = max_workers

    def register(self, stage: BootStage) -> BootPipeline:
        """Register a new BootStage in the pipeline."""
        if stage.name in self._stages:
            raise ValueError(f"BootStage '{stage.name}' already registered")
        self._stages[stage.name] = stage
        return self

    def topological_batches(self) -> List[List[BootStage]]:
        """Compute execution batches of independent stages respecting dependencies.

        Returns a list of batches. All stages within each batch can execute concurrently.
        Raises ValueError if cyclic dependencies or missing prerequisites are detected.
        """
        # Validate all dependencies exist
        for name, stage in self._stages.items():
            for dep in stage.dependencies:
                if dep not in self._stages:
                    raise ValueError(f"Stage '{name}' depends on unknown stage '{dep}'")

        # In-degree count
        in_degree: Dict[str, int] = {name: len(stage.dependencies) for name, stage in self._stages.items()}
        dependents: Dict[str, List[str]] = {name: [] for name in self._stages}
        for name, stage in self._stages.items():
            for dep in stage.dependencies:
                dependents[dep].append(name)

        ready = [name for name, deg in in_degree.items() if deg == 0]
        batches: List[List[BootStage]] = []
        processed_count = 0

        while ready:
            batches.append([self._stages[name] for name in ready])
            processed_count += len(ready)
            next_ready: List[str] = []

            for name in ready:
                for dependent in dependents[name]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        next_ready.append(dependent)
            ready = next_ready

        if processed_count < len(self._stages):
            unresolved = [name for name, deg in in_degree.items() if deg > 0]
            raise ValueError(f"Cycle detected in boot stages involving: {unresolved}")

        return batches

    def run(self, context: Optional[BootContext] = None) -> BootContext:
        """Execute all boot stages through topologically sorted batches."""
        ctx = context or BootContext()
        batches = self.topological_batches()
        t_boot_start = time.perf_counter()

        _LOGGER.info("Starting boot pipeline with %d stages across %d batches", len(self._stages), len(batches))

        for batch_idx, batch in enumerate(batches, start=1):
            main_stages = [s for s in batch if s.thread_affinity == THREAD_MAIN]
            worker_stages = [s for s in batch if s.thread_affinity == THREAD_WORKER]

            # 1. Execute worker stages in parallel
            if worker_stages:
                with concurrent.futures.ThreadPoolExecutor(
                    max_workers=min(self._max_workers, len(worker_stages)),
                    thread_name_prefix="boot-worker",
                ) as pool:
                    future_map = {
                        pool.submit(self._run_single_stage, stage, ctx): stage
                        for stage in worker_stages
                    }
                    for future in concurrent.futures.as_completed(future_map):
                        stage = future_map[future]
                        try:
                            future.result(timeout=stage.timeout_s)
                        except Exception as exc:
                            if stage.is_critical:
                                raise BootFailureError(
                                    f"Critical boot stage '{stage.name}' failed: {exc}"
                                ) from exc
                            _LOGGER.warning(
                                "[BOOT] Non-critical stage '%s' failed: %s (fail-open)",
                                stage.name,
                                exc,
                            )

            # 2. Execute main thread stages synchronously
            for stage in main_stages:
                try:
                    self._run_single_stage(stage, ctx)
                except Exception as exc:
                    if stage.is_critical:
                        raise BootFailureError(
                            f"Critical main boot stage '{stage.name}' failed: {exc}"
                        ) from exc
                    _LOGGER.warning(
                        "[BOOT] Non-critical main stage '%s' failed: %s (fail-open)",
                        stage.name,
                        exc,
                    )

        total_elapsed_ms = (time.perf_counter() - t_boot_start) * 1000.0
        _LOGGER.info("Boot pipeline finished in %.1f ms", total_elapsed_ms)
        return ctx

    def _run_single_stage(self, stage: BootStage, ctx: BootContext) -> Any:
        t0 = time.perf_counter()
        try:
            result = stage.init_fn(ctx)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            ctx.record_stage(stage.name, "success", elapsed_ms)
            _LOGGER.info("[BOOT] Stage '%s' completed in %.1f ms", stage.name, elapsed_ms)
            return result
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            ctx.record_stage(stage.name, "failed", elapsed_ms, error=exc)
            raise


def build_standard_boot_pipeline() -> BootPipeline:
    """Construct standard ALFRED decomposed boot pipeline."""
    pipeline = BootPipeline()

    # Stage 1: Config & Secrets
    def _init_config(ctx: BootContext):
        from memory.config_manager import (
            get_brief_enabled, get_input_device, get_output_device,
            get_wake_word_enabled,
        )
        ctx.set("config_ready", True)
        return True

    pipeline.register(
        BootStage(
            name="config_secrets",
            init_fn=_init_config,
            dependencies=[],
            is_critical=True,
            thread_affinity=THREAD_WORKER,
            description="Load user configuration and local preferences",
        )
    )

    # Stage 2: Audio Stream & Acoustic Gate
    def _init_audio(ctx: BootContext):
        from core.audio.gate import get_audio_gate
        from core.audio.stream import get_shared_audio_stream
        gate = get_audio_gate()
        stream = get_shared_audio_stream()
        ctx.set("audio_gate", gate)
        ctx.set("shared_audio_stream", stream)
        return True

    pipeline.register(
        BootStage(
            name="audio_stream",
            init_fn=_init_audio,
            dependencies=[],
            is_critical=True,
            thread_affinity=THREAD_WORKER,
            description="Prepare shared 16kHz audio stream and acoustic gate",
        )
    )

    # Stage 3: Tool & Action Registry
    def _init_tools(ctx: BootContext):
        from pathlib import Path
        from core.action_loader import discover_actions
        base_dir = Path(__file__).resolve().parent.parent.parent
        actions_dir = base_dir / "actions"
        actions = discover_actions(actions_dir=actions_dir)
        ctx.set("actions", actions)
        return actions

    pipeline.register(
        BootStage(
            name="tool_registry",
            init_fn=_init_tools,
            dependencies=["config_secrets"],
            is_critical=False,
            thread_affinity=THREAD_WORKER,
            description="Auto-discover action plugins and system tools",
        )
    )

    # Stage 4: Wake-word Warmup
    def _init_wakeword(ctx: BootContext):
        from core.wake_word import is_ready
        ctx.set("wakeword_ready", is_ready())
        return True

    pipeline.register(
        BootStage(
            name="wakeword",
            init_fn=_init_wakeword,
            dependencies=["audio_stream"],
            is_critical=False,
            thread_affinity=THREAD_WORKER,
            description="Inspect and prepare wake-word engine",
        )
    )

    # Stage 5: Background Audio / Tron Score
    def _init_bg_audio(ctx: BootContext):
        ctx.set("bg_audio_ready", True)
        return True

    pipeline.register(
        BootStage(
            name="background_audio",
            init_fn=_init_bg_audio,
            dependencies=["audio_stream"],
            is_critical=False,
            thread_affinity=THREAD_WORKER,
            description="Initialize background audio state",
        )
    )

    return pipeline
