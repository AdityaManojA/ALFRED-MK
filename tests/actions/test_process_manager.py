"""Behavioural tests for actions.process_manager using a fake psutil module."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import actions.process_manager as pm
from actions.process_manager import process_manager_action


class NoSuchProcess(Exception):
    pass


class AccessDenied(Exception):
    pass


class FakeProc:
    def __init__(self, pid, name, cmdline=(), cpu=0.0, mem=0.0, rss=0, deny=False, exe="/bin/x"):
        self.pid = pid
        self._name = name
        self._deny = deny
        self._exe = exe
        self.info = {
            "pid": pid,
            "name": name,
            "cmdline": list(cmdline),
            "cpu_percent": cpu,
            "memory_percent": mem,
            "memory_info": SimpleNamespace(rss=rss) if rss else None,
        }
        self.terminated = self.suspended = self.resumed = False

    def name(self):
        return self._name

    def cpu_percent(self, interval=None):
        return self.info["cpu_percent"]

    def exe(self):
        return self._exe

    def _guard(self):
        if self._deny:
            raise AccessDenied()

    def terminate(self):
        self._guard()
        self.terminated = True

    def suspend(self):
        self._guard()
        self.suspended = True

    def resume(self):
        self._guard()
        self.resumed = True


def make_psutil(procs):
    by_pid = {p.pid: p for p in procs}

    def process(pid):
        if pid not in by_pid:
            raise NoSuchProcess()
        return by_pid[pid]

    return SimpleNamespace(
        process_iter=lambda attrs=None: list(procs),
        Process=process,
        NoSuchProcess=NoSuchProcess,
        AccessDenied=AccessDenied,
    )


@pytest.fixture
def procs():
    return [
        FakeProc(1, "chrome.exe", cpu=50.0, mem=10.0, rss=500 * 1_048_576),
        FakeProc(2, "python", cmdline=["python", "discord_bot.py"], cpu=5.0, mem=30.0, rss=100 * 1_048_576),
        FakeProc(3, "system", cpu=1.0, mem=1.0, deny=True),
    ]


@pytest.fixture
def fake_psutil(procs):
    ps = make_psutil(procs)
    with patch.object(pm, "_get_psutil", return_value=ps):
        yield ps


def test_missing_psutil():
    with patch.object(pm, "_get_psutil", return_value=None):
        assert process_manager_action({}) == "psutil is not installed. Run: pip install psutil"
        assert pm._top_procs() == []
        assert pm._find_procs_by_name("x") == []


def test_find_matches_name_or_cmdline(fake_psutil):
    assert [p.pid for p in pm._find_procs_by_name("CHROME")] == [1]
    assert [p.pid for p in pm._find_procs_by_name("discord")] == [2]


def test_top_procs_sort_orders(fake_psutil):
    assert [p["pid"] for p in pm._top_procs("cpu", 2)] == [1, 2]
    assert [p["pid"] for p in pm._top_procs("ram", 3)] == [2, 1, 3]
    top = pm._top_procs("cpu", 1)[0]
    assert top["mem_mb"] == 500.0
    assert pm._top_procs("cpu", 3)[2]["mem_mb"] == 0  # missing memory_info


def test_list_heavy_default_cpu(fake_psutil):
    out = process_manager_action({"action": "list_heavy"})
    lines = out.splitlines()
    assert lines[0] == "Top processes by CPU:"
    assert lines[1] == "  [1] chrome.exe — CPU 50.0%  RAM 500.0 MB (10.0%)"


def test_ram_hogs_sorts_by_memory(fake_psutil):
    out = process_manager_action({"action": "ram_hogs"})
    assert out.splitlines()[0] == "Top processes by RAM:"
    assert out.splitlines()[1].startswith("  [2] python")


def test_find_action(fake_psutil):
    assert process_manager_action({"action": "find"}) == "Provide a 'name' to search for."
    assert process_manager_action({"action": "find", "name": "zzz"}) == (
        "No process matching 'zzz' is currently running."
    )
    out = process_manager_action({"action": "is_running", "name": "chrome"})
    assert out == "Found 1 process(es) matching 'chrome':\n  [1] chrome.exe — CPU 50.0%"


def test_kill_by_pid(fake_psutil, procs):
    assert process_manager_action({"action": "kill", "pid": 1}) == "Terminated process 'chrome.exe' (PID 1)."
    assert procs[0].terminated
    assert process_manager_action({"action": "kill", "pid": 99}) == "No process with PID 99 found."
    assert process_manager_action({"action": "kill", "pid": 3}) == "Access denied — cannot terminate PID 3."


def test_kill_by_name_reports_killed_and_denied(fake_psutil, procs):
    procs.append(FakeProc(4, "chrome.exe", deny=True))
    out = process_manager_action({"action": "terminate", "name": "chrome"})
    assert out == (
        "Terminated: chrome.exe (PID 1). "
        "Access denied for PID(s): 4 — try running Alfred as administrator."
    )


def test_kill_validations(fake_psutil):
    assert process_manager_action({"action": "kill"}) == "Provide a 'name' or 'pid' to kill."
    assert process_manager_action({"action": "kill", "name": "nope"}) == "No process matching 'nope' found."


def test_restart_terminates_and_relaunches(fake_psutil, procs):
    with patch("subprocess.Popen") as popen:
        out = process_manager_action({"action": "restart", "name": "chrome"})
    assert out == "Restarted 'chrome'."
    assert procs[0].terminated
    popen.assert_called_once_with(["/bin/x"])


def test_restart_validations(fake_psutil):
    assert process_manager_action({"action": "restart"}) == "Provide a 'name' to restart."
    assert process_manager_action({"action": "restart", "name": "zzz"}) == (
        "No process matching 'zzz' found to restart."
    )


def test_suspend_and_resume(fake_psutil, procs):
    assert process_manager_action({"action": "suspend", "name": "chrome"}) == "Suspended 'chrome.exe' (PID 1)."
    assert procs[0].suspended
    assert process_manager_action({"action": "resume_process", "pid": 1}) == "Resumed 'chrome.exe' (PID 1)."
    assert procs[0].resumed
    assert process_manager_action({"action": "suspend", "name": "zzz"}) == "Process 'zzz' not found."
    assert process_manager_action({"action": "suspend", "pid": 3}) == "Access denied — cannot suspend PID 3."


def test_unknown_action(fake_psutil):
    assert process_manager_action({"action": "nuke"}).startswith("Unknown process_manager action: 'nuke'")
