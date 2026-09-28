"""Unit and integration tests for Phase 5: Deferred lock, answer window, and settle rule."""
import time
import unittest

from core.sentry.focus.engine import FocusEngine
from core.sentry.focus.reader import BasePlatformReader, SurfaceIdentity, hash_host


class MockSettleReader(BasePlatformReader):
    def __init__(self, current_surf):
        self.current = current_surf

    def set_current(self, surf):
        self.current = surf

    def get_frontmost_surface(self, from_card: bool = False) -> SurfaceIdentity:
        return self.current


class TestDeferredLock(unittest.TestCase):
    def setUp(self):
        self.spoken = []
        self.home_surf = SurfaceIdentity(app_id="alfred", is_home_base=True, is_self=True, capability="FULL")
        self.work_surf = SurfaceIdentity(
            app_id="chrome.exe",
            tab_host_hash=hash_host("github.com"),
            is_browser=True,
            spoken_label="GitHub",
            capability="FULL",
        )
        self.reader = MockSettleReader(self.home_surf)
        self.engine = FocusEngine(
            reader=self.reader,
            speak_fn=lambda txt: self.spoken.append(txt),
            auto_tick=False,
        )

    def tearDown(self):
        self.engine.abort("Teardown")

    def test_start_on_home_base_defers_and_prompts(self):
        # 1. Start session while on home base (prompt_intent=False for synchronous unit test)
        res = self.engine.start(duration_minutes=25, prompt_intent=False)
        self.assertTrue(res["active"])
        self.assertTrue(res["deferred_lock"])
        self.assertFalse(res["locked_app"])
        self.assertFalse(res["locked_tab"])

        st = self.engine.get_state()
        self.assertTrue(st.deferred_lock)

    def test_settle_rule_requires_two_consecutive_ticks(self):
        # Start in deferred lock
        self.engine.start(duration_minutes=25, prompt_intent=False)
        self.assertTrue(self.engine.get_state().deferred_lock)

        # Switch to work tab
        self.reader.set_current(self.work_surf)

        # Tick 1: first observation on work tab (SETTLE_TICKS = 2 not yet reached)
        self.engine.tick()
        st1 = self.engine.get_state()
        self.assertTrue(st1.deferred_lock, "Should still be deferred after only 1 tick")
        self.assertFalse(any("Locked on, sir" in s for s in self.spoken))

        # Tick 2: second consecutive observation on work tab -> settles!
        self.engine.tick()
        st2 = self.engine.get_state()
        self.assertFalse(st2.deferred_lock, "Should settle and lock after 2 consecutive ticks")
        self.assertTrue(st2.locked_app)
        self.assertTrue(st2.locked_tab)
        self.assertTrue(any("Locked on, sir." in s for s in self.spoken))

    def test_only_where_i_am_can_settle_home_base_fallback(self):
        # User stays on home base for 45 ticks
        self.engine.start(duration_minutes=25, prompt_intent=False)
        self.assertTrue(self.engine.get_state().deferred_lock)

        # 44 ticks on home base
        for _ in range(44):
            self.engine.tick()
        self.assertTrue(self.engine.get_state().deferred_lock)

        # 45th tick triggers fallback
        self.engine.tick()
        st_fallback = self.engine.get_state()
        self.assertFalse(st_fallback.deferred_lock)
        self.assertTrue(st_fallback.locked_app)
        self.assertTrue(any("Falling back to application-only focus" in s for s in self.spoken))


if __name__ == "__main__":
    unittest.main()
