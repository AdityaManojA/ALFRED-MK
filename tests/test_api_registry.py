"""
Unit tests for core/apis/registry.py (API backend validators & registry).
"""
import unittest

from core.apis.registry import (
    get_api_registry,
    get_backend,
    save_backend_credentials,
    validate_backend_fields,
)
from core.secrets.store import SecretStore
import tempfile
import shutil
from pathlib import Path


class TestApiRegistry(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.store = SecretStore(secrets_path=Path(self.temp_dir) / "secrets.env")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_registry_contains_required_backends(self):
        reg = get_api_registry()
        self.assertIn("google_workspace", reg)
        self.assertIn("spotify", reg)
        self.assertIn("gmail", reg)

    def test_spotify_validator(self):
        # Valid Spotify keys (32 hex characters)
        valid_fields = {
            "client_id": "a" * 32,
            "client_secret": "b" * 32,
        }
        ok, err = validate_backend_fields("spotify", valid_fields)
        self.assertTrue(ok, err)

        # Invalid short client_id
        invalid_fields = {
            "client_id": "too_short",
            "client_secret": "b" * 32,
        }
        ok, err = validate_backend_fields("spotify", invalid_fields)
        self.assertFalse(ok)
        self.assertIn("32 alphanumeric", err)

    def test_google_workspace_validator(self):
        valid_fields = {
            "client_id": "12345678901234567890.apps.googleusercontent.com",
            "client_secret": "GOCSPX-SecretPayload1234",
        }
        ok, err = validate_backend_fields("google_workspace", valid_fields)
        self.assertTrue(ok, err)

        invalid_fields = {
            "client_id": "short_id",
            "client_secret": "secret",
        }
        ok, err = validate_backend_fields("google_workspace", invalid_fields)
        self.assertFalse(ok)

    def test_gmail_validator(self):
        valid_pw_fields = {
            "email": "alfred@wayne.com",
            "app_password": "abcd efgh ijkl mnop",
            "auth_mode": "api_key",
        }
        ok, err = validate_backend_fields("gmail", valid_pw_fields)
        self.assertTrue(ok, err)

        # Valid OAuth json
        valid_oauth = {
            "auth_mode": "oauth_json",
            "credentials_json": '{"installed": {"client_id": "cid123", "client_secret": "csec123"}}',
        }
        ok, err = validate_backend_fields("gmail", valid_oauth)
        self.assertTrue(ok, err)

    def test_save_backend_credentials_encrypted(self):
        fields = {
            "client_id": "c" * 32,
            "client_secret": "d" * 32,
        }
        ok, msg = save_backend_credentials("spotify", fields, store=self.store)
        self.assertTrue(ok)
        self.assertEqual(self.store.get("spotify.client_id"), "c" * 32)
        self.assertEqual(self.store.get("spotify.client_secret"), "d" * 32)


if __name__ == "__main__":
    unittest.main()
