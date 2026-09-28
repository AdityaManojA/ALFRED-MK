import asyncio
import time
import unittest
from unittest.mock import MagicMock, AsyncMock


class TestConcurrencyLimiter(unittest.IsolatedAsyncioTestCase):
    async def test_bounded_concurrency_scaling(self):
        """
        Verify that a batch of tasks run with a concurrency limit of 5
        scales sub-linearly and enforces maximum concurrent worker limits.
        """
        MAX_WORKERS = 5
        NUM_TASKS = 10
        TASK_LATENCY = 0.05  # 50ms per task

        active_workers = 0
        peak_workers = 0
        lock = asyncio.Lock()
        sem = asyncio.Semaphore(MAX_WORKERS)

        async def worker_task(task_id: int):
            nonlocal active_workers, peak_workers
            async with sem:
                async with lock:
                    active_workers += 1
                    if active_workers > peak_workers:
                        peak_workers = active_workers

                # Simulate third-party latency
                await asyncio.sleep(TASK_LATENCY)

                async with lock:
                    active_workers -= 1

                return f"result_{task_id}"

        start_time = time.monotonic()
        results = await asyncio.gather(*[worker_task(i) for i in range(NUM_TASKS)])
        elapsed = time.monotonic() - start_time

        # Verification 1: Peak concurrent workers must not exceed MAX_WORKERS
        self.assertLessEqual(peak_workers, MAX_WORKERS)
        self.assertEqual(len(results), NUM_TASKS)

        # Verification 2: Execution time scales sub-linearly:
        # Sequential time would be 10 * 0.05 = 0.50s.
        # With 5 workers, theoretical time is 2 * 0.05 = 0.10s.
        # Elapsed must be substantially less than sequential time (<0.35s).
        self.assertLess(elapsed, TASK_LATENCY * NUM_TASKS * 0.7)
        print(f"\n[Concurrency Benchmark] 10 tasks (50ms each) completed in {elapsed:.4f}s "
              f"with peak {peak_workers} concurrent workers (Sequential: {TASK_LATENCY * NUM_TASKS:.2f}s)")

    async def test_error_isolation_in_concurrent_tasks(self):
        """
        Verify that an exception in one concurrent task does not break or cancel
        independent tasks, and returns bounded error details.
        """
        sem = asyncio.Semaphore(5)

        async def execute_task(task_id: int):
            async with sem:
                await asyncio.sleep(0.02)
                if task_id == 3:
                    raise RuntimeError("Third-party API rate limited or timed out")
                return {"id": task_id, "status": "ok"}

        async def safe_run(task_id: int):
            try:
                return await execute_task(task_id)
            except Exception as e:
                return {"id": task_id, "error": str(e)}

        results = await asyncio.gather(*[safe_run(i) for i in range(6)])

        # Tasks 0, 1, 2, 4, 5 must succeed
        for i in [0, 1, 2, 4, 5]:
            self.assertEqual(results[i]["status"], "ok")

        # Task 3 must have isolated error without breaking others
        self.assertIn("error", results[3])
        self.assertIn("rate limited", results[3]["error"])


if __name__ == "__main__":
    unittest.main()
