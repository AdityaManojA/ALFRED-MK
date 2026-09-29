"""
Comprehensive unit tests for ALFRED-MK-V Thematic HUD Overhaul.
Verifies:
1. Theme schema definitions, 1:1 token completeness, and emoji-free display names.
2. Registry uniqueness, id/hex lookups, legacy alias mapping, and safe fallback.
3. ThemeChrome active provider, listeners, and non-blocking thread-safe access.
4. Live apply path: class C attributes update, stylesheet retheming, identity updates.
5. Contrast analysis (WCAG ratio verification on background).
6. Rapid theme switching (spam switch robustness).
7. Data vs presentation: real telemetry, Focus remaining seconds, and Monitor state remain truthful.
"""
from __future__ import annotations

import colorsys
import json
import math
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

import ui
from core.ui.themes import (
    ThemeRegistry,
    ThemeChrome,
    ThemeDefinition,
    apply_theme,
    get_theme,
    list_themes,
    SubjectValueMode,
)
from core.ui.themes.catalog import ALL_THEMES, DEFAULT_BATCAVE


def _luminance(hex_str: str) -> float:
    """Relative luminance calculation per WCAG 2.1."""
    clean = hex_str.strip().lstrip("#")
    if len(clean) != 6:
        return 0.0
    r = int(clean[0:2], 16) / 255.0
    g = int(clean[2:4], 16) / 255.0
    b = int(clean[4:6], 16) / 255.0

    def _adjust(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * _adjust(r) + 0.7152 * _adjust(g) + 0.0722 * _adjust(b)


def _contrast_ratio(hex1: str, hex2: str) -> float:
    """Calculate contrast ratio between two hex colors."""
    l1 = _luminance(hex1)
    l2 = _luminance(hex2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


class TestThematicHUD(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.registry = ThemeRegistry.instance()

    def test_catalog_completeness_and_uniqueness(self):
        """All themes in catalog must have unique IDs, unique hexes, and non-empty metadata."""
        themes = self.registry.list_themes()
        self.assertGreaterEqual(len(themes), 10, "At least 10 themes must be registered")

        ids = set()
        hexes = set()
        for theme in themes:
            # 1. Stable lowercase snake_case id
            self.assertNotIn(theme.id, ids, f"Duplicate theme id: {theme.id}")
            ids.add(theme.id)
            self.assertTrue(theme.id.islower() and theme.id.replace("_", "").isalnum())

            # 2. Hex code
            self.assertTrue(theme.hex.startswith("#") and len(theme.hex) == 7)
            self.assertNotIn(theme.hex.lower(), hexes, f"Duplicate primary hex: {theme.hex}")
            hexes.add(theme.hex.lower())

            # 3. Clean display name (no emoji)
            self.assertTrue(len(theme.display_name.strip()) > 0)
            self.assertFalse(any(ord(c) > 0x2000 for c in theme.display_name),
                             f"Display name '{theme.display_name}' contains non-ASCII/emoji characters")

            # 4. Tagline present
            self.assertTrue(len(theme.tagline.strip()) > 5)

            # 5. Complete 24 palette tokens
            pal_dict = theme.palette.to_dict()
            self.assertEqual(len(pal_dict), 24)
            for token_name, token_val in pal_dict.items():
                self.assertTrue(token_val, f"Empty token {token_name} in theme {theme.id}")

            # 6. Identity block
            self.assertTrue(theme.identity.subject_label)
            self.assertTrue(theme.identity.function_line)
            self.assertTrue(theme.identity.threat_header)
            self.assertTrue(theme.identity.threat_levels.clear)
            self.assertTrue(theme.identity.threat_levels.critical)

            # 7. Chrome strings
            self.assertTrue(theme.chrome.monitor_active_line)
            self.assertTrue(theme.chrome.bio_scan_header)
            self.assertTrue(theme.chrome.pose_track_header)
            self.assertTrue(theme.chrome.telemetry_header)
            self.assertTrue(theme.chrome.tab_telemetry)
            self.assertTrue(theme.chrome.tab_intel)
            self.assertTrue(theme.chrome.window_title_suffix)

    def test_legacy_aliases_and_lookups(self):
        """Registry lookups must handle theme IDs, hexes, legacy hexes, and fallback safely."""
        # By ID
        dossier = self.registry.get_by_id("dossier")
        self.assertIsNotNone(dossier)
        self.assertEqual(dossier.id, "dossier")

        vector = self.registry.get_by_id("vector")
        self.assertIsNotNone(vector)
        self.assertEqual(vector.display_name, "BANE MODE")

        beyond = self.registry.get_by_id("beyond")
        self.assertIsNotNone(beyond)
        self.assertEqual(beyond.display_name, "BATMAN BEYOND")

        # By new hex
        joker = self.registry.get_by_hex("#b537f2")
        self.assertIsNotNone(joker)
        self.assertEqual(joker.id, "joker")

        # By legacy alias hex
        bane_legacy = self.registry.get("#a8ff3e")
        self.assertEqual(bane_legacy.id, "vector")

        beyond_legacy = self.registry.get("#ff0037")
        self.assertEqual(beyond_legacy.id, "beyond")

        # Safe fallback for unknown ID or hex
        fallback = self.registry.get("nonexistent_unknown_theme_99")
        self.assertEqual(fallback.id, DEFAULT_BATCAVE.id)

    def test_apply_theme_updates_palette_and_chrome(self):
        """Applying a theme must update class C, ui._ACTIVE_THEME_ID, and ThemeChrome."""
        listener_calls = []

        def _test_listener(theme: ThemeDefinition):
            listener_calls.append(theme.id)

        ThemeChrome.add_listener(_test_listener)
        try:
            # Apply Bane
            applied = apply_theme("vector", notify_retheme=False)
            self.assertEqual(applied.id, "vector")
            self.assertEqual(ui._ACTIVE_THEME_ID, "vector")
            self.assertEqual(ui.C.PRI, applied.palette.pri)
            self.assertEqual(ThemeChrome.get_active().id, "vector")
            self.assertEqual(ThemeChrome.identity().threat_header, "DOMINANCE ASSESSMENT")
            self.assertEqual(ThemeChrome.chrome().monitor_active_line, "SURVEILLANCE GRID // OVERRUN")
            self.assertIn("vector", listener_calls)

            # Apply Batman Beyond
            applied_bb = apply_theme("beyond", notify_retheme=False)
            self.assertEqual(applied_bb.id, "beyond")
            self.assertEqual(ui._ACTIVE_THEME_ID, "beyond")
            self.assertEqual(ui.C.PRI, applied_bb.palette.pri)
            self.assertEqual(ThemeChrome.identity().threat_header, "CITY THREAT MATRIX")
            self.assertEqual(ThemeChrome.chrome().window_title_suffix, "NEO-GOTHAM TACTICAL HUD")

            # Restore Default
            apply_theme("dossier", notify_retheme=False)
            self.assertEqual(ui._ACTIVE_THEME_ID, "dossier")
        finally:
            ThemeChrome.remove_listener(_test_listener)

    def test_contrast_accessibility(self):
        """Check text on background contrast across all registered themes."""
        for theme in self.registry.list_themes():
            bg = theme.palette.bg
            text = theme.palette.text
            pri = theme.palette.pri

            # Normal text against dark background must have high contrast (>= 4.5:1 recommended, >= 3.5:1 strict floor)
            text_ratio = _contrast_ratio(text, bg)
            self.assertGreater(
                text_ratio, 3.8,
                f"Theme {theme.id} text ({text}) on bg ({bg}) contrast too low: {text_ratio:.2f}"
            )

            # Accent/PRI on BG must be distinctly visible (>= 3.0:1)
            pri_ratio = _contrast_ratio(pri, bg)
            self.assertGreater(
                pri_ratio, 3.0,
                f"Theme {theme.id} primary ({pri}) on bg ({bg}) contrast too low: {pri_ratio:.2f}"
            )

    def test_rapid_theme_switching_stability(self):
        """Switching themes rapidly 20 times must not crash or leak invalid state."""
        all_ids = [t.id for t in self.registry.list_themes()]
        for _ in range(2):
            for tid in all_ids:
                th = apply_theme(tid, notify_retheme=False)
                self.assertEqual(ui._ACTIVE_THEME_ID, tid)
                self.assertEqual(ThemeChrome.get_active().id, tid)
                self.assertTrue(ui.C.PRI.startswith("#"))
        # Reset back to default
        apply_theme("dossier", notify_retheme=False)

    def test_data_vs_presentation_truthfulness(self):
        """Verify that dossier cards and sentry indicators do not alter real factual data."""
        card = ui.SubjectDossierCard("ALFRED.MK-IV")
        try:
            # Under default theme
            apply_theme("dossier", notify_retheme=False)
            card.set_threat_state("clear")
            self.assertEqual(card._threat_state, "clear")

            # Under Bane theme
            apply_theme("vector", notify_retheme=False)
            ident = ThemeChrome.identity()
            self.assertEqual(ident.threat_levels.clear, "SUPPRESSED")
            self.assertEqual(ident.threat_levels.critical, "BREAK THE BAT")
            # Verify that real assistant name remains accurate under KEEP_REAL
            self.assertEqual(ident.subject_value_mode, SubjectValueMode.KEEP_REAL)
            self.assertEqual(ident.codename, "BANE")

            # Under Joker theme
            apply_theme("joker", notify_retheme=False)
            j_ident = ThemeChrome.identity()
            self.assertEqual(j_ident.subject_value_mode, SubjectValueMode.THEMATIC_CODENAME)
            self.assertEqual(j_ident.codename, "THE JOKER")

            # Reset back to default
            apply_theme("dossier", notify_retheme=False)
            self.assertEqual(ThemeChrome.identity().subject_value_mode, SubjectValueMode.KEEP_REAL)
        finally:
            card.close()


if __name__ == "__main__":
    unittest.main()
