"""
core/browser/commands.py — Keyboard automation commands for browser tab control.
"""
from __future__ import annotations

import logging
import os
import platform
import time
from typing import Optional

try:
    import pyautogui
    _HAS_PYAUTOGUI = True
except ImportError:
    _HAS_PYAUTOGUI = False

# ── Named Constants ──────────────────────────────────────────────────────────
HOTKEY_CLOSE_WIN = ('ctrl', 'w')
HOTKEY_CLOSE_MAC = ('command', 'w')
FOCUS_SETTLE_DELAY_S: float = 0.08

logger = logging.getLogger("core.browser.commands")

KNOWN_BROWSER_PROCESSES = {
    "chrome.exe", "msedge.exe", "brave.exe", "firefox.exe",
    "opera.exe", "operagx.exe", "vivaldi.exe", "arc.exe",
    "google-chrome", "chromium", "chromium-browser", "firefox",
    "brave-browser", "microsoft-edge", "opera", "vivaldi"
}


def _ensure_browser_focus(sys_name: str) -> None:
    """
    If ALFRED HUD or the current assistant process is in the foreground,
    restore focus to the browser window or previous active window.
    """
    if sys_name == "Windows":
        try:
            import ctypes
            user32 = getattr(ctypes.windll, "user32", None)
            if not user32:
                return
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            current_pid = os.getpid()

            # If current foreground window belongs to ALFRED
            if pid.value == current_pid:
                browser_hwnd = [0]
                WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)

                def enum_proc(h, _):
                    if not user32.IsWindowVisible(h) or user32.IsIconic(h):
                        return True
                    p = ctypes.c_ulong()
                    user32.GetWindowThreadProcessId(h, ctypes.byref(p))
                    if p.value == current_pid:
                        return True
                    try:
                        import psutil
                        pname = psutil.Process(p.value).name().lower()
                        if pname in KNOWN_BROWSER_PROCESSES:
                            browser_hwnd[0] = h
                            return False  # Stop enumeration
                    except Exception:
                        pass
                    return True

                user32.EnumWindows(WNDENUMPROC(enum_proc), 0)
                if browser_hwnd[0]:
                    user32.SetForegroundWindow(browser_hwnd[0])
                    time.sleep(FOCUS_SETTLE_DELAY_S)
                elif _HAS_PYAUTOGUI:
                    pyautogui.hotkey('alt', 'tab')
                    time.sleep(FOCUS_SETTLE_DELAY_S)
        except Exception as exc:
            logger.debug(f"[BrowserCommands] Windows focus adjustment error: {exc}")
    elif sys_name == "Darwin":
        try:
            import subprocess
            script = '''
            tell application "System Events"
                set frontApp to first application process whose frontmost is true
                if name of frontApp contains "ALFRED" or name of frontApp contains "Python" then
                    key code 48 using {command down}
                end if
            end tell
            '''
            subprocess.run(["osascript", "-e", script], capture_output=True, timeout=1)
            time.sleep(FOCUS_SETTLE_DELAY_S)
        except Exception:
            pass
    elif sys_name == "Linux":
        if _HAS_PYAUTOGUI:
            try:
                import subprocess
                res = subprocess.run(["xdotool", "getactivewindow", "getwindowpid"], capture_output=True, text=True, timeout=1)
                if res.returncode == 0 and res.stdout.strip() == str(os.getpid()):
                    pyautogui.hotkey('alt', 'tab')
                    time.sleep(FOCUS_SETTLE_DELAY_S)
            except Exception:
                pass


def close_tab() -> bool:
    """
    Close the active browser tab using keyboard automation:
    - Determines frontmost window and ensures browser focus.
    - Sends Ctrl+W (Windows/Linux) or Cmd+W (macOS) via pyautogui.hotkey.
    - Never launches browser executables or blank pages.
    """
    sys_name = platform.system()
    _ensure_browser_focus(sys_name)

    if sys_name == "Darwin":
        hotkey = HOTKEY_CLOSE_MAC
    else:
        hotkey = HOTKEY_CLOSE_WIN

    if _HAS_PYAUTOGUI:
        try:
            pyautogui.hotkey(*hotkey)
            logger.info(f"[BrowserCommands] Sent hotkey {hotkey} to close tab.")
            return True
        except Exception as e:
            logger.warning(f"[BrowserCommands] Failed to send {hotkey} via pyautogui: {e}")

    # Fallback to platform driver key simulation if pyautogui failed
    try:
        from core.browser.platform import get_platform_browser_driver
        driver = get_platform_browser_driver()
        return driver.close_active_tab()
    except Exception as e:
        logger.warning(f"[BrowserCommands] Driver fallback failed: {e}")
        return False
