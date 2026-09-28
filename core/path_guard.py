"""
core/path_guard.py — Centralized Path Security and Drive Access Control.

Enforces:
1. Heavenly Restriction (Source Code Lockdown):
   - D:\\Projects\\Personal-Assistant (and any subpaths/variations) is strictly and irrevocably forbidden.
   - Refusal response: "Due to the heavenly restriction placed upon my creator, I cannot."
2. C: Drive Restriction:
   - Access to C: drive is strictly restricted to Desktop and Documents only.
   - All other locations on C: (e.g. C:\\Windows, C:\\Program Files, Downloads, AppData, etc.) are forbidden.
   - Refusal response: "Access denied: Access to C: drive is restricted to Desktop and Documents only."
3. D: Drive and E: Drive:
   - D: drive and E: drive are safe and permitted for file operations.
   - (D:\\Projects\\Personal-Assistant remains strictly locked by the Heavenly Restriction).
"""

from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Any, Union

_OS = platform.system()

HEAVENLY_RESPONSE = "Due to the heavenly restriction placed upon my creator, I cannot."
HEAVENLY_TARGETS = [
    r"d:\projects\personal-assistant",
    r"projects\personal-assistant",
    r"personal-assistant",
    r"d:\projects\alfred-mark-ii",
    r"projects\alfred-mark-ii",
    r"alfred-mark-ii",
]



def is_heavenly_restricted(val: Any) -> bool:
    """Check if any argument references the restricted Personal-Assistant directory."""
    if val is None:
        return False
    if isinstance(val, dict):
        return any(is_heavenly_restricted(v) for v in val.values())
    if isinstance(val, (list, tuple, set)):
        return any(is_heavenly_restricted(v) for v in val)

    s = str(val).strip().lower().replace("/", "\\")
    for t in HEAVENLY_TARGETS:
        if t in s:
            return True

    # Only test filesystem path resolution if val looks like a file/directory path
    if any(c in s for c in ("\\", "/", ":")) or s.startswith("."):
        try:
            p = Path(str(val)).resolve()
            for res_target in (Path(r"D:\Projects\Personal-Assistant"), Path(r"D:\Projects\Alfred-Mark-II")):
                restricted = res_target.resolve()
                if p == restricted or restricted in p.parents:
                    return True
        except Exception:
            pass

    return False


def get_allowed_c_roots() -> list[Path]:
    """Return list of permitted roots on C: drive (Desktop and Documents)."""
    home = Path.home()
    candidates = [
        home / "Desktop",
        home / "Documents",
    ]

    # USERPROFILE environment variable
    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        up = Path(userprofile)
        candidates.extend([
            up / "Desktop",
            up / "Documents",
        ])

    # OneDrive synced folders if present
    onedrive = os.environ.get("OneDrive")
    if onedrive:
        od = Path(onedrive)
        candidates.extend([
            od / "Desktop",
            od / "Documents",
        ])
    candidates.extend([
        home / "OneDrive" / "Desktop",
        home / "OneDrive" / "Documents",
    ])

    unique_roots = []
    seen = set()
    for c in candidates:
        try:
            res = c.resolve()
            s = str(res).lower()
            if s not in seen:
                seen.add(s)
                unique_roots.append(res)
        except Exception:
            pass

    return unique_roots


def check_path_access(raw_path: Union[str, Path, None]) -> tuple[bool, str]:
    """
    Validate whether a given path is allowed to be accessed.
    
    Returns:
        (True, "") if allowed
        (False, error_message) if access is denied
    """
    if raw_path is None:
        return True, ""

    # 1. Check Heavenly Restriction first
    if is_heavenly_restricted(raw_path):
        return False, HEAVENLY_RESPONSE

    s_raw = str(raw_path).strip().strip('"').strip("'")
    if not s_raw:
        return True, ""

    # Shortcuts handling
    lower = s_raw.lower().replace("/", "\\")
    if lower in ("desktop", "documents"):
        return True, ""
    if lower.startswith("desktop\\") or lower.startswith("documents\\"):
        return True, ""

    try:
        p = Path(s_raw).expanduser().resolve()
    except Exception as e:
        return False, f"Invalid path '{s_raw}': {e}"

    # Verify resolved path against Heavenly Restriction
    for res_target in (Path(r"D:\Projects\Personal-Assistant"), Path(r"D:\Projects\Alfred-Mark-II")):
        try:
            restricted = res_target.resolve()
            if p == restricted or restricted in p.parents:
                return False, HEAVENLY_RESPONSE
        except Exception:
            pass

    drive = p.drive.upper()
    if drive:
        if drive == "C:":
            allowed_c = get_allowed_c_roots()
            for root in allowed_c:
                try:
                    r_res = root.resolve()
                    if p == r_res or r_res in p.parents:
                        return True, ""
                except Exception:
                    continue
            return False, f"Access denied: Access to C: drive is restricted to Desktop and Documents only. ('{p}' is not allowed)"

        elif drive in ("D:", "E:"):
            # D: (safe except Personal-Assistant checked above) and E: are safe
            return True, ""

        else:
            return False, f"Access denied: Drive {drive} is not allowed. Only D: drive, E: drive, and C: drive (Desktop & Documents only) are permitted."

    # Non-Windows or path without drive letter
    if _OS != "Windows":
        home = Path.home().resolve()
        desktop = (home / "Desktop").resolve()
        documents = (home / "Documents").resolve()
        if p == desktop or desktop in p.parents or p == documents or documents in p.parents:
            return True, ""
        # Check /mnt/d or /mnt/e
        s_p = str(p).lower()
        if s_p.startswith("/mnt/d") or s_p.startswith("/mnt/e") or s_p.startswith("/d/") or s_p.startswith("/e/"):
            return True, ""

    return True, ""


def is_safe_path(target: Union[str, Path, None]) -> bool:
    """Convenience boolean helper for path safety."""
    ok, _ = check_path_access(target)
    return ok


PATH_PARAM_KEYS = {
    "path", "name", "destination", "file_path", "target", "folder",
    "directory", "dir", "file", "save_path", "src", "dst", "output_dir"
}


def check_action_params(action_name: str, parameters: dict) -> tuple[bool, str]:
    """
    Validate tool execution parameters before invocation.
    
    Returns:
        (True, "") if allowed
        (False, error_message) if rejected
    """
    if not parameters:
        return True, ""

    # Always check Heavenly Restriction across all parameters
    if is_heavenly_restricted(parameters):
        return False, HEAVENLY_RESPONSE

    # Special check for open_app: if an explicit path is provided
    if action_name == "open_app":
        app_name = str(parameters.get("app_name", "")).strip()
        if ":" in app_name or "\\" in app_name or "/" in app_name:
            ok, msg = check_path_access(app_name)
            if not ok:
                return False, msg
        return True, ""

    # Check path parameters
    for k, v in parameters.items():
        k_lower = k.lower()
        if k_lower in PATH_PARAM_KEYS and isinstance(v, (str, Path)):
            s_val = str(v).strip()
            if not s_val:
                continue
            # Skip single action verbs or simple file names without path separators
            if s_val.lower() in ("open", "list", "read", "write", "delete", "create", "move", "copy", "desktop", "documents"):
                continue
            if k_lower == "name" and "\\" not in s_val and "/" not in s_val and ":" not in s_val:
                continue
            ok, msg = check_path_access(s_val)
            if not ok:
                return False, msg

    return True, ""
