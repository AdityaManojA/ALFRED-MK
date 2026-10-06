"""
tests/test_gmail_credentials.py — Unit tests for Gmail credential resolution, configuration mode, and UI synchronization.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from actions.gmail_manager import _load_gmail_creds, gmail_manager
from core.secrets.store import SecretStore


class TestGmailCredentials(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_config = Path(self.tmp_dir.name) / "test_api_keys.json"
        self.tmp_secrets = Path(self.tmp_dir.name) / "test_secrets.env"

        self.store = SecretStore(secrets_path=self.tmp_secrets)
        self.store_patcher = patch("core.secrets.store.get_secret_store", return_value=self.store)
        self.store_patcher.start()

        self.config_patcher = patch("actions.gmail_manager._CONFIG_PATH", self.tmp_config)
        self.config_patcher.start()

    def tearDown(self):
        self.config_patcher.stop()
        self.store_patcher.stop()
        self.tmp_dir.cleanup()

    def test_load_from_secret_store_email_key(self):
        """Verify _load_gmail_creds recognizes 'gmail.email' and strips spaces from app password."""
        self.store.set("gmail.email", "bruce.wayne@gmail.com")
        self.store.set("gmail.app_password", "abcd efgh ijkl mnop")

        user, pw = _load_gmail_creds()
        self.assertEqual(user, "bruce.wayne@gmail.com")
        self.assertEqual(pw, "abcdefghijklmnop")

    def test_load_from_config_file_aliases(self):
        """Verify _load_gmail_creds recognizes config file aliases (gmail_passkey, etc.)."""
        cfg = {
            "gmail_user": "alfred@wayneenterprises.com",
            "gmail_passkey": "wxyz 1234 5678 90ab",
        }
        self.tmp_config.write_text(json.dumps(cfg), encoding="utf-8")

        user, pw = _load_gmail_creds()
        self.assertEqual(user, "alfred@wayneenterprises.com")
        self.assertEqual(pw, "wxyz1234567890ab")

    def test_configure_mode_saves_both_stores(self):
        """Verify mode='configure' persists to both SecretStore and config/api_keys.json."""
        self.tmp_config.write_text("{}", encoding="utf-8")

        res = gmail_manager({
            "mode": "configure",
            "user": "test.user@gmail.com",
            "app_password": "1111 2222 3333 4444",
        })

        self.assertIn("Gmail configuration updated", res)
        self.assertEqual(self.store.get("gmail.email"), "test.user@gmail.com")
        self.assertEqual(self.store.get("gmail.user"), "test.user@gmail.com")
        self.assertEqual(self.store.get("gmail.app_password"), "1111222233334444")

        saved_cfg = json.loads(self.tmp_config.read_text(encoding="utf-8"))
        self.assertEqual(saved_cfg.get("gmail_user"), "test.user@gmail.com")
        self.assertEqual(saved_cfg.get("gmail_app_password"), "1111222233334444")

    def test_missing_credentials_diagnostic(self):
        """Verify clear diagnostic message when app password or user is missing."""
        # Neither
        res = gmail_manager({"mode": "summarize"})
        self.assertIn("requires your Google account credentials", res)

        # Only user
        self.store.set("gmail.email", "user@gmail.com")
        res = gmail_manager({"mode": "summarize"})
        self.assertIn("requires your 16-character Google App Password", res)

        # Only passkey
        self.store.delete("gmail.email")
        self.store.set("gmail.app_password", "abcdefghijklmnop")
        res = gmail_manager({"mode": "summarize"})
        self.assertIn("require your Gmail address", res)


if __name__ == "__main__":
    unittest.main()
