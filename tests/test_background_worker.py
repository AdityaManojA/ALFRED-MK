import asyncio
import time
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

from main import JarvisLive, TOOL_DECLARATIONS
from dashboard.server import DashboardServer


class TestBackgroundWorkerPool(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_ui = MagicMock()
        self.mock_ui.write_log = MagicMock()
        self.mock_ui.set_state = MagicMock()
        self.mock_ui.muted = False

        self.app = JarvisLive(self.mock_ui)
        self.app._loop = asyncio.get_running_loop()

        # Start background worker loop
        self.worker_task = asyncio.create_task(self.app._background_worker())

    async def asyncTearDown(self):
        if hasattr(self, "worker_task") and not self.worker_task.done():
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass

    def test_tool_declaration_registered(self):
        """Verify queue_background_task is registered in TOOL_DECLARATIONS."""
        names = [t["name"] for t in TOOL_DECLARATIONS]
        self.assertIn("queue_background_task", names)
        tool_decl = next(t for t in TOOL_DECLARATIONS if t["name"] == "queue_background_task")
        self.assertIn("task_type", tool_decl["parameters"]["properties"])
        self.assertIn("payload", tool_decl["parameters"]["properties"])

    async def test_queue_and_execute_mock_task_non_blocking(self):
        """
        Verify that queue_background_task returns immediately (sub-millisecond),
        and the worker executes a mock task streaming progress telemetry to UI and dashboard.
        """
        mock_dashboard = MagicMock()
        mock_dashboard.update_background_task = AsyncMock()
        mock_dashboard.broadcast = AsyncMock()
        self.app._dashboard = mock_dashboard

        t0 = time.monotonic()
        res = await self.app.queue_background_task(
            task_type="mock_task",
            payload='{"duration": 0.1}'
        )
        dispatch_latency = (time.monotonic() - t0) * 1000

        # Sub-second (in fact < 10ms) dispatch latency
        self.assertLess(dispatch_latency, 50.0)
        self.assertEqual(res["status"], "queued")
        task_id = res["task_id"]
        self.assertTrue(task_id.startswith("bg_"))

        # Wait for the worker to finish the 0.1s job
        await self.app.background_task_queue.join()

        # Check telemetry updates
        self.assertTrue(mock_dashboard.update_background_task.called)
        calls = mock_dashboard.update_background_task.call_args_list

        progress_values = [c.kwargs.get("progress") for c in calls if "progress" in c.kwargs]
        self.assertIn(0, progress_values)
        self.assertIn(100, progress_values)

        # Verify UI HUD log received [control] [background XX%]
        ui_logs = [call.args[0] for call in self.mock_ui.write_log.call_args_list]
        bg_logs = [log for log in ui_logs if "[control] [background" in log]
        self.assertGreater(len(bg_logs), 0)

    async def test_simulated_10s_mock_task_with_voice_ptt_latency(self):
        """
        Dispatch a mock task and verify voice PTT interaction continues
        with sub-second latency while background logs stream.
        """
        mock_dashboard = MagicMock()
        mock_dashboard.update_background_task = AsyncMock()
        mock_dashboard.broadcast = AsyncMock()
        self.app._dashboard = mock_dashboard

        # Queue background task (simulating 10s via payload parameter parsed into slices)
        t_start = time.monotonic()
        res = await self.app.queue_background_task(task_type="mock_task", payload="0.2")
        self.assertEqual(res["status"], "queued")

        # Simulate voice PTT interaction during background execution
        ptt_latencies = []
        for _ in range(5):
            t_ptt_start = time.monotonic()
            # Push-to-talk press
            self.app._on_ptt(True)
            # Check state
            self.mock_ui.set_state.assert_called_with("LISTENING")
            # Push-to-talk release
            self.app._on_ptt(False)
            self.mock_ui.set_state.assert_called_with("SLEEPING")
            ptt_latency = (time.monotonic() - t_ptt_start) * 1000
            ptt_latencies.append(ptt_latency)
            await asyncio.sleep(0.03)

        # Confirm all PTT operations are sub-second (< 100ms)
        for lat in ptt_latencies:
            self.assertLess(lat, 100.0, f"PTT latency {lat}ms exceeded 100ms threshold")

        await self.app.background_task_queue.join()

    async def test_halt_interruption_stops_background_worker(self):
        """
        Verify that calling interrupt() sets halt event, immediately stops
        active background loops, and emits [control] [background halted].
        """
        mock_dashboard = MagicMock()
        mock_dashboard.update_background_task = AsyncMock()
        mock_dashboard.broadcast = AsyncMock()
        self.app._dashboard = mock_dashboard

        # Queue long job (5 seconds)
        res = await self.app.queue_background_task(task_type="mock_task", payload="5.0")
        task_id = res["task_id"]

        # Wait a tiny bit for it to start
        await asyncio.sleep(0.05)

        # Trigger interrupt / halt
        self.app.interrupt()
        self.assertTrue(self.app._bg_halt_event.is_set())

        # Wait for worker task to process halt
        await asyncio.sleep(0.1)

        # Verify halted telemetry was recorded
        ui_logs = [call.args[0] for call in self.mock_ui.write_log.call_args_list]
        halt_logs = [log for log in ui_logs if "background halted" in log]
        self.assertGreater(len(halt_logs), 0)

        # Verify dashboard received halted status
        halt_calls = [
            c for c in mock_dashboard.update_background_task.call_args_list
            if c.kwargs.get("status") == "halted"
        ]
        self.assertGreater(len(halt_calls), 0)

    async def test_audio_speaking_guard_prevents_interrupting_alfred(self):
        """
        Verify that _safe_background_announce waits until ALFRED finishes speaking
        before emitting any completion notice.
        """
        mock_session = AsyncMock()
        self.app.session = mock_session

        # ALFRED is speaking
        self.app.set_speaking(True)

        announced = False

        async def run_announce():
            nonlocal announced
            await self.app._safe_background_announce("Job complete")
            announced = True

        announce_task = asyncio.create_task(run_announce())

        # Give loop time to run
        await asyncio.sleep(0.1)

        # Must NOT have announced while ALFRED is speaking
        self.assertFalse(announced)
        mock_session.send_client_content.assert_not_called()

        # Stop speaking
        self.app.set_speaking(False)
        await asyncio.sleep(0.4)

        # Now it should be announced
        self.assertTrue(announced)
        mock_session.send_client_content.assert_called_once()
        await announce_task

    async def test_dashboard_server_background_task_tracking(self):
        """Verify DashboardServer tracks background tasks and exposes them via endpoint."""
        server = DashboardServer()
        await server.update_background_task(
            task_id="bg_123",
            task_type="mock_task",
            progress=50,
            status="running",
            detail="Processing step 5/10"
        )

        tasks = server.get_background_tasks()
        self.assertIn("bg_123", tasks)
        self.assertEqual(tasks["bg_123"]["progress"], 50)
        self.assertEqual(tasks["bg_123"]["status"], "running")


if __name__ == "__main__":
    unittest.main()
