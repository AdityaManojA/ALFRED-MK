# process_manager.py
"""
Voice-driven process management using psutil.
Kill a named process, list CPU/RAM hogs, or find what owns a window.
Confirmation is requested before killing so Alfred doesn't fire blindly.
"""
from __future__ import annotations

import sys
from typing import Optional


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_psutil():
    try:
        import psutil  # type: ignore[import]
        return psutil
    except ImportError:
        return None


def _find_procs_by_name(name: str):
    """Return all processes whose name or cmdline contains `name` (case-insensitive)."""
    psutil = _get_psutil()
    if not psutil:
        return []
    fragment = name.lower()
    matches = []
    for p in psutil.process_iter(["pid", "name", "cmdline", "cpu_percent", "memory_percent"]):
        try:
            proc_name = (p.info["name"] or "").lower()
            cmdline   = " ".join(p.info["cmdline"] or []).lower()
            if fragment in proc_name or fragment in cmdline:
                matches.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return matches


def _top_procs(by: str = "cpu", n: int = 10) -> list[dict]:
    psutil = _get_psutil()
    if not psutil:
        return []

    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "memory_info"]):
        try:
            procs.append({
                "pid":    p.info["pid"],
                "name":   p.info["name"] or "unknown",
                "cpu":    p.info["cpu_percent"] or 0.0,
                "mem_pct": p.info["memory_percent"] or 0.0,
                "mem_mb": round((p.info["memory_info"].rss if p.info["memory_info"] else 0) / 1_048_576, 1),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    key = "cpu" if by in ("cpu", "processor") else "mem_pct"
    procs.sort(key=lambda x: x[key], reverse=True)
    return procs[:n]


# ── Action handler ────────────────────────────────────────────────────────────

def process_manager_action(parameters: dict, **kwargs) -> str:
    psutil = _get_psutil()
    if not psutil:
        return "psutil is not installed. Run: pip install psutil"

    action = str(parameters.get("action", "list_heavy")).lower().strip()

    # ── list heavy processes ──────────────────────────────────────────────────
    if action in ("list_heavy", "top", "what_is_heavy", "cpu_hogs", "ram_hogs"):
        by = "cpu" if "ram" not in action else "mem_pct"
        sort_by = str(parameters.get("sort_by", by)).lower()
        procs = _top_procs(by=sort_by, n=10)
        if not procs:
            return "No process information available."
        label = "CPU" if sort_by in ("cpu", "processor") else "RAM"
        lines = [f"Top processes by {label}:"]
        for p in procs:
            lines.append(
                f"  [{p['pid']}] {p['name']} — CPU {p['cpu']}%  RAM {p['mem_mb']} MB ({p['mem_pct']:.1f}%)"
            )
        return "\n".join(lines)

    # ── find a process ────────────────────────────────────────────────────────
    if action in ("find", "search", "is_running"):
        name = str(parameters.get("name", "")).strip()
        if not name:
            return "Provide a 'name' to search for."
        matches = _find_procs_by_name(name)
        if not matches:
            return f"No process matching '{name}' is currently running."
        lines = [f"Found {len(matches)} process(es) matching '{name}':"]
        for p in matches[:10]:
            try:
                lines.append(f"  [{p.pid}] {p.name()} — CPU {p.cpu_percent(interval=0.1):.1f}%")
            except Exception:
                lines.append(f"  [{p.pid}] {p.name()}")
        return "\n".join(lines)

    # ── kill a process ────────────────────────────────────────────────────────
    if action in ("kill", "terminate", "end", "close_process"):
        name = str(parameters.get("name", "")).strip()
        pid  = parameters.get("pid")

        if pid:
            try:
                p = psutil.Process(int(pid))
                proc_name = p.name()
                p.terminate()
                return f"Terminated process '{proc_name}' (PID {pid})."
            except psutil.NoSuchProcess:
                return f"No process with PID {pid} found."
            except psutil.AccessDenied:
                return f"Access denied — cannot terminate PID {pid}."

        if not name:
            return "Provide a 'name' or 'pid' to kill."

        matches = _find_procs_by_name(name)
        if not matches:
            return f"No process matching '{name}' found."

        killed, denied = [], []
        for p in matches:
            try:
                p_name = p.name()
                p.terminate()
                killed.append(f"{p_name} (PID {p.pid})")
            except psutil.AccessDenied:
                denied.append(str(p.pid))
            except psutil.NoSuchProcess:
                pass

        parts = []
        if killed:
            parts.append(f"Terminated: {', '.join(killed)}.")
        if denied:
            parts.append(f"Access denied for PID(s): {', '.join(denied)} — try running Alfred as administrator.")
        return " ".join(parts) or "Nothing was terminated."

    # ── restart a process ─────────────────────────────────────────────────────
    if action in ("restart",):
        name = str(parameters.get("name", "")).strip()
        if not name:
            return "Provide a 'name' to restart."
        matches = _find_procs_by_name(name)
        if not matches:
            return f"No process matching '{name}' found to restart."
        try:
            exe = matches[0].exe()
            matches[0].terminate()
            import subprocess
            subprocess.Popen([exe])
            return f"Restarted '{name}'."
        except Exception as e:
            return f"Could not restart '{name}': {e}"

    # ── suspend / resume ──────────────────────────────────────────────────────
    if action in ("suspend", "pause_process"):
        name = str(parameters.get("name", "")).strip()
        pid  = parameters.get("pid")
        target = psutil.Process(int(pid)) if pid else (_find_procs_by_name(name) or [None])[0]
        if not target:
            return f"Process '{name or pid}' not found."
        try:
            target.suspend()
            return f"Suspended '{target.name()}' (PID {target.pid})."
        except psutil.AccessDenied:
            return f"Access denied — cannot suspend PID {target.pid}."

    if action in ("resume_process", "unpause_process"):
        name = str(parameters.get("name", "")).strip()
        pid  = parameters.get("pid")
        target = psutil.Process(int(pid)) if pid else (_find_procs_by_name(name) or [None])[0]
        if not target:
            return f"Process '{name or pid}' not found."
        try:
            target.resume()
            return f"Resumed '{target.name()}' (PID {target.pid})."
        except psutil.AccessDenied:
            return f"Access denied — cannot resume PID {target.pid}."

    return (
        f"Unknown process_manager action: '{action}'. "
        "Use: list_heavy | find | kill | restart | suspend | resume_process."
    )


# ── Tool declaration ──────────────────────────────────────────────────────────
TOOL = {
    "name": "process_manager",
    "description": (
        "Manage running processes by voice. List top CPU/RAM consumers, "
        "find whether an app is running, kill or restart a process by name or PID, "
        "or suspend/resume a process."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "list_heavy | find | kill | restart | suspend | resume_process"
                ),
            },
            "name": {
                "type": "STRING",
                "description": "Process name fragment (e.g. 'chrome', 'discord').",
            },
            "pid": {
                "type": "INTEGER",
                "description": "Process ID — use instead of name for precision.",
            },
            "sort_by": {
                "type": "STRING",
                "description": "cpu | ram — sort order for list_heavy (default: cpu).",
            },
        },
        "required": ["action"],
    },
    "handler": process_manager_action,
}
