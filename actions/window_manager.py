# window_manager.py
"""
Voice-driven window management for Windows.
Snap, resize, fullscreen, tile, minimise, restore windows by name or the
currently focused window — without touching the mouse.
"""
from __future__ import annotations

import sys
from typing import Optional

# ── Win32 constants ───────────────────────────────────────────────────────────
SW_MAXIMIZE    = 3
SW_MINIMIZE    = 6
SW_RESTORE     = 9
SWP_NOZORDER   = 0x0004
SWP_SHOWWINDOW = 0x0040

user32 = None
if sys.platform == "win32":
    try:
        import ctypes
        import ctypes.wintypes
        user32 = ctypes.windll.user32
    except Exception:
        user32 = None


def _get_user32():
    if sys.platform != "win32":
        return None
    global user32
    if user32 is None:
        try:
            import ctypes
            import ctypes.wintypes
            user32 = ctypes.windll.user32
        except Exception:
            user32 = None
    return user32


def _get_screen() -> tuple[int, int]:
    """Return (width, height) of the primary monitor."""
    u32 = _get_user32()
    if u32 is None:
        return 1920, 1080
    return u32.GetSystemMetrics(0), u32.GetSystemMetrics(1)


def _focused_hwnd() -> Optional[int]:
    u32 = _get_user32()
    if u32 is None:
        return None
    hwnd = u32.GetForegroundWindow()
    return hwnd if hwnd else None


def _find_hwnd_by_title(title_fragment: str) -> Optional[int]:
    """Find the first visible window whose title contains title_fragment (case-insensitive)."""
    u32 = _get_user32()
    if u32 is None:
        return None
    import ctypes
    import ctypes.wintypes

    fragment = title_fragment.lower()
    found = []

    def _cb(hwnd, _):
        if u32.IsWindowVisible(hwnd):
            length = u32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                u32.GetWindowTextW(hwnd, buf, length + 1)
                if fragment in buf.value.lower():
                    found.append(hwnd)
        return True

    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    u32.EnumWindows(EnumWindowsProc(_cb), 0)
    return found[0] if found else None


def _get_title(hwnd: int) -> str:
    u32 = _get_user32()
    if u32 is None:
        return ""
    import ctypes
    length = u32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    u32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def _move_resize(hwnd: int, x: Optional[int], y: Optional[int], w: int, h: int) -> None:
    u32 = _get_user32()
    if u32 is None:
        return
    # Restore first in case it is maximised (SetWindowPos won't move a maximised window)
    u32.ShowWindow(hwnd, SW_RESTORE)
    target_x = x if x is not None else 0
    target_y = y if y is not None else 0
    flags = SWP_NOZORDER | SWP_SHOWWINDOW
    u32.SetWindowPos(hwnd, None, target_x, target_y, w, h, flags)


def _resolve_hwnd(parameters: dict) -> tuple[Optional[int], str]:
    """Return (hwnd, title) for the window named in parameters, or the focused one."""
    target = parameters.get("window", "").strip()
    if target:
        hwnd = _find_hwnd_by_title(target)
        if not hwnd:
            return None, target
        return hwnd, _get_title(hwnd)
    hwnd = _focused_hwnd()
    if not hwnd:
        return None, "(none)"
    return hwnd, _get_title(hwnd)


def _list_windows() -> list[str]:
    u32 = _get_user32()
    if u32 is None:
        return []
    import ctypes
    import ctypes.wintypes
    titles = []

    def _cb(hwnd, _):
        if u32.IsWindowVisible(hwnd):
            length = u32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                u32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value.strip()
                if title:
                    titles.append(title)
        return True

    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    u32.EnumWindows(EnumWindowsProc(_cb), 0)
    return titles


# ── Action handler ────────────────────────────────────────────────────────────

def window_manager_action(parameters: dict, **kwargs) -> str:
    if sys.platform != "win32":
        return "Window management is only supported on Windows."

    u32 = _get_user32()
    if u32 is None:
        return "Window management backend unavailable on this platform."

    action = str(parameters.get("action", "")).lower().strip()

    if action == "list":
        titles = _list_windows()
        if not titles:
            return "No visible windows found."
        return "Open windows:\n" + "\n".join(f"  - {t}" for t in sorted(set(titles))[:30])

    hwnd, title = _resolve_hwnd(parameters)
    if not hwnd:
        target = parameters.get("window", "the focused window")
        return f"Could not find a window matching '{target}'."

    sw, sh = _get_screen()
    half_w, half_h = sw // 2, sh // 2

    if action in ("snap_left", "left"):
        _move_resize(hwnd, 0, 0, half_w, sh)
        return f"Snapped '{title}' to the left half."

    if action in ("snap_right", "right"):
        _move_resize(hwnd, half_w, 0, half_w, sh)
        return f"Snapped '{title}' to the right half."

    if action in ("snap_top", "top"):
        _move_resize(hwnd, 0, 0, sw, half_h)
        return f"Snapped '{title}' to the top half."

    if action in ("snap_bottom", "bottom"):
        _move_resize(hwnd, 0, half_h, sw, half_h)
        return f"Snapped '{title}' to the bottom half."

    if action in ("snap_top_left", "top_left"):
        _move_resize(hwnd, 0, 0, half_w, half_h)
        return f"Snapped '{title}' to the top-left quarter."

    if action in ("snap_top_right", "top_right"):
        _move_resize(hwnd, half_w, 0, half_w, half_h)
        return f"Snapped '{title}' to the top-right quarter."

    if action in ("snap_bottom_left", "bottom_left"):
        _move_resize(hwnd, 0, half_h, half_w, half_h)
        return f"Snapped '{title}' to the bottom-left quarter."

    if action in ("snap_bottom_right", "bottom_right"):
        _move_resize(hwnd, half_w, half_h, half_w, half_h)
        return f"Snapped '{title}' to the bottom-right quarter."

    if action in ("fullscreen", "maximise", "maximize"):
        u32.ShowWindow(hwnd, SW_MAXIMIZE)
        return f"Maximised '{title}'."

    if action in ("minimise", "minimize"):
        u32.ShowWindow(hwnd, SW_MINIMIZE)
        return f"Minimised '{title}'."

    if action in ("restore", "unmaximise", "unmaximize"):
        u32.ShowWindow(hwnd, SW_RESTORE)
        return f"Restored '{title}'."

    if action == "tile":
        # Tile two specific windows side by side, or all visible windows in a grid
        _move_resize(hwnd, 0, 0, half_w, sh)
        # Try to find a second window
        second_title = parameters.get("second_window", "").strip()
        if second_title:
            hwnd2 = _find_hwnd_by_title(second_title)
            if hwnd2:
                _move_resize(hwnd2, half_w, 0, half_w, sh)
                return f"Tiled '{title}' and '{_get_title(hwnd2)}' side by side."
        return f"Snapped '{title}' to the left. Specify 'second_window' to tile two windows."

    if action == "centre":
        w = parameters.get("width", sw // 2)
        h = parameters.get("height", sh // 2)
        x = (sw - w) // 2
        y = (sh - h) // 2
        _move_resize(hwnd, x, y, w, h)
        return f"Centred '{title}' ({w}×{h})."

    if action == "resize":
        w = int(parameters.get("width", sw // 2))
        h = int(parameters.get("height", sh // 2))
        _move_resize(hwnd, None, None, w, h)
        return f"Resized '{title}' to {w}×{h}."

    return (
        f"Unknown window_manager action: '{action}'. "
        "Use: list | snap_left | snap_right | snap_top | snap_bottom | "
        "top_left | top_right | bottom_left | bottom_right | "
        "fullscreen | minimise | restore | tile | centre."
    )


# ── Tool declaration ──────────────────────────────────────────────────────────
TOOL = {
    "name": "window_manager",
    "description": (
        "Snap, resize, maximise, minimise, or tile open windows by voice. "
        "If no 'window' is given, acts on the currently focused window. "
        "Actions: list, snap_left, snap_right, snap_top, snap_bottom, "
        "top_left, top_right, bottom_left, bottom_right, fullscreen, "
        "minimise, restore, tile, centre."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "list | snap_left | snap_right | snap_top | snap_bottom | "
                    "top_left | top_right | bottom_left | bottom_right | "
                    "fullscreen | minimise | restore | tile | centre"
                ),
            },
            "window": {
                "type": "STRING",
                "description": (
                    "Partial window title to target. Omit to act on the focused window."
                ),
            },
            "second_window": {
                "type": "STRING",
                "description": "Second window title for tile action.",
            },
            "width": {
                "type": "INTEGER",
                "description": "Target width in pixels (for resize or centre).",
            },
            "height": {
                "type": "INTEGER",
                "description": "Target height in pixels (for resize or centre).",
            },
        },
        "required": ["action"],
    },
    "handler": window_manager_action,
}
