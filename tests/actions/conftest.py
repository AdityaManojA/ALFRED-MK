"""Shared fixtures for tests/actions.

Several action modules import PyAutoGUI at module import time. On a headless
Linux runner the real package raises (no DISPLAY) during import, so substitute
a MagicMock module when — and only when — the real import fails. Tests that
exercise PyAutoGUI calls always patch the module attribute explicitly anyway,
so no real keystrokes or mouse moves ever happen.
"""
import os
import sys
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:  # pragma: no cover - depends on the host
    import pyautogui  # noqa: F401
except Exception:  # ImportError, KeyError('DISPLAY'), Xlib errors ...
    sys.modules["pyautogui"] = MagicMock(name="pyautogui")
