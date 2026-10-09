"""
tests/test_alexa_account_linking.py — Unit tests for Alexa account linking, device mapping, and state token security.
"""
import time
import unittest

from core.integrations.alexa.account_link import AccountLinkingManager
from server.alexa.relay import DesktopRelayBridge


class TestAlexaAccountLinking(unittest.TestCase):
    """Test suite validating account linking tokens and device mappings."""

    def test_single_use_state_token(self):
        mgr = AccountLinkingManager(ttl_s=5.0)
        token = mgr.create_linking_state(device_id="desktop-alpha")
        self.assertTrue(bool(token))

        # Check valid before consumption
        self.assertTrue(mgr.is_state_valid(token))

        # First consumption succeeds
        state = mgr.consume_linking_state(token)
        self.assertIsNotNone(state)
        self.assertEqual(state.device_id, "desktop-alpha")

        # Second consumption fails (single-use enforcement)
        state_retry = mgr.consume_linking_state(token)
        self.assertIsNone(state_retry)
        self.assertFalse(mgr.is_state_valid(token))

    def test_state_token_expiration(self):
        # Short TTL (0.05 seconds)
        mgr = AccountLinkingManager(ttl_s=0.05)
        token = mgr.create_linking_state(device_id="desktop-beta")

        time.sleep(0.08)
        self.assertFalse(mgr.is_state_valid(token))
        state = mgr.consume_linking_state(token)
        self.assertIsNone(state)

    def test_device_state_revocation(self):
        mgr = AccountLinkingManager(ttl_s=60.0)
        t1 = mgr.create_linking_state("dev-1")
        t2 = mgr.create_linking_state("dev-1")
        t3 = mgr.create_linking_state("dev-2")

        revoked = mgr.revoke_device_states("dev-1")
        self.assertEqual(revoked, 2)
        self.assertFalse(mgr.is_state_valid(t1))
        self.assertFalse(mgr.is_state_valid(t2))
        self.assertTrue(mgr.is_state_valid(t3))

    def test_relay_user_device_mapping_and_unlinking(self):
        bridge = DesktopRelayBridge()
        amazon_user = "amzn1.ask.account.USER123456"
        desktop_id = "alfred-pc-aditya"

        bridge.link_user_to_device(amazon_user, desktop_id)
        self.assertEqual(bridge._user_device_map.get(amazon_user), desktop_id)

        # Unlink device clears user mapping
        count = bridge.unlink_device(desktop_id)
        self.assertEqual(count, 1)
        self.assertIsNone(bridge._user_device_map.get(amazon_user))


if __name__ == "__main__":
    unittest.main()
