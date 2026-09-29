import unittest
from unittest.mock import patch

from core.platform import get_backend
from core.platform.base import PlatformBackend
from core.platform.win import WindowsPlatformBackend
from core.platform.mac import MacPlatformBackend
from core.platform.linux import LinuxPlatformBackend


class TestPlatformSelection(unittest.TestCase):
    def test_backend_selection_types(self):
        backend = get_backend()
        self.assertIsInstance(backend, PlatformBackend)

    @patch("sys.platform", "darwin")
    def test_mac_backend_instantiation(self):
        backend = MacPlatformBackend()
        self.assertEqual(backend.platform_name(), "mac")

    @patch("sys.platform", "linux")
    def test_linux_backend_instantiation(self):
        backend = LinuxPlatformBackend()
        self.assertEqual(backend.platform_name(), "linux")

    @patch("sys.platform", "win32")
    def test_win_backend_instantiation(self):
        backend = WindowsPlatformBackend()
        self.assertEqual(backend.platform_name(), "windows")


if __name__ == "__main__":
    unittest.main()
