"""
tests/boot/test_lazy_boot.py — Unit tests for first-use lazy proxies and delayed service instantiation.
"""

from __future__ import annotations

import unittest

from core.boot.lazy import (
    LazyService,
    create_lazy_scheduler,
    create_lazy_sentry_mgr,
    create_lazy_monitor_controller,
    create_lazy_hud_video_controller,
)


class DummyUnderlying:
    def __init__(self, val: int = 10):
        self.val = val
        self.started = False

    def start(self):
        self.started = True
        return True


class TestLazyBoot(unittest.TestCase):

    def test_lazy_service_defers_instantiation(self):
        call_count = 0

        def _factory():
            nonlocal call_count
            call_count += 1
            return DummyUnderlying(val=42)

        proxy = LazyService(_factory, name="TestDummy")
        self.assertFalse(proxy.is_instantiated())
        self.assertEqual(call_count, 0)

        # Attribute access triggers first instantiation
        self.assertEqual(proxy.val, 42)
        self.assertTrue(proxy.is_instantiated())
        self.assertEqual(call_count, 1)

        # Second access does not re-instantiate
        self.assertTrue(proxy.start())
        self.assertEqual(call_count, 1)

    def test_lazy_scheduler_creation(self):
        spoken = []
        lazy_sched = create_lazy_scheduler(
            speak_fn=lambda s: spoken.append(s),
            notify_fn=lambda s: None,
        )
        self.assertFalse(lazy_sched.is_instantiated())
        # Inspecting representation does not instantiate
        self.assertIn("uninstantiated", repr(lazy_sched))

    def test_lazy_sentry_creation(self):
        lazy_sentry = create_lazy_sentry_mgr()
        self.assertFalse(lazy_sentry.is_instantiated())
        self.assertIn("uninstantiated", repr(lazy_sentry))

    def test_lazy_monitor_controller_creation(self):
        lazy_ctrl = create_lazy_monitor_controller()
        self.assertFalse(lazy_ctrl.is_instantiated())


if __name__ == "__main__":
    unittest.main()
