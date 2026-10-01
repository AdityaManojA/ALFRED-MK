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
        self.temp_config_file = Path("test_ui_api_keys.json")
        if self.temp_config_file.exists():
            self.temp_config_file.unlink()

        self.store = SecretStore(secrets_path=self.temp_store_file)
        self.patcher = patch("core.secrets.store.get_secret_store", return_value=self.store)
        self.patcher.start()
        self.config_patcher = patch("actions.spotify_control.API_CONFIG_PATH", self.temp_config_file)
        self.config_patcher.start()

    def tearDown(self):
        self.config_patcher.stop()
        self.patcher.stop()
        if self.temp_store_file.exists():
            self.temp_store_file.unlink()
        if self.temp_config_file.exists():
            self.temp_config_file.unlink()

    def test_modal_initialization_and_tabs(self):
        modal = SetupApiModal(store=self.store)
        self.assertEqual(modal._tabs.count(), 3)
        self.assertEqual(modal._tabs.tabText(0), "GOOGLE WORKSPACE")
        self.assertEqual(modal._tabs.tabText(1), "SPOTIFY")
        self.assertEqual(modal._tabs.tabText(2), "GMAIL API")

    def test_masked_inputs(self):
        modal = SetupApiModal(store=self.store)
        # Verify inputs are set to Password echo mode for privacy
        self.assertEqual(modal._spotify_id_input.echoMode(), QLineEdit.EchoMode.Password)
        self.assertEqual(modal._spotify_secret_input.echoMode(), QLineEdit.EchoMode.Password)
        self.assertEqual(modal._gw_id_input.echoMode(), QLineEdit.EchoMode.Password)
        self.assertEqual(modal._gw_secret_input.echoMode(), QLineEdit.EchoMode.Password)
        self.assertEqual(modal._gmail_key_input.echoMode(), QLineEdit.EchoMode.Password)

    def test_submit_spotify_valid(self):
        modal = SetupApiModal(store=self.store)
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
        modal = SetupApiModal(store=self.store)
        modal._spotify_id_input.setText("invalid-id")
        modal._spotify_secret_input.setText("invalid-secret")

        saved_signal_emitted = []
        modal.config_saved.connect(lambda name: saved_signal_emitted.append(name))

        modal._submit_spotify()
        QApplication.processEvents()

        self.assertEqual(len(saved_signal_emitted), 0)
        self.assertIn("Spotify Client ID must be exactly 32 alphanumeric characters", modal._footer_status.text())

    def test_customize_overlay_has_services_setup_button(self):
        from ui import CustomizeOverlay
        from PyQt6.QtWidgets import QPushButton
        cov = CustomizeOverlay()
        self.assertTrue(hasattr(cov, "_services_api_btn"))
        self.assertIn("SETUP SPOTIFY, GMAIL & WORKSPACE", cov._services_api_btn.text())

        signal_emitted = []
        cov.setup_api_requested.connect(lambda: signal_emitted.append(True))
        cov._services_api_btn.click()
        self.assertTrue(signal_emitted)

    def test_setup_overlay_has_services_setup_button(self):
        from ui import SetupOverlay
        from PyQt6.QtWidgets import QPushButton
        sov = SetupOverlay()
        self.assertTrue(hasattr(sov, "setup_api_requested"))
        btn = None
        for b in sov.findChildren(QPushButton):
            if "SETUP SPOTIFY" in b.text():
                btn = b
                break
        self.assertIsNotNone(btn)
        signal_emitted = []
        sov.setup_api_requested.connect(lambda: signal_emitted.append(True))
        btn.click()
        self.assertTrue(signal_emitted)


if __name__ == "__main__":
    unittest.main()
