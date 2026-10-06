"""
tests/test_linux_portaudio.py — Tests for graceful PortAudio library missing handling.
"""
import io
import unittest
from unittest.mock import patch

from core.audio_portaudio import (
    PORTAUDIO_MISSING_BANNER,
    handle_portaudio_os_error,
)


class TestLinuxPortAudio(unittest.TestCase):
    def test_banner_content(self):
        self.assertIn("CRITICAL DEPENDENCY MISSING: PortAudio", PORTAUDIO_MISSING_BANNER)
        self.assertIn("sudo apt-get install portaudio19-dev python3-pyaudio", PORTAUDIO_MISSING_BANNER)

    def test_handle_portaudio_error_exits_cleanly(self):
        exc = OSError("PortAudio library not found")
        with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            with self.assertRaises(SystemExit) as ctx:
                handle_portaudio_os_error(exc)
            self.assertEqual(ctx.exception.code, 1)
            err_output = mock_stderr.getvalue()
            self.assertIn("CRITICAL DEPENDENCY MISSING: PortAudio", err_output)
            self.assertIn("sudo apt-get install portaudio19-dev", err_output)

    def test_handle_unrelated_os_error_does_not_exit(self):
        exc = OSError("File not found or disk full")
        handled = handle_portaudio_os_error(exc)
        self.assertFalse(handled)


if __name__ == "__main__":
    unittest.main()
