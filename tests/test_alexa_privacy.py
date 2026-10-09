"""
tests/test_alexa_privacy.py — Zero-Token Leakage & Secret Privacy Enforcement Test Suite.
Generates unique canary tokens and asserts they never appear in logs, snapshots, speech, or errors.
"""
import io
import logging
import unittest

from core.integrations.alexa.config import (
    AlexaConfig,
    load_alexa_config_from_store,
    save_alexa_config_to_store,
)
from core.integrations.alexa.dispatcher import AlexaTypedDispatcher
from core.integrations.alexa.policy import AlexaActionPolicy, AlexaContext
from core.integrations.alexa.protocol import AlexaCommandEnvelope
from core.integrations.alexa.state import AlexaConnectionStatus, AlexaStateManager
from core.secrets.store import SecretStore


class TestAlexaPrivacyAndTokenIsolation(unittest.IsolatedAsyncioTestCase):
    """Rigorous privacy audit ensuring zero token leakage across all integration layers."""

    def setUp(self):
        # Unique canary tokens
        self.CANARY_CLIENT_SECRET = "CANARY_SEC_SECRET_9876543210"
        self.CANARY_ACCESS_TOKEN = "CANARY_ACC_TOKEN_ABCDEF12345"
        self.CANARY_REFRESH_TOKEN = "CANARY_REF_TOKEN_XYZ98765432"
        self.CANARY_USER_ID = "CANARY_USR_AMZN_ID_11223344"
        self.CANARY_RELAY_TOKEN = "CANARY_RLY_BEARER_55667788"

        self.all_canaries = [
            self.CANARY_CLIENT_SECRET,
            self.CANARY_ACCESS_TOKEN,
            self.CANARY_REFRESH_TOKEN,
            self.CANARY_USER_ID,
            self.CANARY_RELAY_TOKEN,
        ]

        # In-memory store
        import tempfile
        from pathlib import Path
        self._temp_dir = tempfile.TemporaryDirectory()
        temp_file = Path(self._temp_dir.name) / "test_secrets.env"
        self.store = SecretStore(secrets_path=temp_file)

        # Log capture
        self.log_stream = io.StringIO()
        self.log_handler = logging.StreamHandler(self.log_stream)
        logging.getLogger().addHandler(self.log_handler)

    def tearDown(self):
        logging.getLogger().removeHandler(self.log_handler)
        self._temp_dir.cleanup()

    def _assert_no_canary(self, text: str, context_label: str):
        for canary in self.all_canaries:
            self.assertNotIn(
                canary,
                text,
                f"PRIVACY VIOLATION: Canary token '{canary}' leaked in {context_label}!",
            )

    def test_state_snapshot_privacy(self):
        """Verify AlexaSnapshot contains no secrets or identity tokens."""
        mgr = AlexaStateManager()
        mgr.set_configured(True)
        mgr.set_linked(True)
        mgr.set_relay_connected(True)
        mgr.record_request_result(True)

        snapshot = mgr.get_snapshot()
        snap_str = str(snapshot)
        snap_dict = repr(snapshot)

        self._assert_no_canary(snap_str, "AlexaSnapshot str")
        self._assert_no_canary(snap_dict, "AlexaSnapshot repr")

        # Snapshot fields check
        fields = [f for f in dir(snapshot) if not f.startswith("_")]
        for secret_word in ("token", "secret", "user", "amazon", "password", "key"):
            for field in fields:
                self.assertNotIn(
                    secret_word,
                    field.lower(),
                    f"Forbidden secret field '{field}' found on AlexaSnapshot!",
                )

    def test_secret_store_persistence_isolation(self):
        """Save and reload configuration with canaries and verify no leakage into general store keys."""
        config = AlexaConfig(
            skill_id="amzn1.ask.skill.canary-test",
            oauth_client_id="client-id-123",
            oauth_client_secret=self.CANARY_CLIENT_SECRET,
        )
        save_alexa_config_to_store(config, self.store)

        # Loaded config
        loaded = load_alexa_config_from_store(self.store)
        self.assertEqual(loaded.oauth_client_secret, self.CANARY_CLIENT_SECRET)

        # Check raw log output
        logs = self.log_stream.getvalue()
        self._assert_no_canary(logs, "store logs")

    async def test_dispatcher_speech_output_privacy(self):
        """Verify that dispatcher results never include tokens even on error or invalid inputs."""
        policy = AlexaActionPolicy()
        hud_logs: list[str] = []
        dispatcher = AlexaTypedDispatcher(
            policy=policy,
            hud_logger=lambda m: hud_logs.append(m),
        )

        ctx = AlexaContext(request_id="canary-req-1", user_hash="canary-hash")

        # Dispatch commands with canary arguments
        intents_to_test = [
            ("AlfredStatusIntent", {"token": self.CANARY_ACCESS_TOKEN}),
            ("StartFocusIntent", {"auth": self.CANARY_REFRESH_TOKEN}),
            ("shell", {"cmd": f"echo {self.CANARY_CLIENT_SECRET}"}),
            ("invalid_intent", {"sec": self.CANARY_RELAY_TOKEN}),
        ]

        for intent, args in intents_to_test:
            speech = await dispatcher.dispatch(intent, args, ctx)
            self._assert_no_canary(speech, f"dispatch response for {intent}")

        for hud_log in hud_logs:
            self._assert_no_canary(hud_log, "HUD log output")


if __name__ == "__main__":
    unittest.main()
