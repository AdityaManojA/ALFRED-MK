"""
tests/boot/test_boot_stages.py — Unit tests for BootStage DAG sorting, parallelism, and error handling.
"""

from __future__ import annotations

import time
import unittest

from core.boot.stages import (
    BootStage,
    THREAD_MAIN,
    THREAD_WORKER,
    BOOT_STAGE_TIMEOUT_DEFAULT_S,
    BOOT_TOTAL_BUDGET_S,
)
from core.boot.loader import (
    BootContext,
    BootPipeline,
    BootFailureError,
    build_standard_boot_pipeline,
)


class TestBootStages(unittest.TestCase):

    def test_constants_defined(self):
        self.assertEqual(BOOT_STAGE_TIMEOUT_DEFAULT_S, 10.0)
        self.assertEqual(BOOT_TOTAL_BUDGET_S, 30.0)
        self.assertEqual(THREAD_MAIN, "main")
        self.assertEqual(THREAD_WORKER, "worker")

    def test_topological_batches_ordering(self):
        pipeline = BootPipeline()
        pipeline.register(BootStage("A", lambda ctx: "A", dependencies=[]))
        pipeline.register(BootStage("B", lambda ctx: "B", dependencies=["A"]))
        pipeline.register(BootStage("C", lambda ctx: "C", dependencies=["A"]))
        pipeline.register(BootStage("D", lambda ctx: "D", dependencies=["B", "C"]))

        batches = pipeline.topological_batches()
        self.assertEqual(len(batches), 3)
        self.assertEqual([s.name for s in batches[0]], ["A"])
        # B and C can run concurrently in batch 1
        batch1_names = set(s.name for s in batches[1])
        self.assertEqual(batch1_names, {"B", "C"})
        self.assertEqual([s.name for s in batches[2]], ["D"])

    def test_cycle_detection(self):
        pipeline = BootPipeline()
        pipeline.register(BootStage("A", lambda ctx: None, dependencies=["B"]))
        pipeline.register(BootStage("B", lambda ctx: None, dependencies=["A"]))

        with self.assertRaises(ValueError) as err:
            pipeline.topological_batches()
        self.assertIn("Cycle detected", str(err.exception))

    def test_unknown_dependency_rejected(self):
        pipeline = BootPipeline()
        pipeline.register(BootStage("A", lambda ctx: None, dependencies=["NON_EXISTENT"]))

        with self.assertRaises(ValueError) as err:
            pipeline.topological_batches()
        self.assertIn("unknown stage", str(err.exception))

    def test_pipeline_execution_timings_and_context(self):
        pipeline = BootPipeline(max_workers=2)

        def _step_a(ctx: BootContext):
            time.sleep(0.01)
            ctx.set("val_a", 100)
            return 100

        def _step_b(ctx: BootContext):
            time.sleep(0.01)
            a = ctx.get("val_a")
            ctx.set("val_b", a + 50)
            return a + 50

        pipeline.register(BootStage("A", _step_a, is_critical=True))
        pipeline.register(BootStage("B", _step_b, dependencies=["A"], is_critical=True))

        ctx = pipeline.run()
        self.assertEqual(ctx.get("val_a"), 100)
        self.assertEqual(ctx.get("val_b"), 150)
        self.assertTrue(ctx.is_successful("A"))
        self.assertTrue(ctx.is_successful("B"))
        timings = ctx.timings()
        self.assertIn("A", timings)
        self.assertIn("B", timings)
        self.assertGreater(timings["A"], 5.0)  # > 5ms

    def test_non_critical_failure_continues(self):
        pipeline = BootPipeline()

        def _fail(ctx: BootContext):
            raise RuntimeError("Minor failure")

        pipeline.register(BootStage("FailingOptional", _fail, is_critical=False))
        pipeline.register(BootStage("SuccessAfter", lambda ctx: "OK", is_critical=True))

        ctx = pipeline.run()
        self.assertFalse(ctx.is_successful("FailingOptional"))
        self.assertTrue(ctx.is_successful("SuccessAfter"))
        self.assertIn("FailingOptional", ctx.errors())

    def test_critical_failure_raises(self):
        pipeline = BootPipeline()

        def _fatal(ctx: BootContext):
            raise RuntimeError("Fatal DB error")

        pipeline.register(BootStage("CriticalStage", _fatal, is_critical=True))

        with self.assertRaises(BootFailureError):
            pipeline.run()

    def test_standard_boot_pipeline_builds_and_runs(self):
        pipeline = build_standard_boot_pipeline()
        batches = pipeline.topological_batches()
        self.assertGreaterEqual(len(batches), 2)
        ctx = pipeline.run()
        self.assertTrue(ctx.is_successful("config_secrets"))
        self.assertTrue(ctx.is_successful("audio_stream"))
        self.assertTrue(ctx.is_successful("tool_registry"))


if __name__ == "__main__":
    unittest.main()
