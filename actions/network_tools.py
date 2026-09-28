# network_tools.py
"""
Network diagnostics available by voice:
  - speed_test   : download / upload / ping via speedtest-cli (falls back to
                   a fast.com request if the library is missing)
  - get_ip       : public and local IP addresses
  - ping         : ICMP ping to a host with loss summary
  - connections  : active TCP connections (non-localhost)
"""
from __future__ import annotations

import platform
import re
import socket
import subprocess
import sys
import urllib.request
from typing import Optional


# ── Helpers ───────────────────────────────────────────────────────────────────

def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "unavailable"


def _public_ip() -> str:
    for url in ("https://api.ipify.org", "https://checkip.amazonaws.com"):
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                return r.read().decode().strip()
        except Exception:
            continue
    return "unavailable"


def _speedtest_cli() -> Optional[dict]:
    """Try speedtest-cli library first, then subprocess."""
    try:
        import speedtest  # type: ignore[import]
        st = speedtest.Speedtest(secure=True)
        st.get_best_server()
        dl = st.download() / 1_000_000
        ul = st.upload() / 1_000_000
        ping = st.results.ping
        return {"download_mbps": round(dl, 1), "upload_mbps": round(ul, 1), "ping_ms": round(ping, 1)}
    except ImportError:
        pass
    except Exception:
        return None

    # subprocess fallback
    try:
        result = subprocess.run(
            ["speedtest", "--format=json-pretty"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            return {
                "download_mbps": round(data["download"]["bandwidth"] / 125_000, 1),
                "upload_mbps":   round(data["upload"]["bandwidth"] / 125_000, 1),
                "ping_ms":       round(data["ping"]["latency"], 1),
            }
    except Exception:
        pass
    return None


def _ping(host: str, count: int = 4) -> dict:
    system = platform.system().lower()
    if system == "windows":
        cmd = ["ping", "-n", str(count), host]
    else:
        cmd = ["ping", "-c", str(count), host]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        output = result.stdout + result.stderr

        # Extract avg RTT
        rtt_match = re.search(r"Average\s*=\s*(\d+)ms", output, re.IGNORECASE)
        if not rtt_match:
            rtt_match = re.search(r"min/avg/max.*?=\s*[\d.]+/([\d.]+)/", output)
        avg_rtt = rtt_match.group(1) if rtt_match else "N/A"

        # Extract loss
        loss_match = re.search(r"(\d+)%\s*(packet\s*)?loss", output, re.IGNORECASE)
        loss = loss_match.group(1) + "%" if loss_match else "N/A"

        return {"host": host, "avg_rtt_ms": avg_rtt, "packet_loss": loss, "raw": output.strip()}
    except subprocess.TimeoutExpired:
        return {"host": host, "avg_rtt_ms": "N/A", "packet_loss": "100%", "raw": "Timed out."}
    except Exception as e:
        return {"host": host, "avg_rtt_ms": "N/A", "packet_loss": "N/A", "raw": str(e)}


def _active_connections() -> list[dict]:
    try:
        import psutil  # type: ignore[import]
        conns = []
        for c in psutil.net_connections(kind="tcp"):
            if c.status == "ESTABLISHED" and c.raddr:
                raddr = f"{c.raddr.ip}:{c.raddr.port}"
                if not raddr.startswith("127.") and not raddr.startswith("::1"):
                    try:
                        proc = psutil.Process(c.pid).name() if c.pid else "unknown"
                    except Exception:
                        proc = "unknown"
                    conns.append({"remote": raddr, "process": proc, "pid": c.pid})
        return conns
    except ImportError:
        return []


# ── Action handler ────────────────────────────────────────────────────────────

def network_tools_action(parameters: dict, **kwargs) -> str:
    action = str(parameters.get("action", "get_ip")).lower().strip()

    if action in ("get_ip", "ip", "my_ip", "whats_my_ip"):
        local  = _local_ip()
        public = _public_ip()
        return f"Local IP: {local} | Public IP: {public}"

    if action in ("speed_test", "speedtest", "speed"):
        result = _speedtest_cli()
        if result:
            return (
                f"Speed test complete — "
                f"Download: {result['download_mbps']} Mbps, "
                f"Upload: {result['upload_mbps']} Mbps, "
                f"Ping: {result['ping_ms']} ms."
            )
        return (
            "Speed test failed. Install speedtest-cli: pip install speedtest-cli"
        )

    if action in ("ping",):
        host = str(parameters.get("host", "8.8.8.8")).strip()
        count = int(parameters.get("count", 4))
        r = _ping(host, count)
        return (
            f"Ping to {r['host']}: avg {r['avg_rtt_ms']} ms, "
            f"packet loss {r['packet_loss']}."
        )

    if action in ("connections", "active_connections", "who_is_connected"):
        conns = _active_connections()
        if not conns:
            return "No established outbound connections found (or psutil is not installed)."
        lines = [f"Active connections ({len(conns)}):"]
        for c in conns[:15]:
            lines.append(f"  [{c['process']} / PID {c['pid']}] → {c['remote']}")
        return "\n".join(lines)

    return (
        f"Unknown network_tools action: '{action}'. "
        "Use: get_ip | speed_test | ping | connections."
    )


# ── Tool declaration ──────────────────────────────────────────────────────────
TOOL = {
    "name": "network_tools",
    "description": (
        "Network diagnostics: check public/local IP, run a speed test, "
        "ping a host, or list active outbound TCP connections."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "get_ip | speed_test | ping | connections",
            },
            "host": {
                "type": "STRING",
                "description": "Hostname or IP to ping (default: 8.8.8.8).",
            },
            "count": {
                "type": "INTEGER",
                "description": "Number of ping packets to send (default: 4).",
            },
        },
        "required": ["action"],
    },
    "handler": network_tools_action,
}
