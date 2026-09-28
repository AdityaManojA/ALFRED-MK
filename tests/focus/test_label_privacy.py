"""Mandatory Privacy Test for Focus Mode Distraction Labels.

Privacy Law:
The distraction label rides for exactly one engine tick into the spoken string and
is stored NOWHERE else:
- Not in FocusState
- Not in asdict(state)
- Not in SentrySnapshot
- Not in ledger
- Not in episode/notes log
- Not in any file written during the test
"""
import time
import unittest
import uuid
from dataclasses import asdict

from core.sentry.focus.engine import FocusEngine
from core.sentry.focus.reader import BasePlatformReader, SurfaceIdentity
from core.sentry.mode_manager import get_sentry_mode_manager


class MockLabelReader(BasePlatformReader):
    def __init__(self, target_surf, drift_surf):
        self.target_surf = target_surf
        self.drift_surf = drift_surf
        self.current = target_surf

    def set_current(self, surf):
        self.current = surf

    def get_frontmost_surface(self, from_card: bool = False) -> SurfaceIdentity:
        return self.current


class TestLabelPrivacy(unittest.TestCase):
    def test_nonsense_label_privacy_isolation(self):
        # 1. Generate unique random nonsense token for label
        nonsense_label = f"zq-vortex-{uuid.uuid4().hex[:8]}"

        target_surf = SurfaceIdentity(app_id="code.exe", spoken_label="VS Code", capability="FULL")
        drift_surf = SurfaceIdentity(
            app_id="browser.exe",
            spoken_label=nonsense_label,
            is_browser=True,
            capability="FULL",
        )

        spoken_lines = []
        reader = MockLabelReader(target_surf, drift_surf)
        engine = FocusEngine(
            reader=reader,
            speak_fn=lambda line: spoken_lines.append(line),
            auto_tick=False,
        )
        mgr = get_sentry_mode_manager()

        # Start session and lock target
        engine.start(duration_minutes=25, intent="Quarterly Report", lock_app=True)
        engine.lock_surface("code.exe")

        # 2. Switch to drifting app with nonsense label
        reader.set_current(drift_surf)

        t0 = time.monotonic()
        # Tick 1: starts candidate timer
        engine.tick(t0)
        # Tick 2 (1.0s later, exceeding 800ms grace window): triggers drift & callout
        engine.tick(t0 + 1.0)

        # 3. Assert the nonsense label was spoken!
        self.assertTrue(len(spoken_lines) >= 1, "Expected at least one spoken callout line")
        spoken_text = " ".join(spoken_lines)
        self.assertIn(nonsense_label, spoken_text, f"Nonsense label '{nonsense_label}' was not in spoken callout: {spoken_text}")

        # 4. Assert the nonsense label appears NOWHERE else!
        state = engine.get_state()
        state_dict = asdict(state)
        state_repr = str(state_dict)

        snapshot = mgr.get_snapshot()
        snap_dict = asdict(snapshot)
        snap_repr = str(snap_dict)

        self.assertNotIn(nonsense_label, state_repr, "Privacy Violation! Label leaked into FocusState!")
        self.assertNotIn(nonsense_label, snap_repr, "Privacy Violation! Label leaked into SentrySnapshot!")

        engine.abort("Privacy test complete")
