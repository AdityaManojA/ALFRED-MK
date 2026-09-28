"""Privacy Test for Focus State: Mandatory verification of structural privacy.

Asserts that synthetic identities with random unique tokens for app_id, host,
and spoken label NEVER appear in:
1. asdict(state)
2. SentrySnapshot
3. mode_manager state
"""
import unittest
import uuid
from dataclasses import asdict

from core.sentry.focus.engine import FocusEngine
from core.sentry.focus.reader import BasePlatformReader, SurfaceIdentity, hash_host
from core.sentry.mode_manager import get_sentry_mode_manager


class MockSyntheticReader(BasePlatformReader):
    def __init__(self, identities):
        self.identities = list(identities)
        self.idx = 0

    def get_frontmost_surface(self, from_card: bool = False) -> SurfaceIdentity:
        if not self.identities:
            return SurfaceIdentity(capability="UNKNOWN")
        surf = self.identities[self.idx % len(self.identities)]
        self.idx += 1
        return surf


class TestFocusStatePrivacy(unittest.TestCase):
    def test_strict_token_privacy(self):
        token_app = f"app_{uuid.uuid4().hex}"
        token_host = f"host_{uuid.uuid4().hex}.com"
        token_label = f"label_{uuid.uuid4().hex}"
        token_intent = f"intent_{uuid.uuid4().hex}"

        host_hash = hash_host(token_host)

        # Ensure synthetic tokens are unique non-empty strings
        for tok in (token_app, token_host, token_label, token_intent):
            self.assertGreater(len(tok), 10)

        # Setup mock reader producing synthetic tokens
        synthetic_surface = SurfaceIdentity(
            app_id=token_app,
            tab_host_hash=host_hash,
            is_home_base=False,
            is_browser=True,
            is_self=False,
            spoken_label=token_label,
            capability="FULL",
        )

        reader = MockSyntheticReader([synthetic_surface])
        engine = FocusEngine(reader=reader)
        mgr = get_sentry_mode_manager()

        # Start session with intent
        engine.start(duration_minutes=25, intent=token_intent, lock_app=True, lock_tab=True)

        # Run several ticks
        for _ in range(5):
            engine.tick()

        state = engine.get_state()
        state_dict = asdict(state)
        snapshot = mgr.get_snapshot()
        snap_dict = asdict(snapshot)

        # Check serialization as well
        state_str = str(state_dict)
        snap_str = str(snap_dict)

        # Critical Privacy Assertion: None of the tokens must appear in state_dict or snapshot!
        for token in (token_app, token_host, token_label, token_intent):
            self.assertNotIn(token, state_str, f"Privacy violation! Token '{token}' found in FocusState!")
            self.assertNotIn(token, snap_str, f"Privacy violation! Token '{token}' found in SentrySnapshot!")

        # Also verify that the raw host string was hashed and not kept plain
        self.assertNotIn(token_host, state_str)
        self.assertNotIn(token_host, snap_str)

        # Clean up
        engine.abort("Privacy test finished")
