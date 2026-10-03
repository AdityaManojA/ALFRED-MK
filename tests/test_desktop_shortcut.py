"""
tests/test_desktop_shortcut.py — Unit tests for desktop shortcut resolution and creation fallbacks.
"""
from __future__ import annotations

import os
import platform
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_SYSTEM = platform.system()


class TestDesktopShortcut(unittest.TestCase):

    def test_get_desktop_dir(self):
        """Verify _get_desktop_dir returns a valid directory path."""
        from ui import MainWindow
        desktop = MainWindow._get_desktop_dir()
        self.assertIsInstance(desktop, Path)
        self.assertTrue(desktop.exists(), f"Desktop directory does not exist: {desktop}")

    @unittest.skipUnless(_SYSTEM == "Windows", "Windows-specific test")
    def test_create_lnk_windows_com_fallback(self):
        """Verify _create_lnk_windows falls back cleanly when win32com raises an Exception."""
        from ui import MainWindow

        with patch("subprocess.run") as mock_ps_run, \
             patch("subprocess.Popen") as mock_wscript, \
             patch("pathlib.Path.exists", return_value=True):

            # Force win32com to raise an arbitrary COM error
            with patch.dict("sys.modules", {"win32com.client": MagicMock()}):
                import sys
                sys.modules["win32com.client"].Dispatch.side_effect = RuntimeError("COM registration corrupted")

                # Should not raise; should fall back to WScript/PowerShell
                try:
                    MainWindow._create_lnk_windows(
                        lnk=r"C:\fake\A.L.F.R.E.D.lnk",
                        target=r"C:\fake\python.exe",
                        args=r"C:\fake\main.py",
                        work_dir=r"C:\fake",
                        icon_loc=r"C:\fake\alfred.ico",
                    )
                except Exception as e:
                    self.fail(f"_create_lnk_windows failed with exception: {e}")

    @unittest.skipUnless(_SYSTEM == "Windows", "Windows-specific test")
    def test_create_lnk_windows_powershell_invocation(self):
        """Verify PowerShell fallback is invoked if both pywin32 and wscript fail."""
        from ui import MainWindow

        # Both win32com and wscript fail, file only exists after PowerShell
        exists_calls = [False, False, True]

        def fake_exists(_self):
            if exists_calls:
                return exists_calls.pop(0)
            return True

        with patch("subprocess.run") as mock_ps_run, \
             patch("subprocess.Popen") as mock_wscript, \
             patch("pathlib.Path.exists", autospec=True, side_effect=fake_exists):

            mock_wscript.side_effect = FileNotFoundError("wscript not found")
            mock_ps_run.return_value = MagicMock(returncode=0)

            with patch.dict("sys.modules", {"win32com.client": None}):
                MainWindow._create_lnk_windows(
                    lnk=r"C:\fake\A.L.F.R.E.D.lnk",
                    target=r"C:\fake\python.exe",
                    args=r"C:\fake\main.py",
                    work_dir=r"C:\fake",
                    icon_loc=r"C:\fake\alfred.ico",
                )

            mock_ps_run.assert_called_once()
            call_args = mock_ps_run.call_args[0][0]
            self.assertIn("powershell.exe", call_args)
            self.assertIn("New-Object -ComObject WScript.Shell", call_args[-1])


if __name__ == "__main__":
    unittest.main()
