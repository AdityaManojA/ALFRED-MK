"""Behavioural tests for actions.reminder.

Scripts are written under tmp_path; schtasks / systemd-run / at / launchctl
calls are mocked, so nothing is registered with the real OS scheduler.
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import actions.reminder as rem
from actions.reminder import reminder


@pytest.fixture(autouse=True)
def scripts_dir(tmp_path, monkeypatch):
    d = tmp_path / "reminders"
    d.mkdir()
    monkeypatch.setattr(rem, "_scripts_dir", lambda: d)
    return d


def _future(minutes=90):
    t = datetime.now() + timedelta(minutes=minutes)
    return t.strftime("%Y-%m-%d"), t.strftime("%H:%M"), t


def test_sanitise_strips_quotes_backslashes_and_newlines():
    assert rem._sanitise('He said "hi" C:\\tmp \'ok\'\r\nnext') == "He said hi C:tmp ok next"
    assert rem._sanitise("x" * 300) == "x" * 200
    assert rem._sanitise("  abc  ", max_len=2) == "ab"


@pytest.mark.parametrize("system, expected", [("Darwin", "mac"), ("Linux", "linux"), ("Windows", "windows"), ("Other", "windows")])
def test_get_os(system, expected):
    with patch.object(rem.platform, "system", return_value=system):
        assert rem._get_os() == expected


@pytest.mark.parametrize("os_name, marker", [("windows", "win10toast"), ("mac", "osascript"), ("linux", "notify-send")])
def test_write_notify_script_is_valid_python_for_each_os(scripts_dir, os_name, marker):
    path = rem._write_notify_script("T1", 'Take "meds"', os_name)
    assert path == scripts_dir / "T1.py"
    body = path.read_text(encoding="utf-8")
    compile(body, str(path), "exec")  # must be syntactically valid
    assert marker in body
    assert 'message = "Take \\"meds\\""' in body  # embedded via json.dumps
    assert "unlink(missing_ok=True)" in body  # self-deletes after firing


# ── reminder() validation ────────────────────────────────────────────────────

def test_requires_date_and_time():
    assert reminder({"date": "2030-01-01"}) == "I need both a date and a time to set a reminder."


def test_rejects_unparseable_input():
    assert reminder({"date": "tomorrow", "time": "noon"}).startswith("I couldn't parse that date or time.")


def test_rejects_past_time():
    assert reminder({"date": "2000-01-01", "time": "10:00"}) == (
        "That time has already passed — I can't set a reminder in the past."
    )


def test_success_on_linux_dispatches_and_logs(scripts_dir):
    date_s, time_s, target = _future()
    player = MagicMock()
    with patch.object(rem, "_get_os", return_value="linux"), \
         patch.object(rem, "_schedule_linux", return_value="job") as sched:
        out = reminder({"date": date_s, "time": time_s, "message": "Stand up"}, player=player)
    target = target.replace(second=0, microsecond=0)
    assert out == f"Reminder set for {target.strftime('%B %d at %I:%M %p')}."
    task_name = f"ALFREDReminder_{target.strftime('%Y%m%d_%H%M%S')}"
    sched.assert_called_once_with(target, task_name, scripts_dir / f"{task_name}.py")
    player.write_log.assert_called_once()


def test_scheduler_failure_message():
    date_s, time_s, _ = _future()
    with patch.object(rem, "_get_os", return_value="linux"), \
         patch.object(rem, "_schedule_linux", return_value=""):
        assert reminder({"date": date_s, "time": time_s}) == (
            "I couldn't register the reminder with the system scheduler."
        )


def test_scheduler_exception_removes_script(scripts_dir):
    date_s, time_s, _ = _future()
    with patch.object(rem, "_get_os", return_value="linux"), \
         patch.object(rem, "_schedule_linux", side_effect=RuntimeError("boom")):
        out = reminder({"date": date_s, "time": time_s})
    assert out == "Something went wrong while scheduling the reminder."
    assert list(scripts_dir.iterdir()) == []


# ── OS schedulers ────────────────────────────────────────────────────────────

def test_schedule_linux_prefers_systemd_run(tmp_path):
    target = datetime(2030, 6, 1, 7, 30)
    script = tmp_path / "s.py"
    with patch.object(rem.shutil, "which", side_effect=lambda n: "/usr/bin/" + n), \
         patch.object(rem.subprocess, "run", return_value=SimpleNamespace(returncode=0, stderr="")) as run:
        assert rem._schedule_linux(target, "T", script) == "T"
    cmd = run.call_args.args[0]
    assert cmd[:2] == ["systemd-run", "--user"]
    assert "--on-calendar=2030-06-01 07:30:00" in cmd
    assert cmd[-2:] == [sys.executable, str(script)]


def test_schedule_linux_falls_back_to_at(tmp_path):
    target = datetime(2030, 6, 1, 7, 30)
    results = [SimpleNamespace(returncode=1, stderr="no user bus"), SimpleNamespace(returncode=0, stderr="")]
    with patch.object(rem.shutil, "which", return_value="/usr/bin/x"), \
         patch.object(rem.subprocess, "run", side_effect=results) as run:
        assert rem._schedule_linux(target, "T", tmp_path / "s.py") == "T"
    at_call = run.call_args_list[1]
    assert at_call.args[0] == ["at", "07:30 2030-06-01"]
    assert at_call.kwargs["input"].endswith("s.py\n")


def test_schedule_linux_without_tools():
    with patch.object(rem.shutil, "which", return_value=None):
        assert rem._schedule_linux(datetime(2030, 1, 1), "T", Path("s.py")) == ""


def test_schedule_windows_writes_xml_and_cleans_up_on_failure(scripts_dir):
    script = scripts_dir / "T.py"
    script.write_text("x", encoding="utf-8")
    seen = {}

    def fake_run(cmd, **kw):
        xml = Path(cmd[cmd.index("/XML") + 1])
        seen["xml"] = xml.read_text(encoding="utf-16")
        return SimpleNamespace(returncode=1, stderr="Access is denied.", stdout="")

    with patch.object(rem.subprocess, "run", side_effect=fake_run):
        assert rem._schedule_windows(datetime(2030, 6, 1, 7, 30), "T", script, "m") == ""
    assert "<StartBoundary>2030-06-01T07:30:00</StartBoundary>" in seen["xml"]
    assert not script.exists()               # script removed after failure
    assert not (scripts_dir / "T.xml").exists()  # temp xml always removed


def test_schedule_windows_success(scripts_dir):
    script = scripts_dir / "T.py"
    script.write_text("x", encoding="utf-8")
    with patch.object(rem.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run:
        assert rem._schedule_windows(datetime(2030, 6, 1, 7, 30), "T", script, "m") == "T"
    assert run.call_args.args[0][:4] == ["schtasks", "/Create", "/TN", "T"]
    assert script.exists()


def test_schedule_mac_writes_plist(tmp_path, monkeypatch):
    monkeypatch.setattr(rem.Path, "home", classmethod(lambda cls: tmp_path))
    with patch.object(rem.subprocess, "run", return_value=SimpleNamespace(returncode=0, stderr="")):
        label = rem._schedule_mac(datetime(2030, 6, 1, 7, 30), "T", tmp_path / "s.py")
    assert label == "com.alfred.reminder.T"
    plist = (tmp_path / "Library" / "LaunchAgents" / f"{label}.plist").read_text(encoding="utf-8")
    assert "<key>Hour</key>   <integer>7</integer>" in plist
    assert "<key>Minute</key> <integer>30</integer>" in plist
