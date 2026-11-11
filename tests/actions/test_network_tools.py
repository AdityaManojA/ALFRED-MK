"""Behavioural tests for actions.network_tools (sockets, urllib, subprocess, psutil mocked)."""
import io
import json
import subprocess
import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import actions.network_tools as nt
from actions.network_tools import network_tools_action

WIN_PING = """
Pinging 8.8.8.8 with 32 bytes of data:
Reply from 8.8.8.8: bytes=32 time=14ms TTL=117
Packets: Sent = 4, Received = 4, Lost = 0 (0% loss),
Approximate round trip times in milli-seconds:
    Minimum = 12ms, Maximum = 16ms, Average = 14ms
"""

LINUX_PING = """
4 packets transmitted, 3 received, 25% packet loss, time 3004ms
rtt min/avg/max/mdev = 10.123/12.456/15.789/1.234 ms
"""


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


# ── _ping ────────────────────────────────────────────────────────────────────

def test_ping_parses_windows_output():
    with patch.object(nt.platform, "system", return_value="Windows"), \
         patch.object(nt.subprocess, "run", return_value=SimpleNamespace(stdout=WIN_PING, stderr="")) as run:
        r = nt._ping("8.8.8.8", 4)
    assert run.call_args.args[0] == ["ping", "-n", "4", "8.8.8.8"]
    assert r["avg_rtt_ms"] == "14" and r["packet_loss"] == "0%"


def test_ping_parses_linux_output():
    with patch.object(nt.platform, "system", return_value="Linux"), \
         patch.object(nt.subprocess, "run", return_value=SimpleNamespace(stdout=LINUX_PING, stderr="")) as run:
        r = nt._ping("example.com", 2)
    assert run.call_args.args[0] == ["ping", "-c", "2", "example.com"]
    assert r["avg_rtt_ms"] == "12.456" and r["packet_loss"] == "25%"


def test_ping_unparseable_and_timeout():
    with patch.object(nt.subprocess, "run", return_value=SimpleNamespace(stdout="??", stderr="")):
        r = nt._ping("h")
    assert r["avg_rtt_ms"] == "N/A" and r["packet_loss"] == "N/A"
    with patch.object(nt.subprocess, "run", side_effect=subprocess.TimeoutExpired("ping", 20)):
        r = nt._ping("h")
    assert r["packet_loss"] == "100%" and r["raw"] == "Timed out."


# ── IP helpers ───────────────────────────────────────────────────────────────

def test_public_ip_falls_through_to_second_provider():
    responses = [OSError("down"), _Resp(b" 203.0.113.9\n")]

    def fake_urlopen(url, timeout):
        r = responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    with patch.object(nt.urllib.request, "urlopen", side_effect=fake_urlopen):
        assert nt._public_ip() == "203.0.113.9"


def test_public_ip_unavailable():
    with patch.object(nt.urllib.request, "urlopen", side_effect=OSError("down")):
        assert nt._public_ip() == "unavailable"


def test_local_ip_from_udp_socket():
    sock = MagicMock()
    sock.getsockname.return_value = ("192.168.1.20", 5555)
    with patch.object(nt.socket, "socket", return_value=sock):
        assert nt._local_ip() == "192.168.1.20"
    with patch.object(nt.socket, "socket", side_effect=OSError("no net")):
        assert nt._local_ip() == "unavailable"


# ── speed test ───────────────────────────────────────────────────────────────

def test_speedtest_library_path():
    st = MagicMock()
    st.download.return_value = 95_440_000
    st.upload.return_value = 20_050_000
    st.results.ping = 11.26
    fake = types.ModuleType("speedtest")
    fake.Speedtest = MagicMock(return_value=st)
    with patch.dict(sys.modules, {"speedtest": fake}):
        assert nt._speedtest_cli() == {"download_mbps": 95.4, "upload_mbps": 20.1, "ping_ms": 11.3}


def test_speedtest_subprocess_fallback_when_library_missing():
    payload = json.dumps({
        "download": {"bandwidth": 12_500_000},
        "upload": {"bandwidth": 2_500_000},
        "ping": {"latency": 9.87},
    })
    with patch.dict(sys.modules, {"speedtest": None}), \
         patch.object(nt.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=payload)):
        assert nt._speedtest_cli() == {"download_mbps": 100.0, "upload_mbps": 20.0, "ping_ms": 9.9}


def test_speedtest_library_error_returns_none():
    fake = types.ModuleType("speedtest")
    fake.Speedtest = MagicMock(side_effect=RuntimeError("403"))
    with patch.dict(sys.modules, {"speedtest": fake}):
        assert nt._speedtest_cli() is None


# ── connections ──────────────────────────────────────────────────────────────

def test_active_connections_filters_localhost_and_non_established():
    conn = lambda ip, status="ESTABLISHED", pid=10: SimpleNamespace(
        status=status, raddr=SimpleNamespace(ip=ip, port=443), pid=pid
    )
    fake = types.ModuleType("psutil")
    fake.net_connections = lambda kind: [
        conn("140.82.112.3"),
        conn("127.0.0.1"),
        conn("1.1.1.1", status="TIME_WAIT"),
        SimpleNamespace(status="ESTABLISHED", raddr=(), pid=1),
        conn("8.8.8.8", pid=None),
    ]
    fake.Process = lambda pid: SimpleNamespace(name=lambda: "chrome.exe")
    with patch.dict(sys.modules, {"psutil": fake}):
        out = nt._active_connections()
    assert out == [
        {"remote": "140.82.112.3:443", "process": "chrome.exe", "pid": 10},
        {"remote": "8.8.8.8:443", "process": "unknown", "pid": None},
    ]


# ── action dispatch ──────────────────────────────────────────────────────────

def test_action_get_ip():
    with patch.object(nt, "_local_ip", return_value="10.0.0.2"), \
         patch.object(nt, "_public_ip", return_value="203.0.113.1"):
        assert network_tools_action({"action": "whats_my_ip"}) == (
            "Local IP: 10.0.0.2 | Public IP: 203.0.113.1"
        )


def test_action_speed_test_success_and_failure():
    with patch.object(nt, "_speedtest_cli", return_value={"download_mbps": 1, "upload_mbps": 2, "ping_ms": 3}):
        assert network_tools_action({"action": "speed"}) == (
            "Speed test complete — Download: 1 Mbps, Upload: 2 Mbps, Ping: 3 ms."
        )
    with patch.object(nt, "_speedtest_cli", return_value=None):
        assert network_tools_action({"action": "speedtest"}).startswith("Speed test failed.")


def test_action_ping_uses_defaults():
    with patch.object(nt, "_ping", return_value={"host": "8.8.8.8", "avg_rtt_ms": "5", "packet_loss": "0%"}) as p:
        out = network_tools_action({"action": "ping"})
    p.assert_called_once_with("8.8.8.8", 4)
    assert out == "Ping to 8.8.8.8: avg 5 ms, packet loss 0%."


def test_action_connections_caps_at_fifteen():
    conns = [{"remote": f"1.1.1.{i}:80", "process": "p", "pid": i} for i in range(20)]
    with patch.object(nt, "_active_connections", return_value=conns):
        out = network_tools_action({"action": "connections"})
    lines = out.splitlines()
    assert lines[0] == "Active connections (20):"
    assert len(lines) == 16


def test_action_connections_empty_and_unknown():
    with patch.object(nt, "_active_connections", return_value=[]):
        assert network_tools_action({"action": "who_is_connected"}).startswith("No established")
    assert network_tools_action({"action": "hack"}).startswith("Unknown network_tools action: 'hack'")
