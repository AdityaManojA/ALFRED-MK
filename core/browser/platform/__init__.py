"""
core/browser/platform/__init__.py — Factory for platform-specific browser drivers.
"""
from __future__ import annotations

import sys
from core.browser.platform.base import BaseBrowserPlatformDriver


def get_platform_browser_driver() -> BaseBrowserPlatformDriver:
    """Return the driver appropriate for the host operating system."""
    if sys.platform == "win32":
        from core.browser.platform.win import WinBrowserDriver
        return WinBrowserDriver()
    elif sys.platform == "darwin":
        from core.browser.platform.mac import MacBrowserDriver
        return MacBrowserDriver()
    else:
        from core.browser.platform.linux import LinuxBrowserDriver
        return LinuxBrowserDriver()
