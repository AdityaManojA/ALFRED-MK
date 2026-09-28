"""Unit tests for voice routing ('lock on this tab') and card trap."""
import unittest

from actions.computer_settings import _detect_action
from actions.sentry_focus import sentry_focus_action
from core.sentry.focus.engine import FocusEngine, get_focus_engine
from core.sentry.focus.reader import BasePlatformReader, SurfaceIdentity, hash_host


class MockTrapReader(BasePlatformReader):
    def __init__(self, front_surf, browser_surf):
        self.front_surf = front_surf
        self.browser_surf = browser_surf

    def get_frontmost_surface(self, from_card: bool = False) -> SurfaceIdentity:
        if from_card:
            return self.browser_surf
        return self.front_surf


class TestVoiceRoutingAndCardTrap(unittest.TestCase):
    def test_voice_route_ahead_of_os_screen_lock(self):
        # Verify that computer_settings does NOT match screen lock for focus phrases
        phrases = [
            "lock on this tab",
            "lock this tab",
            "keep me in this tab",
            "this is the tab",
            "stay on this tab",
            "lock this app",
            "okay I'm gonna need you to keep me in this tab",
        ]
        for phrase in phrases:
            detected = _detect_action(phrase)
            self.assertNotEqual(
                detected.get("action"),
                "lock_screen",
                f"Collision! Phrase '{phrase}' triggered OS lock_screen!",
            )

        # Real screen lock still works
        self.assertEqual(_detect_action("lock")["action"], "lock_screen")
        self.assertEqual(_detect_action("lock the pc")["action"], "lock_screen")

    def test_lock_tab_action_browser_flow(self):
        engine = get_focus_engine()
        spoken = []
        browser_surf = SurfaceIdentity(
            app_id="chrome.exe",
            tab_host_hash=hash_host("github.com"),
            is_browser=True,
            spoken_label="GitHub",
            capability="FULL",
        )
        home_surf = SurfaceIdentity(app_id="alfred", is_home_base=True, is_self=True, capability="FULL")

        reader = MockTrapReader(front_surf=browser_surf, browser_surf=browser_surf)
        engine.set_reader(reader)
        engine.set_callbacks(speak_fn=lambda txt: spoken.append(txt))

        # Start session
        engine.start(duration_minutes=25, prompt_intent=False)

        # Call voice route 'lock on this tab' while frontmost is browser
        res = sentry_focus_action("lock_on_this_tab")
        self.assertIn("Locked on, sir", res)
        st = engine.get_state()
        self.assertFalse(st.deferred_lock)
        self.assertTrue(st.locked_app)
        self.assertTrue(st.locked_tab)

        # Switch to home base and call 'lock on this tab' -> re-arms deferred lock
        reader.front_surf = home_surf
        res2 = sentry_focus_action("lock_on_this_tab")
        self.assertIn("Go to it, sir", res2)
        st2 = engine.get_state()
        self.assertTrue(st2.deferred_lock)

    def test_card_trap_targeting(self):
        engine = get_focus_engine()
        home_surf = SurfaceIdentity(app_id="alfred", is_home_base=True, is_self=True, capability="FULL")
        browser_surf = SurfaceIdentity(
            app_id="msedge.exe",
            tab_host_hash=hash_host("stackoverflow.com"),
            is_browser=True,
            spoken_label="Stack Overflow",
            capability="FULL",
        )

        reader = MockTrapReader(front_surf=home_surf, browser_surf=browser_surf)
        engine.set_reader(reader)

        engine.start(duration_minutes=25, prompt_intent=False)
        # Calling lock_tab with from_card=True bypasses home base and locks top browser window
        res = sentry_focus_action("lock_on_this_tab", from_card=True)
        self.assertIn("Locked on, sir", res)
        st = engine.get_state()
        self.assertFalse(st.deferred_lock)
        self.assertTrue(st.locked_app)
        self.assertTrue(st.locked_tab)


if __name__ == "__main__":
    unittest.main()
