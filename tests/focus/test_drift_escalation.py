"""Unit and integration tests for Phase 4 drift grace window and escalation tiers."""
import time
import unittest

from core.sentry.focus.engine import FocusEngine
from core.sentry.focus.reader import BasePlatformReader, SurfaceIdentity


class MockEscalationReader(BasePlatformReader):
    def __init__(self, target_surf, drift_surf):
        self.target_surf = target_surf
        self.drift_surf = drift_surf
        self.current = target_surf

    def set_current(self, surf):
        self.current = surf

    def get_frontmost_surface(self, from_card: bool = False) -> SurfaceIdentity:
        return self.current


class TestDriftEscalation(unittest.TestCase):
    def setUp(self):
        self.spoken = []
        self.target = SurfaceIdentity(app_id="code.exe", spoken_label="VS Code", capability="FULL")
        self.drift = SurfaceIdentity(app_id="reddit.exe", spoken_label="Reddit", capability="FULL")
        self.reader = MockEscalationReader(self.target, self.drift)
        self.engine = FocusEngine(
            reader=self.reader,
            speak_fn=lambda txt: self.spoken.append(txt),
            auto_tick=False,
        )

    def tearDown(self):
        self.engine.abort("Teardown")

    def test_brief_switch_within_grace_window_does_not_drift(self):
        """Verify DRIFT_GRACE_MS = 800: switching away and returning within 800ms triggers NO drift."""
        self.engine.start(duration_minutes=25)
        self.engine.lock_surface("code.exe")

        t0 = time.monotonic()
        # Switch to drift app at t0
        self.reader.set_current(self.drift)
        self.engine.tick(t0) # candidate timer starts

        # Still within grace window at t0 + 0.4s (400ms < 800ms)
        self.engine.tick(t0 + 0.4)
        st_grace = self.engine.get_state()
        self.assertFalse(st_grace.drifting, "Must not flag drift while inside grace window")
        self.assertEqual(len(self.spoken), 0)

        # Switch back to target at t0 + 0.6s
        self.reader.set_current(self.target)
        self.engine.tick(t0 + 0.6)
        st_recovered = self.engine.get_state()
        self.assertFalse(st_recovered.drifting)
        self.assertEqual(len(self.spoken), 0, "No callout should be issued for brief switch within grace window")

    def test_first_callout_names_intent_and_label(self):
        self.engine.start(duration_minutes=25, intent="Refactor Auth")
        self.engine.lock_surface("code.exe")

        t0 = time.monotonic()
        # Excursion 1
        self.reader.set_current(self.drift)
        self.engine.tick(t0)
        self.engine.tick(t0 + 1.0) # exceeds 800ms grace window

        self.assertEqual(len(self.spoken), 1)
        callout = self.spoken[0]
        # First callout must name both intent and distraction
        self.assertIn("Reddit", callout)
        self.assertIn("Refactor Auth", callout)

    def test_tier_escalation_across_multiple_excursions(self):
        self.engine.start(duration_minutes=25)
        self.engine.lock_surface("code.exe")

        t = time.monotonic()

        # Excursion 1 (Tier 1)
        self.reader.set_current(self.drift)
        self.engine.tick(t)
        t += 1.0
        self.engine.tick(t)
        st1 = self.engine.get_state()
        self.assertEqual(st1.tier, 1)
        self.assertEqual(st1.drift_count, 1)

        # Return to target (recovers)
        self.reader.set_current(self.target)
        t += 1.0
        self.engine.tick(t)
        self.assertFalse(self.engine.get_state().drifting)

        # Excursion 2 (Tier 2)
        self.reader.set_current(self.drift)
        t += 1.0
        self.engine.tick(t)
        t += 1.0
        self.engine.tick(t)
        st2 = self.engine.get_state()
        self.assertEqual(st2.tier, 2)
        self.assertEqual(st2.drift_count, 2)

        # Return to target
        self.reader.set_current(self.target)
        t += 1.0
        self.engine.tick(t)

        # Excursion 3 (Tier 3)
        self.reader.set_current(self.drift)
        t += 1.0
        self.engine.tick(t)
        t += 1.0
        self.engine.tick(t)
        st3 = self.engine.get_state()
        self.assertEqual(st3.tier, 3)
        self.assertEqual(st3.drift_count, 3)

    def test_drill_sergeant_mode(self):
        self.engine.start(duration_minutes=25)
        self.engine.lock_surface("code.exe")
        self.engine.set_drill_sergeant(True)

        t0 = time.monotonic()
        self.reader.set_current(self.drift)
        self.engine.tick(t0)
        self.engine.tick(t0 + 1.0)

        self.assertEqual(len(self.spoken), 1)
        callout = self.spoken[0]
        # Drill sergeant style line
        self.assertTrue(any(marker in callout for marker in ("Drop the", "slack off", "discipline", "Unacceptable")))


if __name__ == "__main__":
    unittest.main()
