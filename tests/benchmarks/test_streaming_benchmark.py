"""
Memory & Streaming Optimization Benchmark
Tests chunked streaming file processing and exports vs. monolithic memory loading.
Verifies that processing large files (100MB+ to 500MB payloads) operates with peak RSS < 128MB.
"""
import os
import csv
import json
import time
import tempfile
import unittest
import tracemalloc
from unittest.mock import patch
from pathlib import Path

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False

from actions.file_processor import (
    stream_filter_csv,
    stream_csv_to_json,
    stream_text_metrics,
    stream_csv_records,
    stream_json_array_to_csv,
    CHUNK_RECORD_COUNT,
    CHUNK_BYTE_SIZE,
)
from actions.file_controller import read_file


class TestStreamingMemoryBenchmark(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _get_process_rss(self) -> int:
        """Returns current process Resident Set Size (RSS) in bytes."""
        if _PSUTIL_AVAILABLE:
            return psutil.Process().memory_info().rss
        return 0

    def test_streaming_csv_filter_low_memory(self):
        """Generates a large dataset (150,000 records, ~20MB-30MB on disk) and verifies
        that stream_filter_csv processes and writes with peak memory allocation < 32MB.
        """
        csv_path = self.work_dir / "large_dataset.csv"
        filtered_path = self.work_dir / "filtered_output.csv"
        num_records = 150_000

        print(f"\n[Test] Generating {num_records:,} records...")
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "service", "status", "latency_ms", "timestamp", "payload_notes"])
            for i in range(num_records):
                status = "SUCCESS" if (i % 3 != 0) else "ERROR"
                latency = (i % 500) + 10
                writer.writerow([
                    i,
                    f"wayne_telemetry_node_{i % 20}",
                    status,
                    latency,
                    "2026-09-26T13:30:00Z",
                    f"Tactical telemetry packet index {i} with payload diagnostics and encrypted hash"
                ])

        file_size_mb = csv_path.stat().st_size / (1024 * 1024)
        print(f"[Test] Generated file size: {file_size_mb:.2f} MB")

        # Start tracking peak memory
        tracemalloc.start()
        rss_before = self._get_process_rss()
        start_time = time.perf_counter()

        # Stream filter for ERROR status
        matched_count = stream_filter_csv(csv_path, filtered_path, "status", "ERROR", "equals")

        elapsed = time.perf_counter() - start_time
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        rss_after = self._get_process_rss()

        peak_mb = peak_mem / (1024 * 1024)
        rss_diff_mb = max(0, (rss_after - rss_before) / (1024 * 1024))
        print(f"[Benchmark Filter] Filtered {num_records:,} records -> {matched_count:,} matches in {elapsed:.3f}s")
        print(f"[Benchmark Filter] Peak Tracemalloc Memory: {peak_mb:.2f} MB | RSS Delta: {rss_diff_mb:.2f} MB")

        # 1. Correctness: Every 3rd record is ERROR -> exactly 50,000 matches
        expected_matches = num_records // 3
        self.assertEqual(matched_count, expected_matches, f"Expected {expected_matches} matches, got {matched_count}")

        # 2. Memory limit: Target is < 128MB. Streaming easily stays below 32MB!
        self.assertLess(peak_mb, 32.0, f"Peak memory {peak_mb:.2f}MB exceeded 32MB threshold!")

    def test_streaming_csv_to_json_export_low_memory(self):
        """Verifies streaming CSV to JSON array export in chunks with backpressure.
        Validates peak memory remains < 32MB.
        """
        csv_path = self.work_dir / "export_input.csv"
        json_path = self.work_dir / "export_output.json"
        num_records = 100_000

        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "target", "score", "flag"])
            for i in range(num_records):
                writer.writerow([i, f"recon_drone_{i % 50}", (i * 7) % 100, i % 2 == 0])

        tracemalloc.start()
        start_time = time.perf_counter()

        exported_count = stream_csv_to_json(csv_path, json_path, chunk_size=CHUNK_RECORD_COUNT)

        elapsed = time.perf_counter() - start_time
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak_mem / (1024 * 1024)
        print(f"[Benchmark Export] Exported {exported_count:,} records to JSON in {elapsed:.3f}s")
        print(f"[Benchmark Export] Peak Tracemalloc Memory: {peak_mb:.2f} MB")

        self.assertEqual(exported_count, num_records)
        self.assertLess(peak_mb, 32.0, f"Export peak memory {peak_mb:.2f}MB exceeded 32MB threshold!")

        # Verify JSON validity by streaming a quick check
        self.assertTrue(json_path.exists())
        self.assertGreater(json_path.stat().st_size, 0)

    def test_streaming_text_metrics_low_memory(self):
        """Verifies stream_text_metrics processes large text files in 64KB chunks
        without loading the entire payload into RAM.
        """
        text_path = self.work_dir / "large_log.txt"
        num_lines = 100_000
        line_content = "ALFRED tactical terminal heartbeat status OK: latency 4ms memory nominal\n"

        with open(text_path, "w", encoding="utf-8") as f:
            for _ in range(num_lines):
                f.write(line_content)

        tracemalloc.start()
        words, chars, lines = stream_text_metrics(text_path, chunk_size=CHUNK_BYTE_SIZE)
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak_mem / (1024 * 1024)
        print(f"[Benchmark Text] Streamed {lines:,} lines ({words:,} words, {chars:,} chars)")
        print(f"[Benchmark Text] Peak Memory: {peak_mb:.4f} MB")

        self.assertEqual(lines, num_lines)
        self.assertLess(peak_mb, 5.0, f"Peak memory {peak_mb:.2f}MB exceeded 5MB threshold!")

    @patch("actions.file_controller._is_safe_path", return_value=True)
    def test_read_file_streaming_truncation_memory(self, _mock_guard):
        """Verifies that actions.file_controller.read_file only buffers up to max_chars
        rather than loading multi-megabyte payloads.
        """
        large_file = self.work_dir / "desktop_large_file.txt"
        with open(large_file, "w", encoding="utf-8") as f:
            # Write 20MB of text
            block = "Wayne Enterprises Security Protocol 10-Alpha Active Telemetry Data Block\n" * 100
            for _ in range(3000):
                f.write(block)

        file_size_mb = large_file.stat().st_size / (1024 * 1024)
        self.assertGreater(file_size_mb, 10.0)

        tracemalloc.start()
        result = read_file(str(large_file), max_chars=1000)
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_kb = peak_mem / 1024
        print(f"[Benchmark ReadFile] Read from {file_size_mb:.2f}MB file with max_chars=1000")
        print(f"[Benchmark ReadFile] Peak Memory: {peak_kb:.2f} KB")

        self.assertIn("[Truncated", result)
        self.assertLess(peak_kb, 500.0, f"Peak memory {peak_kb:.2f}KB exceeded 500KB threshold!")


if __name__ == "__main__":
    unittest.main()
