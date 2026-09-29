"""
core/gui_thread.py — Qt GUI thread assertions and marshalling helpers.
"""

from __future__ import annotations

from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import QApplication


def is_gui_thread() -> bool:
    """Return True if the current thread is the Qt main GUI thread."""
    app = QApplication.instance()
    if app is None:
        return True
    return QThread.currentThread() == app.thread()


def assert_gui_thread(context_name: str = "method") -> None:
    """Assert that the current code is running on the Qt GUI thread.
    
    Raises RuntimeError if called from a background / worker thread.
    """
    app = QApplication.instance()
    if app is not None and QThread.currentThread() != app.thread():
        raise RuntimeError(
            f"Thread assertion failed: {context_name} must be called on Qt GUI thread ({app.thread()}), "
            f"but was called on {QThread.currentThread()}"
        )
