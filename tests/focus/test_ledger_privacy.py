import json
import os
import shutil
import tempfile
import unittest

from core.sentry.focus.engine import FocusEngine
from core.sentry.focus.ledger import FocusLedger
from core.sentry.focus.reader import BasePlatformReader, SurfaceIdentity
from core.sentry.focus.state import Cadence


class MockSensitiveReader(BasePlatformReader):
    """Produces surfaces with highly sensitive app names, raw titles, and labels."""

    def __init__(self, surfaces):
        self.surfaces = list(surfaces)
        self.idx = 0

    def get_frontmost_surface(self, from_card: bool = False) -> SurfaceIdentity:
        if self.idx < len(self.surfaces):
            s = self.surfaces[self.idx]
            self.idx += 1
            return s
        return self.surfaces[-1] if self.surfaces else SurfaceIdentity(
            app_id="DefaultSecretApp.exe",
            raw_title="Classified Project Secret",
            spoken_label="DefaultSecret",
            capability="FULL",
        )


class TestLedgerPrivacy(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.ledger_file = os.path.join(self.temp_dir, "test_focus_ledger.json")
        self.ledger = FocusLedger(self.ledger_file)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_ledger_aggregates_totals_only(self):
        """Verify schema and numerical aggregation in ledger file."""
        self.assertEqual(self.ledger.total_sessions, 0)
        self.assertEqual(self.ledger.clean_streak, 0)

        # Record session 1: planned 1500s (25m), on target 1500s, 0 drift
        res1 = self.ledger.record_session(1500, 1500, 0, timestamp=1700000000.0)
        self.assertEqual(res1["clean_streak"], 1)
        self.assertEqual(res1["previous_streak"], 0)
        self.assertFalse(res1["streak_broken"])

        # Record session 2: planned 1500s, on target 1400s, 1 drift
        res2 = self.ledger.record_session(1500, 1400, 1, timestamp=1700000000.0)
        self.assertEqual(res2["clean_streak"], 0)
        self.assertEqual(res2["previous_streak"], 1)
        self.assertFalse(res2["streak_broken"])  # prev < 3, so not reported as broken

        # Read raw json from disk
        with open(self.ledger_file, "r", encoding="utf-8") as f:
            raw = json.load(f)

        expected_keys = {
            "total_sessions",
            "total_planned_seconds",
            "total_on_target_seconds",
            "total_drift_count",
            "clean_streak",
            "best_clean_streak",
            "daily_buckets",
        }
        self.assertEqual(set(raw.keys()), expected_keys)
        self.assertEqual(raw["total_sessions"], 2)
        self.assertEqual(raw["total_planned_seconds"], 3000)
        self.assertEqual(raw["total_on_target_seconds"], 2900)
        self.assertEqual(raw["total_drift_count"], 1)
        self.assertEqual(raw["best_clean_streak"], 1)

        # Check daily bucket structure
        buckets = raw["daily_buckets"]
        self.assertEqual(len(buckets), 1)
        day_stat = next(iter(buckets.values()))
        self.assertEqual(set(day_stat.keys()), {"sessions", "on_target_s", "drift_count"})
        self.assertEqual(day_stat["sessions"], 2)
        self.assertEqual(day_stat["on_target_s"], 2900)
        self.assertEqual(day_stat["drift_count"], 1)

    def test_streak_mechanics_and_breaking(self):
        """Clean streaks increment on 0 drift, reset on drift, and flag broken if prev >= 3."""
        # Build a streak of 3
        self.ledger.record_session(1500, 1500, 0)
        self.ledger.record_session(1500, 1500, 0)
        res3 = self.ledger.record_session(1500, 1500, 0)
        self.assertEqual(res3["clean_streak"], 3)
        self.assertEqual(self.ledger.clean_streak, 3)

        # 4th session drifts: streak breaks
        res4 = self.ledger.record_session(1500, 1200, 2)
        self.assertEqual(res4["clean_streak"], 0)
        self.assertEqual(res4["previous_streak"], 3)
        self.assertTrue(res4["streak_broken"])

        # Check speech generation with broken streak
        speech_normal = self.ledger.generate_report_card(
            1500, 1200, 2, Cadence.NORMAL,
            previous_streak=3, clean_streak=0, streak_broken=True
        )
        self.assertIn("Clean streak broken at three.", speech_normal)
        self.assertIn("two brief detours", speech_normal)

        speech_drill = self.ledger.generate_report_card(
            1500, 1200, 2, Cadence.DRILL_SERGEANT,
            previous_streak=3, clean_streak=0, streak_broken=True
        )
        self.assertIn("Clean streak broken at three. Reset and go again.", speech_drill)

        speech_gentle = self.ledger.generate_report_card(
            1500, 1200, 2, Cadence.GENTLE,
            previous_streak=3, clean_streak=0, streak_broken=True
        )
        self.assertIn("Clean streak broken at three. Take a breath.", speech_gentle)

    def test_report_card_cadences(self):
        """Test speech text generation across normal, gentle, and drill_sergeant."""
        # 1. Zero drift session (streak = 4)
        speech_norm = self.ledger.generate_report_card(1500, 1500, 0, Cadence.NORMAL, 3, 4, False)
        self.assertIn("Session complete, sir.", speech_norm)
        self.assertIn("Clean streak is now four.", speech_norm)

        speech_gentle = self.ledger.generate_report_card(1500, 1500, 0, Cadence.GENTLE, 3, 4, False)
        self.assertIn("Well done, sir.", speech_gentle)
        self.assertIn("complete focus", speech_gentle)
        self.assertIn("Clean streak is now four.", speech_gentle)

        speech_drill = self.ledger.generate_report_card(1500, 1500, 0, Cadence.DRILL_SERGEANT, 3, 4, False)
        self.assertIn("Zero slips.", speech_drill)
        self.assertIn("Clean streak is now four.", speech_drill)

        # 2. Minor detour (1 slip, prev streak was 1 -> not broken)
        speech_gentle_slip = self.ledger.generate_report_card(1500, 1400, 1, Cadence.GENTLE, 1, 0, False)
        self.assertIn("with only one small slip. Take a breath.", speech_gentle_slip)
        self.assertNotIn("Clean streak", speech_gentle_slip)

    def test_ledger_privacy_end_to_end_no_strings_persisted(self):
        """CRITICAL PRIVACY TEST:
        Ensure that during an entire Focus session with confidential app names,
        private titles, user intent, and distraction labels fed in,
        NONE of these strings are EVER persisted into the focus ledger.
        """
        confidential_app = "ConfidentialTaxPortal_v2.exe"
        confidential_title = "Private Tax Filings & Offshore Holdings"
        confidential_intent = "Review top secret tax audits"
        distraction_app = "UltraAddictiveGame.exe"

        spoken_lines = []

        def mock_speak(text: str):
            spoken_lines.append(text)

        target_surface = SurfaceIdentity(
            app_id=confidential_app,
            raw_title=confidential_title,
            spoken_label="ConfidentialTax",
            capability="FULL",
        )
        drift_surface = SurfaceIdentity(
            app_id=distraction_app,
            raw_title="Play Games Now",
            spoken_label="DistractionGame",
            capability="FULL",
        )

        reader = MockSensitiveReader([
            target_surface,  # read at start()
            target_surface,  # tick 1 (settle 1)
            target_surface,  # tick 2 (settle 2 -> locked!)
            target_surface,  # tick 3 (on target)
            drift_surface,   # tick 4 (drift candidate)
        ])

        engine = FocusEngine(
            reader=reader,
            speak_fn=mock_speak,
            auto_tick=False,
            ledger=self.ledger,
        )

        # Start a short 4-second session with confidential intent
        engine.start(duration_minutes=1, intent=confidential_intent, prompt_intent=False)
        engine._planned_s = 4  # artificially short for unit test

        # Tick 1: settles step 1
        engine.tick()
        # Tick 2: settles step 2 -> announces "Locked on, sir."
        engine.tick()
        # Tick 3: on target
        engine.tick()
        # Tick 4: reaches planned duration (4s elapsed), terminates session & generates report
        engine.tick()

        self.assertFalse(engine.is_active)
        self.assertTrue(len(spoken_lines) > 0)

        # Verify that ledger file exists
        self.assertTrue(os.path.exists(self.ledger_file))

        # Read the raw ledger file content directly from disk
        with open(self.ledger_file, "r", encoding="utf-8") as f:
            ledger_disk_content = f.read()

        # STRUCTURAL PRIVACY INVARIANT: Check that NONE of the sensitive strings are in the file
        for sensitive in [
            confidential_app,
            confidential_title,
            confidential_intent,
            distraction_app,
            "ConfidentialTaxPortal",
            "Offshore Holdings",
            "secret tax audits",
            "UltraAddictiveGame",
            "ConfidentialTax",
            "DistractionGame",
        ]:
            self.assertNotIn(
                sensitive,
                ledger_disk_content,
                f"Privacy violation! Sensitive string '{sensitive}' leaked into focus_ledger.json!"
            )


if __name__ == "__main__":
    unittest.main()
