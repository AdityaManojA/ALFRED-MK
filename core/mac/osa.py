"""AppleScript / JXA runners and the small helpers every mac tool needs.

Scripts go to osascript on stdin rather than via -e so quoting never has to
survive a shell. Errors are translated into sentences the assistant can say.
"""
from __future__ import annotations

import json
import subprocess

_PRIVACY_HINTS = {
    "-1743": "macOS blocked ALFRED from controlling {app}. Allow it in System Settings → "
             "Privacy & Security → Automation → ALFRED.",
    "-1719": "ALFRED needs Accessibility access for that. Allow it in System Settings → "
             "Privacy & Security → Accessibility → ALFRED.",
    "-25211": "ALFRED needs Accessibility access for that. Allow it in System Settings → "
              "Privacy & Security → Accessibility → ALFRED.",
    "-600": "{app} isn't running.",
}


class OSAError(RuntimeError):
    pass


def q(text) -> str:
    """AppleScript string literal."""
    s = str(text if text is not None else "")
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _explain(err: str, app: str) -> str:
    for code, msg in _PRIVACY_HINTS.items():
        if code in err:
            return msg.format(app=app or "that app")
    return err.strip().splitlines()[-1] if err.strip() else "AppleScript failed"


def applescript(script: str, timeout: float = 15.0, app: str = "") -> str:
    """Run AppleScript; return stdout. Raises OSAError with a speakable message."""
    try:
        p = subprocess.run(["osascript", "-"], input=script, capture_output=True,
                           text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise OSAError(f"{app or 'The app'} did not answer in time "
                       "(it may be waiting on a permission prompt).")
    if p.returncode != 0:
        raise OSAError(_explain(p.stderr, app))
    return p.stdout.strip()


def jxa(script: str, timeout: float = 15.0, app: str = ""):
    """Run JavaScript for Automation; the script's last value should be JSON.stringify(...)."""
    try:
        p = subprocess.run(["osascript", "-l", "JavaScript", "-"], input=script,
                           capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise OSAError(f"{app or 'The app'} did not answer in time "
                       "(it may be waiting on a permission prompt).")
    if p.returncode != 0:
        raise OSAError(_explain(p.stderr, app))
    out = p.stdout.strip()
    try:
        return json.loads(out) if out else None
    except ValueError:
        return out


def running_apps() -> list:
    """NSRunningApplication objects for regular (Dock) apps."""
    from AppKit import NSWorkspace
    return [a for a in NSWorkspace.sharedWorkspace().runningApplications()
            if a.activationPolicy() == 0]


def is_running(bundle_id: str) -> bool:
    from AppKit import NSRunningApplication
    return len(NSRunningApplication.runningApplicationsWithBundleIdentifier_(bundle_id)) > 0


def notify(title: str, text: str) -> None:
    try:
        applescript(f"display notification {q(text)} with title {q(title)}", timeout=5)
    except OSAError:
        pass


def run(cmd: list[str], timeout: float = 15.0) -> str:
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return (p.stdout or p.stderr).strip()
