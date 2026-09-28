"""Process Target: Monitors a system process by PID or name."""
from __future__ import annotations

import time
import psutil
from core.sentry.monitor.targets.base import MonitorTarget, TargetStatus


class ProcessTarget(MonitorTarget):
    """Monitors a process for exit, or alerts when CPU/memory exceed thresholds."""

    def __init__(
        self,
        target_id: str,
        name: str,
        pid: int | None = None,
        cpu_threshold: float | None = None,
        mem_mb_threshold: float | None = None,
        alert_on_exit: bool = True,
        interval_s: float = 3.0,
    ) -> None:
        super().__init__(target_id, name, interval_s)
        self.pid = pid
        self.cpu_threshold = cpu_threshold
        self.mem_mb_threshold = mem_mb_threshold
        self.alert_on_exit = alert_on_exit
        self._proc: psutil.Process | None = None

        if self.pid is not None:
            try:
                self._proc = psutil.Process(self.pid)
            except Exception:
                pass

    def describe(self) -> str:
        return f"process '{self.name}' (PID: {self.pid or 'auto'})"

    def poll(self) -> TargetStatus:
        self.last_poll_t = time.time()

        # Resolve process by name if PID not supplied
        if self._proc is None:
            self._proc = self._find_proc_by_name(self.name)
            if self._proc is None:
                self.status = TargetStatus.RUNNING
                return self.status
            self.pid = self._proc.pid

        # Inspect process status
        try:
            if not self._proc.is_running() or self._proc.status() == psutil.STATUS_ZOMBIE:
                if self.alert_on_exit:
                    self._pending_alert = f"Sir, process '{self.name}' has terminated."
                self.status = TargetStatus.FINISHED
                return self.status

            if self.cpu_threshold is not None:
                cpu = self._proc.cpu_percent(interval=None)
                if cpu >= self.cpu_threshold:
                    self._pending_alert = f"Sir, process '{self.name}' CPU exceeded {self.cpu_threshold:.0f}% ({cpu:.1f}%)."
                    self.status = TargetStatus.ALERTED
                    return self.status

            if self.mem_mb_threshold is not None:
                mem_mb = self._proc.memory_info().rss / (1024 * 1024)
                if mem_mb >= self.mem_mb_threshold:
                    self._pending_alert = f"Sir, process '{self.name}' memory exceeded {self.mem_mb_threshold:.0f} MB ({mem_mb:.0f} MB)."
                    self.status = TargetStatus.ALERTED
                    return self.status

            self.status = TargetStatus.RUNNING
            return self.status
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            if self.alert_on_exit:
                self._pending_alert = f"Sir, process '{self.name}' is no longer active."
            self.status = TargetStatus.FINISHED
            return self.status

    def _find_proc_by_name(self, name: str) -> psutil.Process | None:
        low = name.lower()
        for p in psutil.process_iter(["pid", "name"]):
            try:
                if low in (p.info["name"] or "").lower():
                    return p
            except Exception:
                pass
        return None
