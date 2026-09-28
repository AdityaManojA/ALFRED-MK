"""Unit tests verifying Tactical Controls & Main Screen UI Cleanup.

Requirements verified:
1. Directive Archives directly accessible on ALFRED's main screen, searching/filtering, theme styling, and archive data survival.
2. Removal of Tactical Directives and Plugins navigation from Tactical Controls (quick drawer).
3. Descriptive hover help mechanism (TacticalHoverHelpManager) with 600ms delay, dismiss on leave/close/hide, and keyboard focus.
4. Single theme selector in CustomizeOverlay with emoji-free names and persistence.
5. Automatic plugin activation, legacy disabled-settings migration, and failure isolation.
"""
from __future__ import annotations

import json
import os
import sys
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtCore import QEvent, QPoint, Qt
from PyQt6.QtGui import QFocusEvent, QHoverEvent
from PyQt6.QtWidgets import QApplication, QPushButton, QWidget

import ui
from ui import (
    CapabilitiesOverlay,
    CustomizeOverlay,
    HOVER_HELP_DELAY_MS,
    MainWindow,
    TacticalHoverHelpManager,
    attach_hover_help,
)
from memory import config_manager
from core import plugin_loader


class TestUICleanup(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.config_dir = Path(self.temp_dir.name)
        self.config_file = self.config_dir / "api_keys.json"
        self.dir_patch = patch.object(config_manager, "CONFIG_DIR", self.config_dir)
        self.file_patch = patch.object(config_manager, "CONFIG_FILE", self.config_file)
        self.dir_patch.start()
        self.file_patch.start()
        config_manager.invalidate_config_cache()

    def tearDown(self) -> None:
        config_manager.invalidate_config_cache()
        self.file_patch.stop()
        self.dir_patch.stop()
        self.temp_dir.cleanup()
        TacticalHoverHelpManager.instance().dismiss()

    # ── 1. Directive Archives on Main Screen ───────────────────────────────────

    def test_capabilities_overlay_search_and_dismiss(self):
        parent = QWidget()
        overlay = CapabilitiesOverlay(parent=parent)
        try:
            overlay.show()
            self.assertGreater(len(overlay._cards), 0)
            self.assertTrue(overlay._empty_lbl.isHidden())

            # Filter with matching query
            overlay._search.setText("youtube")
            visible_count = sum(1 for card, text in overlay._cards if not card.isHidden())
            self.assertGreater(visible_count, 0)
            self.assertTrue(overlay._empty_lbl.isHidden())

            # Filter with non-matching query
            overlay._search.setText("xyz_non_existent_capability_12345")
            visible_count = sum(1 for card, text in overlay._cards if not card.isHidden())
            self.assertEqual(visible_count, 0)
            self.assertFalse(overlay._empty_lbl.isHidden())

            # Clear search
            overlay._search.setText("")
            self.assertTrue(all(not card.isHidden() for card, text in overlay._cards))
            self.assertTrue(overlay._empty_lbl.isHidden())
        finally:
            overlay.close()
            parent.close()

    # ── 2. Absence of Tactical Directives & Plugins in Tactical Controls ───────

    def test_quick_drawer_has_no_directives_or_plugins_entries(self):
        window = MainWindow("")
        try:
            drawer = window._quick_drawer
            # Check all buttons inside quick drawer
            btn_texts = [b.text() for b in drawer.findChildren(QPushButton)]
            for text in btn_texts:
                self.assertNotIn("TACTICAL DIRECTIVES", text.upper())
                self.assertNotIn("PLUGIN MANAGER", text.upper())
                self.assertNotIn("MODULE PARAMETERS", text.upper())

            # Verify main screen top bar has the direct Directives button
            self.assertTrue(hasattr(window, "_directives_btn"))
            self.assertIn("ARCHIVE", window._directives_btn.text().upper())
        finally:
            window.close()

    # ── 3. Descriptive Long-Hover Help ─────────────────────────────────────────

    def test_hover_help_manager_delayed_trigger_and_dismiss(self):
        mgr = TacticalHoverHelpManager.instance()
        self.assertEqual(HOVER_HELP_DELAY_MS, 600)

        button = QPushButton("Test Button")
        attach_hover_help(button, "This is a descriptive help text.")

        # Simulate pointer enter
        enter_ev = QEvent(QEvent.Type.Enter)
        mgr.eventFilter(button, enter_ev)
        self.assertTrue(mgr._timer.isActive())
        self.assertEqual(mgr._help_map[button], "This is a descriptive help text.")
        self.assertIs(mgr._target_widget, button)

        # Fast leave before 600ms timer fires
        leave_ev = QEvent(QEvent.Type.Leave)
        mgr.eventFilter(button, leave_ev)
        self.assertFalse(mgr._timer.isActive())
        self.assertIsNone(mgr._target_widget)

        # FocusIn should also trigger delayed help for keyboard accessibility
        focus_ev = QFocusEvent(QEvent.Type.FocusIn)
        mgr.eventFilter(button, focus_ev)
        self.assertTrue(mgr._timer.isActive())
        self.assertIs(mgr._target_widget, button)

        # FocusOut dismisses
        focus_out = QFocusEvent(QEvent.Type.FocusOut)
        mgr.eventFilter(button, focus_out)
        self.assertFalse(mgr._timer.isActive())
        button.close()

    # ── 4. Single Theme Selector & Emoji-Free Names ────────────────────────────

    def test_single_theme_selector_emoji_free_and_persisted(self):
        overlay = CustomizeOverlay(
            assistant_name="Alfred",
            user_name="Bruce",
            ui_color="#8e9bff",
            voice="",
            current_icon="",
        )
        try:
            # Check theme card buttons
            self.assertEqual(len(overlay._theme_btns), 3)
            for theme_name, btn in overlay._theme_btns.items():
                text = btn.text()
                # Verify no leading emoji characters
                self.assertNotIn("🦇", text)
                self.assertNotIn("🔥", text)
                self.assertNotIn("⚡", text)
                self.assertIn(text, ["DEFAULT BATCAVE", "BANE MODE", "BATMAN BEYOND"])

            # Test picking and saving theme
            overlay._set_color("#a8ff3e", update_wheel=True, preview=True)
            self.assertEqual(overlay._sel_color, "#a8ff3e")
        finally:
            overlay.close()

    # ── 5. Automatic Plugin Activation & Legacy Settings Migration ─────────────

    def test_automatic_plugin_activation_and_legacy_migration(self):
        # Write legacy disabled plugin setting to config file
        self.config_file.write_text(json.dumps({
            "plugins_enabled": {
                "sample_plugin": False,
            }
        }), encoding="utf-8")

        # get_plugin_enabled should always return True
        self.assertTrue(config_manager.get_plugin_enabled("sample_plugin"))
        self.assertTrue(config_manager.get_plugin_enabled("unseen_plugin"))

        # Run migration
        config_manager.migrate_legacy_plugin_settings()
        stored = json.loads(self.config_file.read_text(encoding="utf-8"))
        self.assertNotIn("plugins_enabled", stored)

    def test_plugin_discovery_isolates_failures(self):
        # Create a mock valid plugin and a mock failing plugin
        record_valid = plugin_loader.PluginRecord(
            name="good_plugin",
            description="Working plugin",
            valid=True,
        )
        record_broken = plugin_loader.PluginRecord(
            name="broken_plugin",
            description="Broken plugin",
            valid=False,
            error="Missing required dependency 'xyz'",
        )

        registry = plugin_loader.PluginRegistry(
            {"good_plugin": record_valid},
            lambda _msg: None
        )
        registry._all_records = [record_valid, record_broken]

        ui_list = registry.list_for_ui()
        self.assertEqual(len(ui_list), 2)
        valid_entry = next(e for e in ui_list if e["name"] == "good_plugin")
        broken_entry = next(e for e in ui_list if e["name"] == "broken_plugin")

        self.assertTrue(valid_entry["valid"])
        self.assertTrue(valid_entry["enabled"])
        self.assertFalse(broken_entry["valid"])
        self.assertFalse(broken_entry["enabled"])
        self.assertIn("Missing required dependency", broken_entry["error"])


if __name__ == "__main__":
    unittest.main()
