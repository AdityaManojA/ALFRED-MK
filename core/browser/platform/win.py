"""
core/browser/platform/win.py — Windows Win32 / UIA browser driver.
"""
from __future__ import annotations

import ctypes
import logging
import os
import time
from typing import Optional

from core.browser.platform.base import (
    BaseBrowserPlatformDriver,
    DEFAULT_KEY_SETTLE_MS,
    normalize_tab_query,
    tab_matches_query,
)

# ── Named Constants ──────────────────────────────────────────────────────────
VK_SHIFT: int = 0x10
VK_CONTROL: int = 0x11
VK_MENU: int = 0x12       # Alt
VK_TAB: int = 0x09
VK_W: int = 0x57
VK_T: int = 0x54
VK_F4: int = 0x73

KEYEVENTF_KEYUP: int = 0x0002
SW_RESTORE: int = 9
SW_SHOW: int = 5
UIA_CONTROL_TYPE_PROPERTY_ID: int = 30003
UIA_TAB_ITEM_CONTROL_TYPE_ID: int = 50019
UIA_SELECTION_ITEM_PATTERN_ID: int = 10010

KNOWN_WIN_BROWSERS: dict[str, str] = {
    "chrome.exe": "Chrome",
    "msedge.exe": "Edge",
    "brave.exe": "Brave",
    "firefox.exe": "Firefox",
    "opera.exe": "Opera",
    "operagx.exe": "Opera GX",
    "vivaldi.exe": "Vivaldi",
    "arc.exe": "Arc",
}

_LOGGER = logging.getLogger(__name__)


class WinBrowserDriver(BaseBrowserPlatformDriver):
    """Windows browser driver using targeted Win32 virtual keys and process inspection."""
    KNOWN_WIN_BROWSERS = KNOWN_WIN_BROWSERS

    def __init__(self) -> None:
        self._user32 = getattr(ctypes.windll, "user32", None)

    def _get_foreground_hwnd_and_proc(self) -> tuple[int, str]:
        if not self._user32:
            return 0, ""
        hwnd = self._user32.GetForegroundWindow()
        if not hwnd:
            return 0, ""
        pid = ctypes.c_ulong()
        self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return hwnd, ""
        try:
            import psutil
            name = psutil.Process(pid.value).name().lower()
            return hwnd, name
        except Exception:
            return hwnd, ""

    def get_frontmost_browser(self) -> Optional[str]:
        _, proc_name = self._get_foreground_hwnd_and_proc()
        if proc_name in KNOWN_WIN_BROWSERS:
            return KNOWN_WIN_BROWSERS[proc_name]
        return None

    def _send_keys(self, *vk_codes: int) -> bool:
        if not self._user32:
            return False
        try:
            # Key down in order
            for vk in vk_codes:
                self._user32.keybd_event(vk, 0, 0, 0)
            time.sleep(DEFAULT_KEY_SETTLE_MS / 1000.0)
            # Key up in reverse order
            for vk in reversed(vk_codes):
                self._user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
            return True
        except Exception as exc:
            _LOGGER.warning("[WinBrowserDriver] Key event failed: %s", exc)
            return False

    def _focus_window(self, hwnd: int) -> bool:
        """Bring window to foreground cleanly across Windows processes."""
        if not hwnd or not self._user32:
            return False
        try:
            if self._user32.IsIconic(hwnd):
                self._user32.ShowWindow(hwnd, SW_RESTORE)
            else:
                self._user32.ShowWindow(hwnd, SW_SHOW)

            kernel32 = getattr(ctypes.windll, "kernel32", None)
            fore_hwnd = self._user32.GetForegroundWindow()
            fore_thread = self._user32.GetWindowThreadProcessId(fore_hwnd, None)
            curr_thread = kernel32.GetCurrentThreadId() if kernel32 else 0

            if fore_thread and curr_thread and fore_thread != curr_thread:
                self._user32.AttachThreadInput(curr_thread, fore_thread, True)
                self._user32.BringWindowToTop(hwnd)
                self._user32.SetForegroundWindow(hwnd)
                self._user32.AttachThreadInput(curr_thread, fore_thread, False)
            else:
                self._user32.BringWindowToTop(hwnd)
                self._user32.SetForegroundWindow(hwnd)
            return True
        except Exception as exc:
            _LOGGER.debug("[WinBrowserDriver] Failed to focus window %s: %s", hwnd, exc)
            return False

    def _get_browser_windows(
        self, target_browser: Optional[str] = None
    ) -> list[tuple[int, str, str]]:
        """Return list of (hwnd, process_name, title) for visible matching browser windows."""
        if not self._user32:
            return []

        target_norm = target_browser.lower().strip() if target_browser else None
        hwnds: list[tuple[int, int, str]] = []

        def enum_proc(hwnd: int, lParam: int) -> int:
            if self._user32.IsWindowVisible(hwnd):
                length = self._user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    self._user32.GetWindowTextW(hwnd, buff, length + 1)
                    pid = ctypes.c_ulong()
                    self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    hwnds.append((hwnd, pid.value, buff.value))
            return 1

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_int)
        cb = WNDENUMPROC(enum_proc)
        self._user32.EnumWindows(cb, 0)

        # Fallback to OpenInputDesktop if EnumWindows saw no windows
        if not hwnds:
            desk = self._user32.OpenInputDesktop(0, False, 0x01FF)
            if desk:
                try:
                    self._user32.EnumDesktopWindows(desk, cb, 0)
                finally:
                    self._user32.CloseDesktop(desk)

        result: list[tuple[int, str, str]] = []
        try:
            import psutil

            for hwnd, pid, title in hwnds:
                try:
                    pname = psutil.Process(pid).name().lower()
                    if pname not in KNOWN_WIN_BROWSERS and not any(
                        k in pname
                        for k in (
                            "chrome",
                            "brave",
                            "edge",
                            "firefox",
                            "opera",
                            "vivaldi",
                        )
                    ):
                        continue
                    canonical_name = KNOWN_WIN_BROWSERS.get(pname, pname)
                    if target_norm:
                        if (
                            target_norm not in pname
                            and target_norm not in canonical_name.lower()
                        ):
                            continue
                    result.append((hwnd, pname, title))
                except Exception:
                    continue
        except Exception as exc:
            _LOGGER.debug(
                "[WinBrowserDriver] Error enumerating browser processes: %s", exc
            )

        return result

    def close_active_tab(self) -> bool:
        """Send Ctrl+W to frontmost browser."""
        browser = self.get_frontmost_browser()
        if not browser:
            _LOGGER.debug("[WinBrowserDriver] Frontmost window is not a recognized browser.")
            return False
        return self._send_keys(VK_CONTROL, VK_W)

    def close_tab_matching(self, query: str, browser: Optional[str] = None) -> bool:
        """Find and close a tab matching query/URL in specified or frontmost browser.

        Never closes an arbitrary active tab if no matching tab is found.
        """
        candidates = normalize_tab_query(query)
        if not candidates:
            return False

        browser_wins = self._get_browser_windows(target_browser=browser)
        if not browser_wins:
            _LOGGER.debug(
                "[WinBrowserDriver] No matching browser windows found for '%s'.",
                browser or "any",
            )
            return False

        # Phase 1: Fast-path — check if target tab is already active in a window title
        for hwnd, proc_name, title in browser_wins:
            if tab_matches_query(title, candidates):
                _LOGGER.info(
                    "[WinBrowserDriver] Target tab matched active window title '%s' (hwnd=%s).",
                    title,
                    hwnd,
                )
                self._focus_window(hwnd)
                time.sleep(DEFAULT_KEY_SETTLE_MS / 1000.0)
                return self._send_keys(VK_CONTROL, VK_W)

        # Phase 2: Native COM UIAutomation background tab scan
        try:
            import comtypes.client
            from comtypes.gen.UIAutomationClient import (
                CUIAutomation,
                IUIAutomation,
                TreeScope_Descendants,
                IUIAutomationSelectionItemPattern,
            )

            uia = comtypes.client.CreateObject(CUIAutomation, interface=IUIAutomation)
            cond = uia.CreatePropertyCondition(
                UIA_CONTROL_TYPE_PROPERTY_ID, UIA_TAB_ITEM_CONTROL_TYPE_ID
            )

            for hwnd, proc_name, _ in browser_wins:
                try:
                    root = uia.ElementFromHandle(hwnd)
                    elements = root.FindAll(TreeScope_Descendants, cond)
                    if not elements:
                        continue
                    for i in range(elements.Length):
                        el = elements.GetElement(i)
                        name = getattr(el, "CurrentName", "") or ""
                        if tab_matches_query(name, candidates):
                            _LOGGER.info(
                                "[WinBrowserDriver] Found background tab '%s' via UIA in %s (hwnd=%s).",
                                name,
                                proc_name,
                                hwnd,
                            )
                            self._focus_window(hwnd)
                            pattern_unk = el.GetCurrentPattern(
                                UIA_SELECTION_ITEM_PATTERN_ID
                            )
                            if pattern_unk:
                                pattern = pattern_unk.QueryInterface(
                                    IUIAutomationSelectionItemPattern
                                )
                                pattern.Select()
                                time.sleep(0.08)
                            return self._send_keys(VK_CONTROL, VK_W)
                except Exception as el_exc:
                    _LOGGER.debug(
                        "[WinBrowserDriver] UIA search on hwnd %s failed: %s",
                        hwnd,
                        el_exc,
                    )
                    continue
        except Exception as exc:
            _LOGGER.debug("[WinBrowserDriver] COM UIA tab search unavailable: %s", exc)

        _LOGGER.debug(
            "[WinBrowserDriver] No tab matching query candidates %s found.", candidates
        )
        return False

    def new_tab(self, url: Optional[str] = None) -> bool:
        """Send Ctrl+T to frontmost browser, or launch URL natively."""
        if url:
            try:
                os.startfile(url)
                return True
            except Exception as exc:
                _LOGGER.warning("[WinBrowserDriver] Failed to open URL %s: %s", url, exc)
                return False
        browser = self.get_frontmost_browser()
        if not browser:
            _LOGGER.debug("[WinBrowserDriver] Frontmost window is not a recognized browser.")
            return False
        return self._send_keys(VK_CONTROL, VK_T)

    def switch_tab(self, direction: str = "next") -> bool:
        """Send Ctrl+Tab (next) or Ctrl+Shift+Tab (prev)."""
        browser = self.get_frontmost_browser()
        if not browser:
            return False
        if direction.lower() in ("prev", "previous", "back", "left"):
            return self._send_keys(VK_CONTROL, VK_SHIFT, VK_TAB)
        return self._send_keys(VK_CONTROL, VK_TAB)

    def reopen_closed_tab(self) -> bool:
        """Send Ctrl+Shift+T."""
        browser = self.get_frontmost_browser()
        if not browser:
            return False
        return self._send_keys(VK_CONTROL, VK_SHIFT, VK_T)

    def close_window(self) -> bool:
        """Send Alt+F4."""
        browser = self.get_frontmost_browser()
        if not browser:
            return False
        return self._send_keys(VK_MENU, VK_F4)
