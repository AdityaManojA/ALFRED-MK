"""
tests/test_browser_controller.py
Unit tests for core.browser.controller, platform drivers, and intent routing.
"""
import unittest
from unittest.mock import MagicMock, patch

from core.browser.controller import (
    BrowserController,
    MSG_TAB_CLOSED,
    MSG_NEW_TAB_OPENED,
    MSG_TAB_SWITCHED,
    MSG_TAB_REOPENED,
    MSG_WINDOW_CLOSED,
)
from core.browser.platform.base import BaseBrowserPlatformDriver
from core.browser.platform.mac import MacBrowserDriver
from core.browser.platform.linux import LinuxBrowserDriver
from core.browser.platform.win import WinBrowserDriver
from actions.computer_settings import _detect_action
from actions.browser_control import browser_control


class MockDriver(BaseBrowserPlatformDriver):
    def __init__(self, frontmost="Chrome", succeed=True):
        self._frontmost = frontmost
        self._succeed = succeed
        self.calls = []

    def get_frontmost_browser(self):
        return self._frontmost

    def close_active_tab(self) -> bool:
        self.calls.append("close_active_tab")
        return self._succeed

    def close_tab_matching(self, query: str, browser=None) -> bool:
        self.calls.append(("close_tab_matching", query, browser))
        return self._succeed

    def new_tab(self, url=None) -> bool:
        self.calls.append(("new_tab", url))
        return self._succeed

    def switch_tab(self, direction="next") -> bool:
        self.calls.append(("switch_tab", direction))
        return self._succeed

    def reopen_closed_tab(self) -> bool:
        self.calls.append("reopen_closed_tab")
        return self._succeed

    def close_window(self) -> bool:
        self.calls.append("close_window")
        return self._succeed


class TestBrowserController(unittest.TestCase):
    def test_controller_delegates_to_driver(self):
        driver = MockDriver(frontmost="Brave", succeed=True)
        controller = BrowserController(driver=driver)

        self.assertEqual(controller.get_frontmost_browser(), "Brave")
        self.assertTrue(controller.is_browser_frontmost())

        # Test close_active_tab
        res = controller.close_active_tab()
        self.assertEqual(res, MSG_TAB_CLOSED)
        self.assertIn("close_active_tab", driver.calls)

        # Test new_tab
        res = controller.new_tab("https://netflix.com")
        self.assertEqual(res, MSG_NEW_TAB_OPENED)
        self.assertIn(("new_tab", "https://netflix.com"), driver.calls)

        # Test switch_tab
        res = controller.switch_tab("prev")
        self.assertEqual(res, MSG_TAB_SWITCHED)
        self.assertIn(("switch_tab", "prev"), driver.calls)

        # Test reopen_closed_tab
        res = controller.reopen_closed_tab()
        self.assertEqual(res, MSG_TAB_REOPENED)
        self.assertIn("reopen_closed_tab", driver.calls)

        # Test close_window
        res = controller.close_window()
        self.assertEqual(res, MSG_WINDOW_CLOSED)
        self.assertIn("close_window", driver.calls)

    def test_close_tab_matching_success(self):
        driver = MockDriver(frontmost="Brave", succeed=True)
        controller = BrowserController(driver=driver)
        res = controller.close_tab_matching("youtube.com", browser="brave")
        self.assertIn("Closed the youtube.com tab in Brave", res)
        self.assertIn(("close_tab_matching", "youtube.com", "brave"), driver.calls)

    def test_close_tab_matching_not_found(self):
        driver = MockDriver(frontmost="Brave", succeed=False)
        controller = BrowserController(driver=driver)
        res = controller.close_tab_matching("youtube.com", browser="brave")
        self.assertIn("No open tab matching 'youtube.com' was found in Brave", res)
        self.assertNotIn("close_active_tab", driver.calls)


class TestPlatformDrivers(unittest.TestCase):
    @patch("subprocess.run")
    def test_mac_driver_applescript_generation(self, mock_run):
        def mock_osascript(cmd, **kwargs):
            script = cmd[2] if len(cmd) > 2 else ""
            if "bundle identifier" in script:
                return MagicMock(returncode=0, stdout="com.google.Chrome\n")
            return MagicMock(returncode=0, stdout="")

        mock_run.side_effect = mock_osascript
        driver = MacBrowserDriver()

        # Frontmost check
        browser = driver.get_frontmost_browser()
        self.assertEqual(browser, "Google Chrome")

        # Close tab script targeting front window
        ok = driver.close_active_tab()
        self.assertTrue(ok)
        args, kwargs = mock_run.call_args
        script_executed = args[0][2]
        self.assertIn('tell application "Google Chrome"', script_executed)
        self.assertIn("close active tab of front window", script_executed)

    @patch("subprocess.run")
    def test_linux_driver_xdotool(self, mock_run):
        driver = LinuxBrowserDriver()
        # Mock active window and wm_class
        def mock_subprocess(cmd, **kwargs):
            if cmd[:2] == ["xdotool", "getactivewindow"]:
                return MagicMock(returncode=0, stdout="123456\n")
            if "WM_CLASS" in cmd:
                return MagicMock(returncode=0, stdout='"google-chrome", "Google-chrome"\n')
            return MagicMock(returncode=0, stdout="")

        mock_run.side_effect = mock_subprocess

        # Mock xdotool key
        ok = driver.close_active_tab()
        self.assertTrue(ok)

    def test_win_driver_constants(self):
        driver = WinBrowserDriver()
        self.assertIn("chrome.exe", driver.KNOWN_WIN_BROWSERS)
        self.assertIn("msedge.exe", driver.KNOWN_WIN_BROWSERS)
        self.assertIn("brave.exe", driver.KNOWN_WIN_BROWSERS)
        self.assertIn("firefox.exe", driver.KNOWN_WIN_BROWSERS)

    def test_query_normalization_and_matching(self):
        from core.browser.platform.base import normalize_tab_query, tab_matches_query

        candidates = normalize_tab_query("https://www.youtube.com/watch?v=123")
        self.assertIn("youtube", candidates)
        self.assertTrue(tab_matches_query("Rick Astley - YouTube - Brave", candidates))
        self.assertFalse(tab_matches_query("GitHub - Alfred-Mark-VIII", candidates))

        candidates_domain = normalize_tab_query("youtube.com")
        self.assertIn("youtube", candidates_domain)
        self.assertTrue(tab_matches_query("YouTube Music", candidates_domain))
        self.assertFalse(tab_matches_query("Tavily API Platform", candidates_domain))


class TestIntentRoutingAndAliases(unittest.TestCase):
    def test_close_tab_aliases(self):
        for phrase in [
            "close tab",
            "close this tab",
            "shut this tab",
            "kill tab",
            "close active tab",
        ]:
            match = _detect_action(phrase)
            self.assertEqual(
                match.get("action"),
                "close_tab",
                f"Phrase '{phrase}' failed to resolve to 'close_tab'",
            )

    def test_reopen_tab_aliases(self):
        for phrase in ["reopen tab", "undo close tab"]:
            match = _detect_action(phrase)
            self.assertIn(
                match.get("action"),
                ("reopen_tab", "reopen_closed_tab"),
                f"Phrase '{phrase}' failed to resolve to reopen tab action",
            )

    @patch("core.browser.controller.close_active_tab")
    def test_browser_control_action_close_tab_no_playwright_spawn(
        self, mock_close_tab
    ):
        mock_close_tab.return_value = MSG_TAB_CLOSED
        res = browser_control(parameters={"action": "close_tab"})
        self.assertEqual(res, MSG_TAB_CLOSED)
        mock_close_tab.assert_called_once()

    @patch("core.browser.controller.close_tab_matching")
    @patch("core.browser.controller.close_active_tab")
    def test_browser_control_action_close_tab_with_query_delegates_to_matching(
        self, mock_close_active, mock_close_matching
    ):
        mock_close_matching.return_value = (
            "Closed the youtube.com tab in Brave, sir."
        )
        res = browser_control(
            parameters={
                "action": "close_tab",
                "query": "youtube.com",
                "browser": "brave",
            }
        )
        self.assertEqual(res, "Closed the youtube.com tab in Brave, sir.")
        mock_close_matching.assert_called_once_with(
            query="youtube.com", browser="brave"
        )
        mock_close_active.assert_not_called()

    def test_intent_router_close_this_tab_fast_path(self):
        from core.intents.router import IntentRouter
        router = IntentRouter()
        match = router.route("close this tab")
        self.assertIsNotNone(match)
        self.assertEqual(match.intent_name, "close_tab")
        self.assertEqual(match.action_name, "browser_control")

    @patch("pyautogui.hotkey")
    @patch("platform.system", return_value="Windows")
    def test_browser_commands_close_tab_hotkey_windows(self, mock_sys, mock_hotkey):
        from core.browser.commands import close_tab, HOTKEY_CLOSE_WIN
        ok = close_tab()
        self.assertTrue(ok)
        mock_hotkey.assert_called_with(*HOTKEY_CLOSE_WIN)

    @patch("pyautogui.hotkey")
    @patch("platform.system", return_value="Darwin")
    def test_browser_commands_close_tab_hotkey_mac(self, mock_sys, mock_hotkey):
        from core.browser.commands import close_tab, HOTKEY_CLOSE_MAC
        ok = close_tab()
        self.assertTrue(ok)
        mock_hotkey.assert_called_with(*HOTKEY_CLOSE_MAC)


if __name__ == "__main__":
    unittest.main()
