"""
tests/test_open_app.py — Unit tests for application resolution and launching.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch
import platform

from actions.open_app import _normalize, open_app

_SYSTEM = platform.system()


class TestOpenApp(unittest.TestCase):

    def test_normalize_brave(self):
        """Verify normalization maps Brave browser variants appropriately."""
        self.assertEqual(_normalize("Brave").lower(), "brave")
        self.assertEqual(_normalize("brave browser").lower(), "brave")

    def test_empty_app_name(self):
        """Verify passing empty app_name returns a clear error."""
        res = open_app({})
        self.assertIn("No application name provided", res)

    @unittest.skipUnless(_SYSTEM == "Windows", "Windows-specific test")
    def test_find_windows_app_path_brave(self):
        """Verify _find_windows_app_path resolves Brave to its real executable or shortcut."""
        from actions.open_app import _find_windows_app_path
        target = _find_windows_app_path("brave")
        self.assertIsNotNone(target)
        self.assertTrue("brave" in target.lower())

    @unittest.skipUnless(_SYSTEM == "Windows", "Windows-specific test")
    def test_launch_windows_mocked(self):
        """Verify _launch_windows calls os.startfile with resolved target."""
        from actions.open_app import _launch_windows
        with patch("os.startfile") as mock_startfile:
            success = _launch_windows("brave")
            self.assertTrue(success)
            mock_startfile.assert_called()


if __name__ == "__main__":
    unittest.main()
