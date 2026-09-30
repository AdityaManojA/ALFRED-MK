"""
core/gui_thread.py — Qt GUI thread assertions and marshalling helpers.

Now powered by core.thread_safety.
"""

from __future__ import annotations

from core.thread_safety import (
    assert_gui_thread as _base_assert,
    is_gui_thread,
    run_on_gui_thread,
    gui_thread_only,
    STRICT_GUI_ASSERTIONS,
    LOG_STACK_TRACE_ON_VIOLATION,
)


def assert_gui_thread(context_name: str = "method") -> None:
    """Assert that the current code is running on the Qt GUI thread.

    Raises RuntimeError if called from a background / worker thread.
    """
    _base_assert(context_name=context_name, raise_error=True)
