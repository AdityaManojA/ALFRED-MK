"""Unit and integration tests for FocusEngine lifecycle, ticks, and controls."""
import time
import unittest

from core.sentry.focus.engine import FocusEngine
from core.sentry.focus.reader import BasePlatformReader, SurfaceIdentity, hash_host


class MockReader(BasePlatformReader):
    def __init__(self, sequence=None):
        self.sequence = list(sequence or [])
        self.idx = 0

    def set_sequence(self, sequence):
        self.sequence = list(sequence)
        self.idx = 0

    def get_frontmost_surface(self, from_card: bool = False) -> SurfaceIdentity:
        if not self.sequence:
            return SurfaceIdentity(app_id="code.exe", capability="FULL")
        item = self.sequence[self.idx % len(self.sequence)]
        self.idx += 1
        return item


class TestFocusEngine(unittest.TestCase):
    def setUp(self):
        self.reader = MockReader()
        self.completed = []
        self.drifts = []
        self.engine = FocusEngine(
            reader=self.reader,
            on_complete=lambda: self.completed.append(True),
            on_drift=lambda surf, s: self.drifts.append((surf, s)),
            auto_tick=False,
        )

    def tearDown(self):
        self.engine.abort("Teardown")

    def test_start_pause_resume_extend(self):
        self.engine.start(duration_minutes=20, intent="Write tests", prompt_intent=False)
        st = self.engine.get_state()
        self.assertTrue(st.active)
        self.assertFalse(st.paused)
        self.assertEqual(st.planned_s, 1200)
        self.assertEqual(st.remaining_s, 1200)

        # Pause
        self.engine.pause()
        st2 = self.engine.get_state()
        self.assertTrue(st2.paused)

        # Tick while paused should not advance elapsed_s
        self.engine.tick()
        self.assertEqual(self.engine.get_state().elapsed_s, 0)

        # Resume
        self.engine.resume()
        self.assertFalse(self.engine.get_state().paused)

        # Tick while resumed
        self.engine.tick()
        self.assertEqual(self.engine.get_state().elapsed_s, 1)
        self.assertEqual(self.engine.get_state().remaining_s, 1199)

        # Extend
        rem = self.engine.extend(minutes=5)
        self.assertEqual(rem, 1199 + 300)
        self.assertEqual(self.engine.get_state().planned_s, 1500)

    def test_fresh_query_consecutive_ticks(self):
        """Verify fresh query every tick: log two different apps in consecutive ticks."""
        app1 = SurfaceIdentity(app_id="code.exe", spoken_label="VS Code", capability="FULL")
        app2 = SurfaceIdentity(app_id="chrome.exe", tab_host_hash=hash_host("youtube.com"), is_browser=True, capability="FULL")

        # Sequence: start() reads app1, tick 1 reads app1 (count 1), tick 2 reads app1 (count 2 -> settles!),
        # tick 3 reads app2 (candidate drift), tick 4 reads app2 (drift confirmed)
        self.reader.set_sequence([app1, app1, app1, app2, app2])
        self.engine.start(duration_minutes=10, prompt_intent=False)

        t0 = time.monotonic()
        # Tick 1 & 2 -> settles on app1
        self.engine.tick(t0)
        self.engine.tick(t0 + 1.0)
        st1 = self.engine.get_state()
        self.assertFalse(st1.deferred_lock)
        self.assertFalse(st1.drifting)
        self.assertEqual(st1.on_target_s, 2)

        # Tick 3 & 4 -> reads app2 (drifting past grace window)
        self.engine.tick(t0 + 2.0)
        self.engine.tick(t0 + 3.0)
        st2 = self.engine.get_state()
        self.assertTrue(st2.drifting)
        self.assertEqual(st2.current_drift_s, 1)
        self.assertEqual(st2.drift_count, 1)

    def test_snooze_and_excuse(self):
        app_drift = SurfaceIdentity(app_id="discord.exe", capability="FULL")

        self.reader.set_sequence([app_drift])
        self.engine.start(duration_minutes=10, prompt_intent=False)
        self.engine.lock_surface("code.exe")

        t0 = time.monotonic()
        # Snooze for 10 seconds
        until = self.engine.snooze(10)
        self.assertGreater(until, time.time())

        # Tick while snoozed: should not count as drift
        self.engine.tick(t0)
        self.engine.tick(t0 + 1.0)
        st = self.engine.get_state()
        self.assertFalse(st.drifting)

        # Clear snooze
        self.engine.snooze(0)
        t1 = time.monotonic() + 15.0
        self.engine.tick(t1)
        self.engine.tick(t1 + 1.0)
        self.assertTrue(self.engine.get_state().drifting)

        # Excuse flow
        self.engine.excuse("Doing research")
        st_excused = self.engine.get_state()
        self.assertTrue(st_excused.excused)
        self.assertEqual(st_excused.current_drift_s, 0)

    def test_session_survives_hud_lifecycle(self):
        """Verify countdown survives HUD minimize/close/recreation."""
        live_engine = FocusEngine(reader=self.reader, auto_tick=True)
        live_engine.start(duration_minutes=1, prompt_intent=False)

        st0 = live_engine.get_state()
        self.assertTrue(st0.active)
        self.assertEqual(st0.remaining_s, 60)

        # Simulate HUD minimized / closed: HUD detached, time elapses
        time.sleep(1.2)

        # Simulate HUD recreated: re-attaching to running singleton engine
        st_after = live_engine.get_state()
        self.assertTrue(st_after.active)
        self.assertLess(st_after.remaining_s, 60)

        live_engine.abort("Completed lifecycle test")


if __name__ == "__main__":
    unittest.main()
