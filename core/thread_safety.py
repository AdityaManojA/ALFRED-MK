"""
core/thread_safety.py — Qt GUI thread safety assertions and marshalling helpers.

Rules:
- Blocking is the enemy: any I/O, sleep, or long computation on the Qt GUI thread causes lag.
- Qt objects, widgets, and QTimers must only be created and accessed from the GUI thread.
- Named constants at top of file.
"""

from __future__ import annotations

import functools
import logging
import threading
import traceback
from typing import Any, Callable

from PyQt6.QtCore import QCoreApplication, QThread, QTimer
from PyQt6.QtWidgets import QApplication

# ── Configuration Constants ──────────────────────────────────────────────────
STRICT_GUI_ASSERTIONS: bool = False
LOG_STACK_TRACE_ON_VIOLATION: bool = False
THREAD_SAFETY_LOG_LEVEL: int = logging.WARNING

logger = logging.getLogger("core.thread_safety")


def is_gui_thread() -> bool:
    """Return True if the caller is currently on the Qt GUI thread."""
    app = QApplication.instance()
    if app is None:
        return True
    return QThread.currentThread() == app.thread()


def assert_gui_thread(
    context_name: str = "method",
    raise_error: bool | None = None,
) -> bool:
    """Check that the current thread is the Qt GUI thread.

    If called off-thread:
      - Logs a warning with context information.
      - If raise_error is True (or STRICT_GUI_ASSERTIONS is True and raise_error is not False),
        raises RuntimeError.
    Returns True if on GUI thread, False otherwise.
    """
    should_raise = STRICT_GUI_ASSERTIONS if raise_error is None else raise_error

    if not is_gui_thread():
        curr_thread = threading.current_thread()
        app = QApplication.instance()
        target = app.thread() if app is not None else "MainThread"
        msg = (
            f"Thread assertion failed: {context_name} must be called on Qt GUI thread ({target}), "
            f"but was called on '{curr_thread.name}' (id={curr_thread.ident}, {QThread.currentThread()})"
        )
        if LOG_STACK_TRACE_ON_VIOLATION:
            msg += "\n" + "".join(traceback.format_stack())
        logger.log(THREAD_SAFETY_LOG_LEVEL, msg)

        if should_raise:
            raise RuntimeError(msg)
        return False
    return True


def run_on_gui_thread(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    """Execute `fn(*args, **kwargs)` on the Qt GUI thread.

    If already on the GUI thread, executes immediately.
    If called from a worker thread, schedules it via QTimer.singleShot(0, ...).
    """
    if is_gui_thread():
        fn(*args, **kwargs)
    else:
        app = QApplication.instance()
        if app is not None:
            QTimer.singleShot(0, lambda: fn(*args, **kwargs))
        else:
            # Fallback when Qt app is not yet instantiated
            fn(*args, **kwargs)


def gui_thread_only(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator ensuring a method/function runs on the GUI thread.

    If invoked from an off-thread, it re-dispatches the call to the Qt event loop
    via QTimer.singleShot(0, ...) and returns None immediately.
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if is_gui_thread():
            return func(*args, **kwargs)
        run_on_gui_thread(func, *args, **kwargs)
        return None
    return wrapper
