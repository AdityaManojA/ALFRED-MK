"""
core/browser/__init__.py — Browser Suite package export.
"""
from __future__ import annotations

from core.browser.commands import (
    HOTKEY_CLOSE_WIN,
    HOTKEY_CLOSE_MAC,
    close_tab as close_tab_hotkey,
)
from core.browser.controller import (
    BrowserController,
    get_browser_controller,
    close_active_tab,
    new_tab,
    switch_tab,
    reopen_closed_tab,
    close_window,
)

__all__ = [
    "BrowserController",
    "get_browser_controller",
    "close_active_tab",
    "close_tab_hotkey",
    "new_tab",
    "switch_tab",
    "reopen_closed_tab",
    "close_window",
    "HOTKEY_CLOSE_WIN",
    "HOTKEY_CLOSE_MAC",
]
