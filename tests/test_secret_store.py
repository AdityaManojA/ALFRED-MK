"""
Unit tests for core/secrets/store.py (Encrypted SecretStore).
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from core.secrets.store import SecretStore


class TestSecretStore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.secrets_file = Path(self.temp_dir) / "secrets.env"
        self.store = SecretStore(secrets_path=self.secrets_file)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_set_and_get_secret(self):
        self.store.set("spotify.client_id", "abc123def456")
        self.assertEqual(self.store.get("spotify.client_id"), "abc123def456")
        self.assertTrue(self.store.has("spotify.client_id"))

    def test_persistence_across_instances(self):
        self.store.set("gmail.api_key", "AIzaSyTestKey123")
        # Instantiate second store pointing to same file
        store2 = SecretStore(secrets_path=self.secrets_file)
        self.assertEqual(store2.get("gmail.api_key"), "AIzaSyTestKey123")

    def test_file_is_encrypted_on_disk(self):
        secret_val = "SUPER_SECRET_PAYLOAD_9988"
        self.store.set("test.secret", secret_val)
        raw_content = self.secrets_file.read_text(encoding="utf-8")
        # Ensure raw secret string never appears in plain text on disk
        self.assertNotIn(secret_val, raw_content)
        self.assertIn("test.secret=", raw_content)

    def test_delete_secret(self):
        self.store.set("temp.key", "val123")
        self.assertTrue(self.store.has("temp.key"))
        self.assertTrue(self.store.delete("temp.key"))
        self.assertFalse(self.store.has("temp.key"))
        self.assertIsNone(self.store.get("temp.key"))

    def test_format_validation(self):
        # 32 hex char Spotify client ID
        pattern = r"^[a-fA-F0-9]{32}$"
        valid_id = "a1b2c3d4e5f6789012345678abcdef01"
        invalid_id = "short_id_123"
        self.assertTrue(SecretStore.validate_format(valid_id, pattern))
        self.assertFalse(SecretStore.validate_format(invalid_id, pattern))


if __name__ == "__main__":
    unittest.main()
