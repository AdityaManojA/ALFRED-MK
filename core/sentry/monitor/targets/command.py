"""Command Target: Runs a shell command periodically and alerts on status/output change."""
from __future__ import annotations

import subprocess
import time
from core.sentry.monitor.targets.base import MonitorTarget, TargetStatus

COMMAND_TIMEOUT_S: float = 3.0


class CommandTarget(MonitorTarget):
    """Executes a command every N seconds and alerts on exit code or output change."""

    def __init__(
        self,
        target_id: str,
        name: str,
        command: str,
        expected_code: int = 0,
        alert_on_change: bool = False,
        interval_s: float = 10.0,
    ) -> None:
        super().__init__(target_id, name, interval_s)
        self.command = command
        self.expected_code = expected_code
        self.alert_on_change = alert_on_change
        self._last_stdout = ""

    def describe(self) -> str:
        return f"command '{self.command[:35]}'"

    def poll(self) -> TargetStatus:
        self.last_poll_t = time.time()
        try:
            res = subprocess.run(
                self.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=COMMAND_TIMEOUT_S,
            )
            out = res.stdout.strip()
            code = res.returncode

            if code != self.expected_code:
                self._pending_alert = f"Sir, command '{self.name}' exited with code {code}."
                self.status = TargetStatus.ALERTED
                return self.status

            if self.alert_on_change and self._last_stdout and out != self._last_stdout:
                self._pending_alert = f"Sir, output changed for command '{self.name}'."
                self._last_stdout = out
                self.status = TargetStatus.ALERTED
                return self.status

            self._last_stdout = out
            self.status = TargetStatus.RUNNING
            return self.status
        except subprocess.TimeoutExpired:
            self._pending_alert = f"Sir, command '{self.name}' timed out after {COMMAND_TIMEOUT_S}s."
            self.status = TargetStatus.ERROR
            return self.status
        except Exception as exc:
            self.status = TargetStatus.ERROR
            return self.status
