"""
core/browser/controller.py — Cross-platform browser tab and window controller.
"""
from __future__ import annotations

import logging
from typing import Optional

from core.browser.platform import get_platform_browser_driver
from core.browser.platform.base import BaseBrowserPlatformDriver

# ── Named Constants ──────────────────────────────────────────────────────────
HOTKEY_CLOSE_WIN = ('ctrl', 'w')
HOTKEY_CLOSE_MAC = ('command', 'w')
CONTROLLER_TIMEOUT_S: float = 3.0
MSG_TAB_CLOSED: str = "Tab closed, sir."
MSG_TAB_CLOSE_FAILED: str = "Could not close active tab, sir."
MSG_NO_BROWSER_FRONTMOST: str = "No active browser detected in the foreground, sir."
MSG_NEW_TAB_OPENED: str = "New tab opened, sir."
MSG_TAB_SWITCHED: str = "Tab switched, sir."
MSG_TAB_REOPENED: str = "Tab reopened, sir."
MSG_WINDOW_CLOSED: str = "Browser window closed, sir."

_LOGGER = logging.getLogger(__name__)


class BrowserController:
    """Standardised cross-browser controller across Chrome, Brave, Edge, Firefox, Arc, Safari."""

    def __init__(self, driver: Optional[BaseBrowserPlatformDriver] = None) -> None:
        self._driver = driver or get_platform_browser_driver()

    @property
    def driver(self) -> BaseBrowserPlatformDriver:
        return self._driver

    def get_frontmost_browser(self) -> Optional[str]:
        """Detect and return the active browser name (e.g. 'Chrome', 'Edge', 'Brave')."""
        return self._driver.get_frontmost_browser()

    def is_browser_frontmost(self) -> bool:
        """Return True if a known browser process is currently in the foreground."""
        return self.get_frontmost_browser() is not None

    def close_active_tab(self) -> str:
        """Close the active browser tab without opening blank pages or windows."""
        browser = self.get_frontmost_browser()
        ok = self._driver.close_active_tab()
        if not ok:
            # Fallback: keyboard automation with window-focus restoration
            try:
                from core.browser.commands import close_tab as cmd_close_tab
                ok = cmd_close_tab()
            except Exception as exc:
                _LOGGER.debug("[BrowserController] Keyboard close fallback failed: %s", exc)

        if ok:
            _LOGGER.info("[BrowserController] Active tab closed successfully in %s.", browser or "frontmost window")
            try:
                from core.registry import get
                player = get("main_player") or get("hud_controller") or get("ui")
                if player and hasattr(player, "show_toast"):
                    player.show_toast("[Browser] Tab closed")
            except Exception:
                pass
            return MSG_TAB_CLOSED
        
        # If platform driver and keyboard fallback returned False because frontmost was not browser, report cleanly
        if not browser:
            return MSG_NO_BROWSER_FRONTMOST
        return MSG_TAB_CLOSE_FAILED

    def new_tab(self, url: Optional[str] = None) -> str:
        """Open a new tab in the active browser or default browser."""
        ok = self._driver.new_tab(url=url)
        if ok:
            return MSG_NEW_TAB_OPENED
        return "Could not open new tab, sir."

    def switch_tab(self, direction: str = "next") -> str:
        """Switch to next or previous tab."""
        ok = self._driver.switch_tab(direction=direction)
        if ok:
            return MSG_TAB_SWITCHED
        return "Could not switch tab, sir."

    def reopen_closed_tab(self) -> str:
        """Reopen recently closed tab."""
        ok = self._driver.reopen_closed_tab()
        if ok:
            return MSG_TAB_REOPENED
        return "Could not reopen tab, sir."

    def close_window(self) -> str:
        """Close active browser window."""
        ok = self._driver.close_window()
        if ok:
            return MSG_WINDOW_CLOSED
        return "Could not close browser window, sir."


_GLOBAL_CONTROLLER: Optional[BrowserController] = None


def get_browser_controller() -> BrowserController:
    """Return the global BrowserController instance."""
    global _GLOBAL_CONTROLLER
    if _GLOBAL_CONTROLLER is None:
        _GLOBAL_CONTROLLER = BrowserController()
    return _GLOBAL_CONTROLLER


def close_active_tab() -> str:
    """Module-level shortcut to close the active tab."""
    return get_browser_controller().close_active_tab()


def new_tab(url: Optional[str] = None) -> str:
    """Module-level shortcut to open a new tab."""
    return get_browser_controller().new_tab(url=url)


def switch_tab(direction: str = "next") -> str:
    """Module-level shortcut to switch tabs."""
    return get_browser_controller().switch_tab(direction=direction)


def reopen_closed_tab() -> str:
    """Module-level shortcut to reopen closed tab."""
    return get_browser_controller().reopen_closed_tab()


def close_window() -> str:
    """Module-level shortcut to close browser window."""
    return get_browser_controller().close_window()
