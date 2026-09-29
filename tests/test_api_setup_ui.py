import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication, QLineEdit

# Ensure QApplication exists for Qt tests
app = QApplication.instance() or QApplication(sys.argv)

from core.secrets.store import SecretStore
from ui.setup_api_modal import SetupApiModal


class TestApiSetupUI(unittest.TestCase):
    def setUp(self):
        self.temp_store_file = Path("test_ui_secrets.env")
        if self.temp_store_file.exists():
            self.temp_store_file.unlink()
        self.store = SecretStore(secrets_path=self.temp_store_file)
        self.patcher = patch("core.secrets.store.get_secret_store", return_value=self.store)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        if self.temp_store_file.exists():
            self.temp_store_file.unlink()

    def test_modal_initialization_and_tabs(self):
        modal = SetupApiModal()
        self.assertEqual(modal._tabs.count(), 3)
        self.assertEqual(modal._tabs.tabText(0), "GOOGLE WORKSPACE")
        self.assertEqual(modal._tabs.tabText(1), "SPOTIFY")
        self.assertEqual(modal._tabs.tabText(2), "GMAIL API")

    def test_masked_inputs(self):
        modal = SetupApiModal()
        # Verify inputs are set to Password echo mode for privacy
        self.assertEqual(modal._spotify_id_input.echoMode(), QLineEdit.EchoMode.Password)
        self.assertEqual(modal._spotify_secret_input.echoMode(), QLineEdit.EchoMode.Password)
        self.assertEqual(modal._gw_id_input.echoMode(), QLineEdit.EchoMode.Password)
        self.assertEqual(modal._gw_secret_input.echoMode(), QLineEdit.EchoMode.Password)
        self.assertEqual(modal._gmail_key_input.echoMode(), QLineEdit.EchoMode.Password)

    def test_submit_spotify_valid(self):
        modal = SetupApiModal()
        valid_id = "a" * 32
        valid_secret = "b" * 32
        modal._spotify_id_input.setText(valid_id)
        modal._spotify_secret_input.setText(valid_secret)

        saved_signal_emitted = []
        modal.config_saved.connect(lambda name: saved_signal_emitted.append(name))

        modal._submit_spotify()
        QApplication.processEvents()

        self.assertIn("Spotify", saved_signal_emitted)
        self.assertEqual(self.store.get("spotify.client_id"), valid_id)
        self.assertEqual(self.store.get("spotify.client_secret"), valid_secret)

    def test_submit_spotify_invalid(self):
        modal = SetupApiModal()
        modal._spotify_id_input.setText("invalid-id")
        modal._spotify_secret_input.setText("invalid-secret")

        saved_signal_emitted = []
        modal.config_saved.connect(lambda name: saved_signal_emitted.append(name))

        modal._submit_spotify()
        QApplication.processEvents()

        self.assertEqual(len(saved_signal_emitted), 0)
        self.assertIn("Spotify Client ID must be exactly 32 alphanumeric characters", modal._footer_status.text())


if __name__ == "__main__":
    unittest.main()
