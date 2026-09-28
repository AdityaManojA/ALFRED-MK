"""
Performance Benchmark: dev_agent._parse_traceback
Tests O(1) hash map lookups vs O(N) linear search on large file sets (50,000 files).
"""
import time
import unittest
from actions.dev_agent import _parse_traceback


class TestTracebackBenchmark(unittest.TestCase):

    def test_benchmark_50k_files(self):
        """Measures lookup time across 50,000 mock project files and 500 stack frames."""
        num_files = 50_000
        mock_project_files = [f"/workspace/module_{i}/service_{i}.py" for i in range(num_files)]
        # Target file located towards the end
        target_file = mock_project_files[-1]

        # Generate a traceback with 200 stack frames ending at the target file
        traceback_lines = ["Traceback (most recent call last):"]
        for j in range(200):
            traceback_lines.append(f'  File "/external/lib/site-packages/pkg_{j}.py", line {10 + j}, in run')
            traceback_lines.append(f"    call_{j}()")
        traceback_lines.append(f'  File "{target_file}", line 42, in execute')
        traceback_lines.append("    raise ValueError('Simulated error')")
        traceback_lines.append("ValueError: Simulated error")

        output = "\n".join(traceback_lines)

        start = time.perf_counter()
        matched_file, line_num = _parse_traceback(output, mock_project_files)
        elapsed = time.perf_counter() - start

        print(f"\n[Benchmark] _parse_traceback over {num_files:,} files: matched in {elapsed:.6f}s")
        self.assertEqual(matched_file, target_file)
        self.assertEqual(line_num, 42)
        # Should resolve in under 50ms with hash maps
        self.assertLess(elapsed, 0.1, f"Lookup took {elapsed:.4f}s, expected < 0.1s")


if __name__ == "__main__":
    unittest.main()
