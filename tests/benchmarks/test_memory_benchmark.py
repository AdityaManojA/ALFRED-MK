"""
Performance Benchmark: memory_manager._trim_to_limit
Tests execution time and correctness on large inputs (50,000 mock records).
Verifies that time complexity is O(N log N) / O(N) rather than O(N^2).
"""
import time
import json
import unittest
from memory.memory_manager import _trim_to_limit, MEMORY_MAX_CHARS


class TestMemoryTrimBenchmark(unittest.TestCase):

    def test_benchmark_50k_records(self):
        """Measures execution time for 50,000 mock records.
        Under the old O(N^2) implementation (re-serializing all entries on every deletion),
        50k records would cause severe CPU spikes and take minutes.
        The optimized implementation completes in sub-second time.
        """
        num_records = 50_000
        mock_memory = {
            "identity": {},
            "preferences": {},
            "projects": {},
            "relationships": {},
            "wishes": {},
            "notes": {},
        }

        # Populate categories with 50,000 records total (oldest to newest dates)
        categories = ["preferences", "projects", "relationships", "wishes", "notes"]
        for i in range(num_records):
            cat = categories[i % len(categories)]
            key = f"record_{i}"
            # Format dates across years so older records are explicitly ordered
            day = (i % 28) + 1
            month = ((i // 28) % 12) + 1
            year = 2000 + (i // (28 * 12))
            mock_memory[cat][key] = {
                "value": f"Telemetry fact value sample number {i} with tactical details",
                "updated": f"{year:04d}-{month:02d}-{day:02d}",
            }

        initial_size = len(json.dumps(mock_memory, ensure_ascii=False))
        self.assertGreater(initial_size, MEMORY_MAX_CHARS,
                           f"Mock memory ({initial_size} chars) must exceed limit ({MEMORY_MAX_CHARS} chars)")

        start_time = time.perf_counter()
        trimmed_memory = _trim_to_limit(mock_memory)
        elapsed = time.perf_counter() - start_time

        final_size = len(json.dumps(trimmed_memory, ensure_ascii=False))

        # 1. Correctness: final size must be strictly within MEMORY_MAX_CHARS
        self.assertLessEqual(final_size, MEMORY_MAX_CHARS,
                             f"Final size {final_size} must be <= {MEMORY_MAX_CHARS}")

        # 2. Performance: 50,000 items must be trimmed in less than 1.5 seconds (sub-second target)
        print(f"\n[Benchmark] 50,000 records: trimmed from {initial_size:,} to {final_size:,} chars in {elapsed:.4f}s")
        self.assertLess(elapsed, 1.5, f"Execution took {elapsed:.4f}s, exceeding 1.5s threshold")

        # 3. Integrity: Newest records should have been preserved over oldest
        preserved_keys = []
        for cat in categories:
            preserved_keys.extend(trimmed_memory[cat].keys())
        self.assertGreater(len(preserved_keys), 0)

        # Check that high index records (newer) exist while low index (older) were trimmed
        self.assertIn(f"record_{num_records - 1}", trimmed_memory[categories[(num_records - 1) % len(categories)]])
        self.assertNotIn("record_0", trimmed_memory["preferences"])

    def test_edge_case_already_under_limit(self):
        """Preserves all items when memory is already below limit."""
        memory = {
            "identity": {"name": {"value": "Bruce Wayne", "updated": "2026-01-01"}},
            "preferences": {"tea": {"value": "Earl Grey", "updated": "2026-01-02"}},
        }
        res = _trim_to_limit(memory)
        self.assertEqual(len(res["identity"]), 1)
        self.assertEqual(len(res["preferences"]), 1)

    def test_edge_case_empty_memory(self):
        """Handles empty memory structure gracefully."""
        empty = {cat: {} for cat in ["identity", "preferences", "projects", "relationships", "wishes", "notes"]}
        res = _trim_to_limit(empty)
        self.assertEqual(res, empty)


if __name__ == "__main__":
    unittest.main()
