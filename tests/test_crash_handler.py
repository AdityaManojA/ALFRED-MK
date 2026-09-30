import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from core import crash_handler as handler


class CrashHandlerTests(unittest.TestCase):
    def test_report_and_log(self):
        try:
            raise ValueError("test failure")
        except ValueError:
            report = handler.format_crash_report(*sys.exc_info())
        self.assertIn("ValueError: test failure", report)
        self.assertIn("test_report_and_log", report)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "crashes.log"
            with patch.object(handler, "CRASH_LOG_FILE", path):
                handler.log_crash(report)
                handler.log_crash(report)
            self.assertEqual(path.read_text(encoding="utf-8").count("CRASH REPORT"), 2)

    def test_email_encoding_and_size(self):
        with patch.object(handler.sys, "platform", "linux"), patch.object(
            handler.webbrowser, "open", return_value=True
        ) as launch:
            self.assertTrue(handler.open_email_client("Error: ValueError: A&B #?\n" + "長" * 2000))
        url = launch.call_args.args[0]
        self.assertLessEqual(len(url), 1900)
        self.assertEqual(urlsplit(url).path, handler.DEVELOPER_EMAIL)
        query = parse_qs(urlsplit(url).query)
        self.assertEqual(query["subject"], ["ALFRED Crash Report"])
        self.assertIn("ValueError: A&B #?", query["body"][0])
        self.assertIn("truncated", query["body"][0])

    def test_email_requires_report_click(self):
        for clicked in (True, False):
            with self.subTest(clicked=clicked), patch.object(handler, "log_crash") as log, patch.object(
                handler, "show_crash_dialog", return_value=clicked
            ), patch.object(handler, "open_email_client") as email:
                with self.assertRaises(SystemExit) as exit_info:
                    handler._handle_exception(ValueError, ValueError("failure"), None)
                self.assertEqual(exit_info.exception.code, 1)
                log.assert_called_once()
                self.assertEqual(email.call_count, int(clicked))

    def test_headless_fallback(self):
        with patch.object(handler.sys, "platform", "linux"), patch.dict(
            handler.os.environ, {}, clear=True
        ), patch.object(handler, "_print") as output:
            self.assertFalse(handler.show_crash_dialog("Error: broken"))
        self.assertIn(handler.DEVELOPER_EMAIL, output.call_args.args[0])

    def test_log_failure_does_not_raise(self):
        with patch.object(handler, "CRASH_LOG_FILE") as path, patch.object(handler, "_print"):
            path.parent.mkdir.side_effect = PermissionError("denied")
            handler.log_crash("report")

    def test_keyboard_interrupt_is_not_reported(self):
        with patch.object(sys, "__excepthook__") as original, patch.object(handler, "log_crash") as log:
            handler._handle_exception(KeyboardInterrupt, KeyboardInterrupt(), None)
        original.assert_called_once()
        log.assert_not_called()


if __name__ == "__main__":
    unittest.main()
