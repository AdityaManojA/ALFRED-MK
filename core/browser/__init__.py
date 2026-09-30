"""
core/browser/__init__.py — Browser Suite package export.
"""
from __future__ import annotations

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
    "new_tab",
    "switch_tab",
    "reopen_closed_tab",
    "close_window",
]
