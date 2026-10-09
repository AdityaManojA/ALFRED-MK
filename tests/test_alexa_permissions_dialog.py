"""
tests/test_alexa_permissions_dialog.py — Unit tests for AlexaPermissionsDialog.
"""
import sys
import unittest

from PyQt6.QtWidgets import QApplication

from core.integrations.alexa.policy import AlexaActionPolicy
from core.secrets.store import SecretStore
from core.ui.alexa_permissions_dialog import AlexaPermissionsDialog

app = QApplication.instance() or QApplication(sys.argv)


class TestAlexaPermissionsDialog(unittest.TestCase):
    """Test suite validating permissions dialog interactions and persistence."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        self._temp_dir = tempfile.TemporaryDirectory()
        temp_file = Path(self._temp_dir.name) / "test_secrets.env"
        self.store = SecretStore(secrets_path=temp_file)
        self.policy = AlexaActionPolicy()
        self.dialog = AlexaPermissionsDialog(policy=self.policy, store=self.store)

    def tearDown(self):
        self.dialog.close()
        self._temp_dir.cleanup()

    def test_dialog_initialization(self):
        self.assertIsNotNone(self.dialog)
        self.assertEqual(len(self.dialog._checkboxes), 7)
        self.assertTrue(self.dialog._checkboxes["focus_mode"].isChecked())

    def test_toggle_updates_policy(self):
        cb = self.dialog._checkboxes["media_playback"]
        self.assertTrue(cb.isChecked())

        # Uncheck media playback
        cb.setChecked(False)
        self.dialog._save_and_close()

        self.assertFalse(self.policy.is_capability_enabled("media_playback"))

    def test_reset_to_safe_defaults(self):
        # Disable several capabilities
        self.dialog._checkboxes["focus_mode"].setChecked(False)
        self.dialog._checkboxes["internet_speed"].setChecked(False)
        self.dialog._save_and_close()

        self.assertFalse(self.policy.is_capability_enabled("focus_mode"))
        self.assertFalse(self.policy.is_capability_enabled("internet_speed"))

        # Trigger reset
        self.dialog._reset_defaults()
        self.dialog._save_and_close()

        self.assertTrue(self.dialog._checkboxes["focus_mode"].isChecked())
        self.assertTrue(self.dialog._checkboxes["internet_speed"].isChecked())
        self.assertTrue(self.policy.is_capability_enabled("focus_mode"))
        self.assertTrue(self.policy.is_capability_enabled("internet_speed"))


if __name__ == "__main__":
    unittest.main()
