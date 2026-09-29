"""Local clipboard-and-keystroke automation with an explicit focus gate."""

from __future__ import annotations

import platform
import subprocess
import time
from dataclasses import dataclass

POST_PASTE_DELAY_MS = 200


@dataclass(frozen=True)
class AutomationResult:
    ok: bool
    detail: str


def _focus_windows(keyword: str) -> bool:
    try:
        import pygetwindow as gw
        matches = [item for item in gw.getAllWindows() if keyword.casefold() in (item.title or "").casefold()]
        if not matches:
            return False
        window = matches[0]
        if window.isMinimized:
            window.restore()
        window.activate()
        return True
    except Exception:
        return False


def _focus_macos(keyword: str) -> bool:
    script = 'tell application "System Events" to set frontmost of first process whose name contains ' + repr(keyword) + ' to true'
    try:
        return subprocess.run(["osascript", "-e", script], capture_output=True, timeout=3, check=False).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _focus_linux(keyword: str) -> bool:
    try:
        found = subprocess.run(["xdotool", "search", "--name", keyword], capture_output=True, text=True, timeout=3, check=False)
        window_id = next((line.strip() for line in found.stdout.splitlines() if line.strip()), "")
        return bool(window_id) and subprocess.run(["xdotool", "windowactivate", "--sync", window_id], timeout=3, check=False).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def focus_target(keyword: str) -> bool:
    """Focus a window by the user-supplied app or tab-title keyword."""
    keyword = str(keyword or "").strip()
    if not keyword:
        return False
    if platform.system() == "Windows":
        return _focus_windows(keyword)
    if platform.system() == "Darwin":
        return _focus_macos(keyword)
    return _focus_linux(keyword)


def run_macro(payload: dict) -> AutomationResult:
    """Focus first, then paste local clipboard text, wait 200 ms, and Enter."""
    target = payload.get("target_tab") or payload.get("target_app")
    text = str(payload.get("paste_text") or "")
    if not target:
        return AutomationResult(False, "A target application or tab keyword is required.")
    if not text:
        return AutomationResult(False, "Macro has no text to paste.")
    if not focus_target(str(target)):
        return AutomationResult(False, f"Could not focus target '{target}'.")
    try:
        import pyautogui
        import pyperclip
        pyperclip.copy(text)
        pyautogui.hotkey("command" if platform.system() == "Darwin" else "ctrl", "v")
        time.sleep(POST_PASTE_DELAY_MS / 1000)
        if payload.get("hit_run", True):
            pyautogui.press("enter")
    except Exception as exc:
        return AutomationResult(False, f"Input injection failed: {exc}")
    return AutomationResult(True, f"Pasted into {target}.")
