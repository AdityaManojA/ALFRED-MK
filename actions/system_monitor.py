"""
actions/system_monitor.py — System Metric Checks, Process Tree Watchdog & Security Socket Monitor.

Features:
1. Snapshot metric checks (CPU, RAM, GPU via NVML, thermal temps).
2. watch_process_tree(): Monitored non-system processes exceeding 90% CPU for >10s.
3. Network Socket Tracking: Detects active outbound TCP/UDP on non-standard ports.
4. Auto-Throttling: throttle_process(pid) lowers process priority class (BELOW_NORMAL) or suspends execution.
5. Defensive Exclusion: Protects system executables, IDE compilers, and ALFRED's own process tree.
6. Confirmation Gate: Never terminates a process without explicit confirmation via core/confirm.py.
7. Red-Tag Alert Telemetry:
   [monitor] Resource anomaly: Process <PID:Name> utilizing <X>% CPU
   [monitor] Suspicious socket: Process <PID:Name> -> <Remote_IP>:<Port>
"""
from __future__ import annotations

import ctypes
import ipaddress
import os
import platform
import re
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import psutil

from core import confirm

_RED = "\033[91m"
_RESET = "\033[0m"
_OS = platform.system()  # "Windows" | "Darwin" | "Linux"

DEFAULT_THRESHOLDS = {
    "cpu": 90.0,
    "ram": 90.0,
    "temp": 85.0,
    "gpu": 95.0,
}

_COOLDOWN = 300
_CPU_STREAK = 3

# ── NVML DLL cache (Windows: nvml.dll, Linux: libnvidia-ml.so.1) ─────────────
_nvml_lib: object = None
_nvml_ok: object = None  # None=untested True=works False=unavailable

# ── Probe caches (pynvml and WMI connections are slow to recreate) ───────────
_pynvml_obj: object = None
_pynvml_handle: object = None
_pynvml_ok: object = None  # None=untested True=works False=unavailable

_wmi_conn: object = None
_wmi_ok: object = None  # None=untested True=works False=unavailable

# ── Process Watchdog & Throttling Protections ────────────────────────────────
_PROTECTED_PROCESS_NAMES = {
    # Windows core system
    "system", "system idle process", "registry", "smss.exe", "csrss.exe",
    "wininit.exe", "services.exe", "lsass.exe", "svchost.exe", "explorer.exe",
    "dwm.exe", "spoolsv.exe", "taskmgr.exe", "winlogon.exe", "fontdrvhost.exe",
    "sihost.exe", "runtimebroker.exe", "searchhost.exe", "startmenuexperiencehost.exe",
    # Unix / macOS core system
    "kernel_task", "launchd", "systemd", "init", "kthreadd", "systemd-journald",
    # IDEs, Compilers & Tools
    "code.exe", "code", "devenv.exe", "cl.exe", "gcc.exe", "g++.exe", "rustc.exe",
    "javac.exe", "cargo.exe", "git.exe", "wt.exe", "windowsterminal.exe",
    "powershell.exe", "cmd.exe", "bash"
}

# Standard common outbound service ports (ignore from suspicious socket alerts)
_STANDARD_PORTS = {
    80, 443, 53, 123, 853, 22, 21, 25, 110, 143, 465, 587, 993, 995,
    5353, 1900, 8080, 8443, 3000, 5173
}

# In-memory high CPU streak tracker: pid -> {"first_seen": timestamp, "last_seen": timestamp, "name": str, "alerted": bool}
_CPU_STREAK_TRACKER: Dict[int, Dict[str, Any]] = {}
_TRACKER_LOCK = threading.Lock()


def _nvml_gpu() -> float:
    """GPU utilisation via NVML — zero subprocess on all platforms."""
    global _nvml_lib, _nvml_ok
    if _nvml_ok is False:
        return -1.0
    try:
        class _Util(ctypes.Structure):
            _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]

        if _nvml_lib is None:
            if _OS == "Windows":
                candidates = ("nvml", r"C:\Windows\System32\nvml.dll")
                _load = ctypes.WinDLL
            else:
                candidates = (
                    "libnvidia-ml.so.1",
                    "libnvidia-ml.so",
                    "libnvidia-ml.dylib",
                )
                _load = ctypes.CDLL
            for name in candidates:
                try:
                    lib = _load(name)
                    lib.nvmlInit_v2()
                    _nvml_lib = lib
                    break
                except Exception:
                    continue

        if _nvml_lib is None:
            _nvml_ok = False
            return -1.0

        dev = ctypes.c_void_p()
        _nvml_lib.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(dev))
        u = _Util()
        _nvml_lib.nvmlDeviceGetUtilizationRates(dev, ctypes.byref(u))
        _nvml_ok = True
        return float(u.gpu)
    except Exception:
        _nvml_ok = False
        return -1.0


def _get_gpu_usage() -> float:
    global _pynvml_obj, _pynvml_handle, _pynvml_ok
    if _pynvml_ok is not False:
        try:
            if _pynvml_handle is None:
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", category=FutureWarning)
                    import pynvml  # type: ignore
                pynvml.nvmlInit()
                _pynvml_obj = pynvml
                _pynvml_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                _pynvml_ok = True
            return float(_pynvml_obj.nvmlDeviceGetUtilizationRates(_pynvml_handle).gpu)
        except Exception:
            _pynvml_ok = False
            _pynvml_handle = None

    return _nvml_gpu()


def _get_cpu_temp() -> float:
    try:
        temps = psutil.sensors_temperatures()
        for name in ["coretemp", "k10temp", "cpu_thermal", "acpitz",
                     "cpu-thermal", "zenpower", "it8688"]:
            if name in temps and temps[name]:
                return temps[name][0].current
        for entries in temps.values():
            if entries:
                return entries[0].current
    except Exception:
        pass

    global _wmi_conn, _wmi_ok
    if _OS == "Windows" and _wmi_ok is not False:
        try:
            if _wmi_conn is None:
                import wmi  # type: ignore
                _wmi_conn = wmi.WMI(namespace="root/wmi")
                _wmi_ok = True
            tz = _wmi_conn.MSAcpi_ThermalZoneTemperature()
            if tz:
                return (tz[0].CurrentTemperature / 10.0) - 273.15
        except Exception:
            _wmi_ok = False
            _wmi_conn = None

    return -1.0


def get_system_status() -> dict:
    """Snapshot of current system metrics for the system_status tool."""
    cpu = psutil.cpu_percent(interval=0.1)
    ram = psutil.virtual_memory()
    temp = _get_cpu_temp()
    gpu = _get_gpu_usage()

    boot_time = psutil.boot_time()
    uptime_secs = time.time() - boot_time
    uptime_h = int(uptime_secs // 3600)
    uptime_m = int((uptime_secs % 3600) // 60)

    return {
        "cpu_percent": round(cpu, 1),
        "ram_percent": round(ram.percent, 1),
        "ram_used_gb": round(ram.used / 1024 ** 3, 1),
        "ram_total_gb": round(ram.total / 1024 ** 3, 1),
        "cpu_temp_c": round(temp, 1) if temp > 0 else None,
        "gpu_percent": round(gpu, 1) if gpu >= 0 else None,
        "uptime": f"{uptime_h}h {uptime_m}m",
        "process_count": len(psutil.pids()),
    }


def is_protected_process(proc_or_pid: Any) -> bool:
    """
    Check if a process belongs to core system executables, IDE compilers,
    or ALFRED's own process tree to prevent unauthorized throttling or termination.
    """
    try:
        if isinstance(proc_or_pid, (int, str)):
            proc = psutil.Process(int(proc_or_pid))
        else:
            proc = proc_or_pid

        pid = proc.pid
        if pid <= 4:
            return True

        # ALFRED's own process tree
        alfred_pid = os.getpid()
        if pid == alfred_pid:
            return True
        try:
            alfred_children = {p.pid for p in psutil.Process(alfred_pid).children(recursive=True)}
            if pid in alfred_children:
                return True
        except Exception:
            pass

        # Protected names
        name = proc.name().lower()
        if name in _PROTECTED_PROCESS_NAMES or any(name.startswith(p.replace(".exe", "")) for p in _PROTECTED_PROCESS_NAMES):
            return True

    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
        return True
    except Exception:
        return True

    return False


def _is_private_or_loopback(ip: str) -> bool:
    """Check if remote IP address is private, loopback, or multicast."""
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_private or addr.is_loopback or addr.is_multicast or addr.is_unspecified
    except Exception:
        return False


def track_suspicious_sockets() -> List[Dict[str, Any]]:
    """
    Inspect active outbound TCP/UDP connections for non-standard remote ports.
    Emits red-tag telemetry: [monitor] Suspicious socket: Process <PID:Name> -> <Remote_IP>:<Port>
    """
    suspicious: List[Dict[str, Any]] = []
    try:
        connections = psutil.net_connections(kind="inet")
    except Exception:
        return []

    for conn in connections:
        if not conn.raddr or conn.status != "ESTABLISHED":
            continue

        if hasattr(conn.raddr, "ip"):
            remote_ip = str(conn.raddr.ip)
            remote_port = int(conn.raddr.port)
        elif isinstance(conn.raddr, (tuple, list)) and len(conn.raddr) >= 2:
            remote_ip = str(conn.raddr[0])
            remote_port = int(conn.raddr[1])
        else:
            continue

        # Ignore local, private, and standard service ports
        if _is_private_or_loopback(remote_ip) or remote_port in _STANDARD_PORTS:
            continue

        # Non-standard remote port detected on public IP
        pid = conn.pid or 0
        proc_name = "unknown"
        if pid > 0:
            try:
                proc_name = psutil.Process(pid).name()
            except Exception:
                pass

        alert_entry = {
            "pid": pid,
            "name": proc_name,
            "local_addr": f"{conn.laddr.ip}:{conn.laddr.port}",
            "remote_addr": f"{remote_ip}:{remote_port}",
            "remote_port": remote_port,
            "status": conn.status,
        }
        suspicious.append(alert_entry)
        print(f"{_RED}[monitor]{_RESET} Suspicious socket: Process <{pid}:{proc_name}> -> {remote_ip}:{remote_port}")

    return suspicious


def watch_process_tree(
    cpu_threshold: float = 90.0,
    duration_seconds: float = 10.0,
    check_sockets: bool = True,
    sample_interval: float = 0.0,
) -> Dict[str, Any]:
    """
    Monitor active process tree for resource anomalies and suspicious sockets:
    1. Monitors single non-system processes exceeding 90% CPU utilization for >10 consecutive seconds.
    2. Emits alert: [monitor] Resource anomaly: Process <PID:Name> utilizing <X>% CPU
    3. Tracks active outbound TCP/UDP connections for non-standard remote ports.
    """
    global _CPU_STREAK_TRACKER
    now = time.monotonic()
    high_cpu_anomalies: List[Dict[str, Any]] = []
    active_pids: Set[int] = set()

    try:
        # Collect current CPU percentages
        for proc in psutil.process_iter(["pid", "name", "cpu_percent"]):
            try:
                pid = proc.info["pid"]
                active_pids.add(pid)
                cpu = proc.info["cpu_percent"] or 0.0

                if cpu >= cpu_threshold and not is_protected_process(proc):
                    with _TRACKER_LOCK:
                        if pid not in _CPU_STREAK_TRACKER:
                            _CPU_STREAK_TRACKER[pid] = {
                                "first_seen": now,
                                "last_seen": now,
                                "name": proc.info["name"],
                                "peak_cpu": cpu,
                                "alerted": False,
                            }
                        else:
                            rec = _CPU_STREAK_TRACKER[pid]
                            rec["last_seen"] = now
                            rec["peak_cpu"] = max(rec["peak_cpu"], cpu)

                            consecutive_sec = now - rec["first_seen"]
                            if consecutive_sec >= duration_seconds and not rec["alerted"]:
                                rec["alerted"] = True
                                anomaly = {
                                    "pid": pid,
                                    "name": rec["name"],
                                    "cpu_percent": round(cpu, 1),
                                    "duration_seconds": round(consecutive_sec, 1),
                                }
                                high_cpu_anomalies.append(anomaly)
                                print(f"{_RED}[monitor]{_RESET} Resource anomaly: Process <{pid}:{rec['name']}> utilizing {cpu:.1f}% CPU")
                else:
                    with _TRACKER_LOCK:
                        # Clear tracker if CPU dropped below threshold
                        _CPU_STREAK_TRACKER.pop(pid, None)

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Prune terminated PIDs from tracker
        with _TRACKER_LOCK:
            dead_pids = set(_CPU_STREAK_TRACKER.keys()) - active_pids
            for d in dead_pids:
                _CPU_STREAK_TRACKER.pop(d, None)

    except Exception as e:
        print(f"{_RED}[monitor]{_RESET} Error inspecting process tree: {e}")

    suspicious_sockets = track_suspicious_sockets() if check_sockets else []

    return {
        "status": "ok",
        "timestamp": time.time(),
        "high_cpu_anomalies": high_cpu_anomalies,
        "suspicious_sockets": suspicious_sockets,
        "active_processes": len(active_pids),
    }


def throttle_process(pid: int, pause: bool = False) -> Dict[str, Any]:
    """
    Lower process priority class (BELOW_NORMAL_PRIORITY_CLASS) or pause process execution.
    Protects core system executables, IDE compilers, and ALFRED's own process tree.
    """
    try:
        proc = psutil.Process(pid)
        name = proc.name()

        if is_protected_process(proc):
            msg = f"Cannot throttle protected/system process <{pid}:{name}>."
            print(f"{_RED}[monitor]{_RESET} [protect] {msg}")
            return {"status": "rejected", "message": msg, "pid": pid, "name": name}

        if pause:
            proc.suspend()
            action_desc = "suspended execution"
        else:
            if _OS == "Windows":
                proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
                action_desc = "set priority to BELOW_NORMAL"
            else:
                proc.nice(10)
                action_desc = "set nice level to +10"

        print(f"\033[93m[monitor]\033[0m [throttle] Process <{pid}:{name}>: {action_desc}")
        return {
            "status": "throttled",
            "pid": pid,
            "name": name,
            "action": action_desc,
            "message": f"Successfully throttled process <{pid}:{name}> ({action_desc}).",
        }

    except psutil.NoSuchProcess:
        return {"status": "error", "message": f"Process {pid} no longer exists."}
    except Exception as e:
        return {"status": "error", "message": f"Failed to throttle process {pid}: {e}"}


def resume_process(pid: int) -> Dict[str, Any]:
    """Resume a paused process and restore normal priority."""
    try:
        proc = psutil.Process(pid)
        name = proc.name()

        proc.resume()
        if _OS == "Windows":
            proc.nice(psutil.NORMAL_PRIORITY_CLASS)
        else:
            proc.nice(0)

        print(f"\033[92m[monitor]\033[0m [resume] Process <{pid}:{name}> resumed to NORMAL priority.")
        return {
            "status": "resumed",
            "pid": pid,
            "name": name,
            "message": f"Process <{pid}:{name}> resumed to NORMAL priority.",
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to resume process {pid}: {e}"}


def terminate_process(pid: int, ask_confirmation: bool = True) -> Dict[str, Any]:
    """
    Terminate a process. NEVER terminates without explicit confirmation via core/confirm.py.
    """
    try:
        proc = psutil.Process(pid)
        name = proc.name()

        if is_protected_process(proc):
            msg = f"Cannot terminate protected/system process <{pid}:{name}>."
            print(f"{_RED}[monitor]{_RESET} [protect] {msg}")
            return {"status": "rejected", "message": msg}

        def _do_terminate() -> str:
            try:
                proc.terminate()
                return f"Process <{pid}:{name}> terminated successfully."
            except Exception as e:
                return f"Failed to terminate <{pid}:{name}>: {e}"

        if ask_confirmation:
            key = f"terminate_proc_{pid}_{int(time.time())}"
            title = f"Terminate Process: {name} (PID: {pid})"
            detail = f"Confirm immediate termination of process <{pid}:{name}>."
            msg = confirm.request(key=key, title=title, detail=detail, run=_do_terminate)
            return {
                "status": "pending_confirmation",
                "confirmation_key": key,
                "message": msg,
            }

        res_msg = _do_terminate()
        return {"status": "terminated", "message": res_msg}

    except psutil.NoSuchProcess:
        return {"status": "error", "message": f"Process {pid} no longer exists."}
    except Exception as e:
        return {"status": "error", "message": f"Error terminating process {pid}: {e}"}


class SystemMonitor:
    """
    Stateful monitor — cooldown state persists across session reconnections.
    Call check() periodically; returns a [SYSTEM_ALERT] string or None.
    """

    def __init__(self, thresholds: dict | None = None):
        self.thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
        self._last_alert: dict[str, float] = {}
        self._cpu_streak = 0

    def _can_alert(self, key: str) -> bool:
        return (time.monotonic() - self._last_alert.get(key, 0)) > _COOLDOWN

    def _record(self, key: str):
        self._last_alert[key] = time.monotonic()

    def check(self) -> str | None:
        try:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            temp = _get_cpu_temp()
            gpu = _get_gpu_usage()
        except Exception:
            return None

        alerts: list[str] = []

        if cpu >= self.thresholds["cpu"]:
            self._cpu_streak += 1
            if self._cpu_streak >= _CPU_STREAK and self._can_alert("cpu"):
                alerts.append(
                    f"[SYSTEM_ALERT] CPU usage has been critically high ({cpu:.0f}%) "
                    "for several seconds. Warn the user in their language and suggest "
                    "closing heavy applications."
                )
                self._record("cpu")
                self._cpu_streak = 0
        else:
            self._cpu_streak = 0

        if ram >= self.thresholds["ram"] and self._can_alert("ram"):
            alerts.append(
                f"[SYSTEM_ALERT] RAM is at {ram:.0f}% — nearly exhausted. "
                "Warn the user in their language and suggest freeing memory."
            )
            self._record("ram")

        if temp > 0 and temp >= self.thresholds["temp"] and self._can_alert("temp"):
            alerts.append(
                f"[SYSTEM_ALERT] CPU temperature is {temp:.0f}°C — above the safe limit. "
                "Warn the user in their language and advise reducing system load "
                "or checking cooling."
            )
            self._record("temp")

        if gpu >= 0 and gpu >= self.thresholds["gpu"] and self._can_alert("gpu"):
            alerts.append(
                f"[SYSTEM_ALERT] GPU load is at {gpu:.0f}%. "
                "Briefly inform the user in their language."
            )
            self._record("gpu")

        # Also trigger lightweight process tree watchdog scan
        watch_res = watch_process_tree(check_sockets=False)
        for anomaly in watch_res.get("high_cpu_anomalies", []):
            alerts.append(
                f"[SYSTEM_ALERT] Process {anomaly['name']} (PID: {anomaly['pid']}) has utilized "
                f"{anomaly['cpu_percent']}% CPU for over {anomaly['duration_seconds']}s."
            )

        return " ".join(alerts) if alerts else None


# ── Action Handler for ALFRED ────────────────────────────────────────────────
def system_monitor_action(parameters: dict, player=None, speak=None, **kwargs) -> str:
    """Action handler called by ALFRED action dispatcher."""
    action = str(parameters.get("action", "status")).lower().strip()

    if action in ("status", "metrics"):
        st = get_system_status()
        temp_str = f", Temp: {st['cpu_temp_c']}°C" if st["cpu_temp_c"] else ""
        gpu_str = f", GPU: {st['gpu_percent']}%" if st["gpu_percent"] is not None else ""
        return (
            f"System Status: CPU {st['cpu_percent']}%, RAM {st['ram_percent']}% "
            f"({st['ram_used_gb']}/{st['ram_total_gb']} GB){temp_str}{gpu_str}, "
            f"Uptime: {st['uptime']}, Active Processes: {st['process_count']}."
        )

    elif action in ("watch", "process_tree", "processes"):
        cpu_thresh = float(parameters.get("cpu_threshold", 90.0))
        duration = float(parameters.get("duration", 10.0))
        res = watch_process_tree(cpu_threshold=cpu_thresh, duration_seconds=duration, check_sockets=True)
        anomalies = res.get("high_cpu_anomalies", [])
        sockets = res.get("suspicious_sockets", [])

        lines = [f"Process tree monitored ({res['active_processes']} processes):"]
        if anomalies:
            lines.append("Resource Anomalies (>90% CPU):")
            for a in anomalies:
                lines.append(f"- <{a['pid']}:{a['name']}>: {a['cpu_percent']}% CPU ({a['duration_seconds']}s)")
        else:
            lines.append("No sustained high-CPU resource anomalies detected.")

        if sockets:
            lines.append("Suspicious / Non-standard Outbound Sockets:")
            for s in sockets[:5]:
                lines.append(f"- <{s['pid']}:{s['name']}> -> {s['remote_addr']}")
        else:
            lines.append("No suspicious outbound network sockets detected.")

        return "\n".join(lines)

    elif action in ("throttle", "lower_priority"):
        pid_val = parameters.get("pid")
        if not pid_val:
            return "Please provide a 'pid' to throttle."
        pause = bool(parameters.get("pause", False))
        res = throttle_process(int(pid_val), pause=pause)
        return str(res.get("message", res.get("status")))

    elif action == "resume":
        pid_val = parameters.get("pid")
        if not pid_val:
            return "Please provide a 'pid' to resume."
        res = resume_process(int(pid_val))
        return str(res.get("message", res.get("status")))

    elif action in ("terminate", "kill"):
        pid_val = parameters.get("pid")
        if not pid_val:
            return "Please provide a 'pid' to terminate."
        res = terminate_process(int(pid_val), ask_confirmation=True)
        return str(res.get("message", res.get("status")))

    elif action in ("sockets", "connections"):
        sockets = track_suspicious_sockets()
        if not sockets:
            return "All active outbound network sockets are connected to standard trusted service ports."
        lines = [f"Detected {len(sockets)} outbound connection(s) on non-standard remote ports:"]
        for s in sockets:
            lines.append(f"- <{s['pid']}:{s['name']}> -> {s['remote_addr']} (Port {s['remote_port']})")
        return "\n".join(lines)

    return f"Unknown system_monitor action: '{action}'"


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "system_monitor",
    "description": (
        "Monitors system metrics, process resource anomalies, and network sockets. "
        "Allows inspecting high-CPU process streaks (>90% for >10s), tracking outbound sockets, "
        "and throttling runaway tasks."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "status | watch | throttle | resume | terminate | sockets"
            },
            "pid": {
                "type": "INTEGER",
                "description": "Process ID (PID) to inspect, throttle, resume, or terminate"
            },
            "pause": {
                "type": "BOOLEAN",
                "description": "Whether to pause/suspend execution when throttling (default: false)"
            },
            "cpu_threshold": {
                "type": "NUMBER",
                "description": "CPU percentage threshold for resource anomalies (default: 90.0)"
            },
            "duration": {
                "type": "NUMBER",
                "description": "Consecutive duration in seconds to trigger alert (default: 10.0)"
            }
        },
        "required": ["action"]
    },
    "handler": system_monitor_action,
}
