"""Unit tests for the Batcomputer-Grade RemoteKeyOverlay."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QWidget

import ui
from ui import C, RemoteKeyOverlay, apply_ui_accent, retheme_all_widgets


class TestRemoteKeyOverlay(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.url = "https://192.168.1.100:8000"
        self.key = "BAT-9942"
        self.auto_url = "https://192.168.1.100:8000/login?token=xyz123"
        self.manual_url = "https://192.168.1.100:8000"
        self.desktop_url = "https://localhost:8001"
        self.parent = QWidget()
        self.overlay = RemoteKeyOverlay(
            url=self.url,
            key=self.key,
            auto_login_url=self.auto_url,
            manual_url=self.manual_url,
            desktop_url=self.desktop_url,
            expiry_secs=600,
            parent=self.parent,
        )

    def tearDown(self) -> None:
        self.overlay.close()
        self.parent.close()

    def test_all_pairing_values_present_in_widgets(self):
        """Verify QR, LAN URL, Localhost URL, manual host:port, and access key are populated."""
        self.assertEqual(self.overlay._key_lbl.text(), self.key)
        self.assertIn("192.168.1.100:8000", self.overlay._lan_lbl.text())
        self.assertIn("localhost:8001", self.overlay._local_lbl.text())
        self.assertEqual(self.overlay._manual_lbl.text(), "192.168.1.100:8000")
        self.assertFalse(self.overlay._qr_label.pixmap().isNull())

    def test_hyperlinks_accessible_and_open_external(self):
        """Verify link labels have LinksAccessibleByMouse and openExternalLinks=True."""
        for lbl in (self.overlay._lan_lbl, self.overlay._local_lbl):
            self.assertTrue(lbl.openExternalLinks())
            flags = lbl.textInteractionFlags()
            self.assertTrue(flags & Qt.TextInteractionFlag.LinksAccessibleByMouse)
            self.assertTrue(flags & Qt.TextInteractionFlag.TextSelectableByMouse)

    def test_copy_affordances_and_flash_feedback(self):
        """Verify copy buttons copy values to clipboard and show flash indicator."""
        # 1. LAN copy
        self.overlay._lan_copy_btn.click()
        self.assertEqual(QApplication.clipboard().text(), self.manual_url)
        self.assertTrue(self.overlay._lan_flash.isVisible())
        self.assertIn("COPIED", self.overlay._lan_flash.text())

        # 2. Key copy
        self.overlay._key_copy_btn.click()
        self.assertEqual(QApplication.clipboard().text(), self.key)
        self.assertTrue(self.overlay._key_flash.isVisible())

        # 3. Manual coordinate copy
        self.overlay._manual_copy_btn.click()
        self.assertEqual(QApplication.clipboard().text(), "192.168.1.100:8000")
        self.assertTrue(self.overlay._manual_flash.isVisible())

    @patch("webbrowser.open")
    def test_open_in_browser_action(self, mock_browser_open):
        """Verify primary action triggers browser open with desktop/auto-login link."""
        self.overlay._open_btn.click()
        mock_browser_open.assert_called_once_with(self.desktop_url)

    def test_new_key_refresh(self):
        """Verify NEW KEY updates access key, urls, and QR code."""
        new_tuple = (
            "https://192.168.1.100:8000",
            "WAYNE-8821",
            "https://192.168.1.100:8000/login?token=fresh456",
            "https://192.168.1.100:8000",
            "https://localhost:8001",
        )
        self.overlay.set_new_key_callback(lambda: new_tuple)
        self.overlay._new_btn.click()
        self.assertEqual(self.overlay._key_lbl.text(), "WAYNE-8821")
        self.assertEqual(self.overlay._current_key, "WAYNE-8821")
        self.assertIn("fresh456", self.overlay._auto_login_url)

    def test_mark_connected_state(self):
        """Verify connection handshake changes status indicators to green paired state."""
        self.overlay.mark_connected()
        self.assertEqual(self.overlay._key_lbl.text(), "UPLINK ACTIVE")
        self.assertEqual(self.overlay._qr_label.text(), "✓")
        self.assertIn("telemetry uplink active", self.overlay._timer_lbl.text())
        self.assertIn("HANDSHAKE VERIFIED", self.overlay._footer_lbl.text())

    def test_theme_retint_preserves_qr_scannability(self):
        """Retinting palette updates tactical colors while keeping QR high-contrast."""
        old_pal = ui.current_palette()
        # Switch to Bane theme (green)
        apply_ui_accent("#a8ff3e")
        new_pal = ui.current_palette()
        retheme_all_widgets(old_pal, new_pal)

        # Retint overlay
        self.overlay._apply_theme_styles()

        # Check that tactical colors updated
        self.assertEqual(C.PRI, "#a8ff3e")
        self.assertEqual(self.overlay._insignia_lbl.styleSheet(), f"color: {C.PRI};")

        # QR pixmap remains valid and intact
        self.assertFalse(self.overlay._qr_label.pixmap().isNull())

        # Restore default dossier theme
        apply_ui_accent("#8e9bff")
        retheme_all_widgets(new_pal, old_pal)


if __name__ == "__main__":
    unittest.main()
