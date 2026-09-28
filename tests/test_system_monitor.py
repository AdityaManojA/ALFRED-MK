"""
tests/test_system_monitor.py — Unit tests for process tree watchdog, anomaly alerts, throttling, and socket inspection.
"""
import os
import time
import unittest
from unittest.mock import MagicMock, patch

import psutil

from actions.system_monitor import (
    watch_process_tree,
    throttle_process,
    resume_process,
    terminate_process,
    track_suspicious_sockets,
    is_protected_process,
    get_system_status,
    system_monitor_action,
    _CPU_STREAK_TRACKER,
)


class TestSystemMonitor(unittest.TestCase):
    def setUp(self):
        _CPU_STREAK_TRACKER.clear()

    def test_verification_requirement_synthetic_high_cpu_spike_detection(self):
        """
        Verification Requirement:
        Run a synthetic high-CPU test script. Confirm system_monitor detects
        the spike within 10s and emits [monitor] telemetry:
        [monitor] Resource anomaly: Process <PID:Name> utilizing <X>% CPU.
        """
        fake_pid = 98765
        fake_proc = MagicMock()
        fake_proc.info = {
            "pid": fake_pid,
            "name": "synthetic_compute_task.exe",
            "cpu_percent": 96.5,
        }
        fake_proc.pid = fake_pid
        fake_proc.name.return_value = "synthetic_compute_task.exe"

        # Simulate first check at t=0
        t0 = 1000.0
        with patch("time.monotonic", return_value=t0), \
             patch("psutil.process_iter", return_value=[fake_proc]), \
             patch("builtins.print") as mock_print:

            res0 = watch_process_tree(cpu_threshold=90.0, duration_seconds=10.0, check_sockets=False)
            # First tick: anomaly recorded in tracker, but consecutive duration < 10s so no alert yet
            self.assertEqual(len(res0["high_cpu_anomalies"]), 0)
            self.assertIn(fake_pid, _CPU_STREAK_TRACKER)

        # Simulate consecutive check at t=10.5s (>10s threshold)
        t1 = 1010.5
        with patch("time.monotonic", return_value=t1), \
             patch("psutil.process_iter", return_value=[fake_proc]), \
             patch("builtins.print") as mock_print:

            res1 = watch_process_tree(cpu_threshold=90.0, duration_seconds=10.0, check_sockets=False)

            # Anomaly detected within 10.5s
            self.assertEqual(len(res1["high_cpu_anomalies"]), 1)
            anomaly = res1["high_cpu_anomalies"][0]
            self.assertEqual(anomaly["pid"], fake_pid)
            self.assertEqual(anomaly["name"], "synthetic_compute_task.exe")
            self.assertEqual(anomaly["cpu_percent"], 96.5)
            self.assertGreaterEqual(anomaly["duration_seconds"], 10.0)

            # Verify required [monitor] telemetry tag emitted
            print_calls = [str(call.args[0]) for call in mock_print.call_args_list if call.args]
            anomaly_logs = [
                log for log in print_calls
                if "Resource anomaly: Process <98765:synthetic_compute_task.exe> utilizing 96.5% CPU" in log
            ]
            self.assertGreater(len(anomaly_logs), 0, "Expected [monitor] Resource anomaly log not found")

    def test_protected_process_exclusion_from_throttling(self):
        """
        Verify that core system executables, IDE compilers, and ALFRED's own process tree
        are excluded from throttling actions.
        """
        current_pid = os.getpid()

        # 1. ALFRED's own process cannot be throttled
        self.assertTrue(is_protected_process(current_pid))
        res_self = throttle_process(current_pid)
        self.assertEqual(res_self["status"], "rejected")
        self.assertIn("Cannot throttle protected", res_self["message"])

        # 2. System executable (e.g. explorer.exe or PID 4) cannot be throttled
        mock_explorer = MagicMock()
        mock_explorer.pid = 1234
        mock_explorer.name.return_value = "explorer.exe"
        self.assertTrue(is_protected_process(mock_explorer))

        with patch("psutil.Process", return_value=mock_explorer):
            res_exp = throttle_process(1234)
            self.assertEqual(res_exp["status"], "rejected")

        # 3. IDE compiler (e.g. cl.exe or code.exe) cannot be throttled
        mock_code = MagicMock()
        mock_code.pid = 5678
        mock_code.name.return_value = "code.exe"
        self.assertTrue(is_protected_process(mock_code))

        with patch("psutil.Process", return_value=mock_code):
            res_code = throttle_process(5678)
            self.assertEqual(res_code["status"], "rejected")

    def test_throttle_process_lowers_priority(self):
        """Verify throttle_process sets BELOW_NORMAL priority class on standard target."""
        fake_pid = 77777
        mock_target = MagicMock()
        mock_target.pid = fake_pid
        mock_target.name.return_value = "heavy_worker.exe"

        with patch("actions.system_monitor.is_protected_process", return_value=False), \
             patch("psutil.Process", return_value=mock_target):

            res = throttle_process(fake_pid, pause=False)
            self.assertEqual(res["status"], "throttled")
            mock_target.nice.assert_called_once()

    def test_throttle_process_pause_and_resume(self):
        """Verify pause (suspend) and resume functionality."""
        fake_pid = 77777
        mock_target = MagicMock()
        mock_target.pid = fake_pid
        mock_target.name.return_value = "heavy_worker.exe"

        with patch("actions.system_monitor.is_protected_process", return_value=False), \
             patch("psutil.Process", return_value=mock_target):

            # Suspend
            res_pause = throttle_process(fake_pid, pause=True)
            self.assertEqual(res_pause["status"], "throttled")
            mock_target.suspend.assert_called_once()

            # Resume
            res_resume = resume_process(fake_pid)
            self.assertEqual(res_resume["status"], "resumed")
            mock_target.resume.assert_called_once()

    def test_terminate_process_requires_confirmation(self):
        """
        Verify that a process is NEVER terminated automatically
        without explicit confirmation via core/confirm.py.
        """
        fake_pid = 88888
        mock_target = MagicMock()
        mock_target.pid = fake_pid
        mock_target.name.return_value = "rogue_task.exe"

        with patch("actions.system_monitor.is_protected_process", return_value=False), \
             patch("psutil.Process", return_value=mock_target), \
             patch("core.confirm.request", return_value="Please confirm termination") as mock_confirm:

            res = terminate_process(fake_pid, ask_confirmation=True)
            self.assertEqual(res["status"], "pending_confirmation")
            mock_confirm.assert_called_once()
            mock_target.terminate.assert_not_called()

    def test_track_suspicious_sockets(self):
        """Verify tracking outbound connections for non-standard remote ports."""
        mock_conn1 = MagicMock()
        mock_conn1.status = "ESTABLISHED"
        mock_conn1.laddr.ip = "192.168.1.10"
        mock_conn1.laddr.port = 54321
        mock_conn1.raddr.ip = "45.33.32.156"   # Public IP
        mock_conn1.raddr.port = 4444           # Non-standard suspicious port (Metasploit default)
        mock_conn1.pid = 9999

        mock_conn2 = MagicMock()
        mock_conn2.status = "ESTABLISHED"
        mock_conn2.laddr.ip = "192.168.1.10"
        mock_conn2.laddr.port = 54322
        mock_conn2.raddr.ip = "142.250.190.46" # Public Google IP
        mock_conn2.raddr.port = 443            # Standard HTTPS port (whitelisted)
        mock_conn2.pid = 1111

        with patch("psutil.net_connections", return_value=[mock_conn1, mock_conn2]), \
             patch("psutil.Process") as mock_proc, \
             patch("builtins.print") as mock_print:

            mock_proc.return_value.name.return_value = "suspicious_payload.exe"
            flagged = track_suspicious_sockets()

            # Port 443 must be ignored, Port 4444 must be flagged
            self.assertEqual(len(flagged), 1)
            self.assertEqual(flagged[0]["remote_port"], 4444)
            self.assertEqual(flagged[0]["pid"], 9999)

            print_calls = [str(call.args[0]) for call in mock_print.call_args_list if call.args]
            socket_logs = [log for log in print_calls if "Suspicious socket: Process <9999:suspicious_payload.exe> -> 45.33.32.156:4444" in log]
            self.assertGreater(len(socket_logs), 0)

    def test_system_monitor_action_dispatcher(self):
        """Verify system_monitor TOOL action handler."""
        # 1. status
        out_status = system_monitor_action({"action": "status"})
        self.assertIn("System Status: CPU", out_status)
        self.assertIn("RAM", out_status)

        # 2. watch
        out_watch = system_monitor_action({"action": "watch", "duration": 1.0})
        self.assertIn("Process tree monitored", out_watch)

        # 3. sockets
        out_sockets = system_monitor_action({"action": "sockets"})
        self.assertTrue("All active outbound network sockets" in out_sockets or "Detected" in out_sockets)


if __name__ == "__main__":
    unittest.main()
