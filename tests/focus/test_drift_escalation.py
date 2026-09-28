"""Unit and integration tests for Phase 4 drift grace window and escalation tiers."""
import time
import unittest

from core.sentry.focus.engine import FocusEngine
from core.sentry.focus.lines import FIRST_CALLOUT, TIER1, TIER2, TIER3, DRILL_SERGEANT
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

    def test_first_callout_names_intent_and_label(self):
        self.engine.start(duration_minutes=25, intent="Refactor Auth")
        self.engine.lock_surface("code.exe")

        # Excursion 1
        self.reader.set_current(self.drift)
        self.engine.tick() # candidate starts
        self.engine.tick() # grace passed -> triggers callout

        self.assertEqual(len(self.spoken), 1)
        callout = self.spoken[0]
        # First callout must name both intent and distraction
        self.assertIn("Reddit", callout)
        self.assertIn("Refactor Auth", callout)

    def test_tier_escalation_across_multiple_excursions(self):
        self.engine.start(duration_minutes=25)
        self.engine.lock_surface("code.exe")

        # Excursion 1 (Tier 1)
        self.reader.set_current(self.drift)
        self.engine.tick()
        self.engine.tick()
        st1 = self.engine.get_state()
        self.assertEqual(st1.tier, 1)
        self.assertEqual(st1.drift_count, 1)

        # Return to target (recovers)
        self.reader.set_current(self.target)
        self.engine.tick()
        self.assertFalse(self.engine.get_state().drifting)

        # Excursion 2 (Tier 2)
        self.reader.set_current(self.drift)
        self.engine.tick()
        self.engine.tick()
        st2 = self.engine.get_state()
        self.assertEqual(st2.tier, 2)
        self.assertEqual(st2.drift_count, 2)

        # Return to target
        self.reader.set_current(self.target)
        self.engine.tick()

        # Excursion 3 (Tier 3)
        self.reader.set_current(self.drift)
        self.engine.tick()
        self.engine.tick()
        st3 = self.engine.get_state()
        self.assertEqual(st3.tier, 3)
        self.assertEqual(st3.drift_count, 3)

    def test_drill_sergeant_mode(self):
        self.engine.start(duration_minutes=25)
        self.engine.lock_surface("code.exe")
        self.engine.set_drill_sergeant(True)

        self.reader.set_current(self.drift)
        self.engine.tick()
        self.engine.tick()

        self.assertEqual(len(self.spoken), 1)
        callout = self.spoken[0]
        # Drill sergeant style line
        self.assertTrue(any(marker in callout for marker in ("Drop the", "slack off", "discipline", "Unacceptable")))


if __name__ == "__main__":
    unittest.main()
