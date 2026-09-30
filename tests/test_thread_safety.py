"""
tests/test_thread_safety.py — Unit tests for core.thread_safety.
"""

from __future__ import annotations

import threading
import unittest

from PyQt6.QtWidgets import QApplication

_APP = QApplication.instance() or QApplication([])

from core.thread_safety import (
    assert_gui_thread,
    is_gui_thread,
    run_on_gui_thread,
    gui_thread_only,
    STRICT_GUI_ASSERTIONS,
)


class TestThreadSafety(unittest.TestCase):

    def test_is_gui_thread_on_main(self):
        self.assertTrue(is_gui_thread())

    def test_is_gui_thread_on_worker(self):
        worker_res = []

        def worker():
            worker_res.append(is_gui_thread())

        t = threading.Thread(target=worker)
        t.start()
        t.join()
        self.assertEqual(worker_res, [False])

    def test_assert_gui_thread_main(self):
        # Should return True without error
        self.assertTrue(assert_gui_thread("test_main", raise_error=True))

    def test_assert_gui_thread_worker_warning_no_raise(self):
        worker_res = []

        def worker():
            worker_res.append(assert_gui_thread("test_worker", raise_error=False))

        t = threading.Thread(target=worker)
        t.start()
        t.join()
        self.assertEqual(worker_res, [False])

    def test_assert_gui_thread_worker_raise(self):
        error_raised = []

        def worker():
            try:
                assert_gui_thread("test_worker_raise", raise_error=True)
            except RuntimeError as e:
                error_raised.append(e)

        t = threading.Thread(target=worker)
        t.start()
        t.join()
        self.assertEqual(len(error_raised), 1)
        self.assertIn("must be called on Qt GUI thread", str(error_raised[0]))

    def test_gui_thread_only_decorator(self):
        executed = []

        @gui_thread_only
        def target(x: int):
            executed.append(x)

        target(42)
        self.assertEqual(executed, [42])


if __name__ == "__main__":
    unittest.main()
