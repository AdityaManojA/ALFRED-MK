"""
Registry for ALFRED-MK-VIII themes.
Provides lookup, validation, and listing of all registered themes.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from core.ui.themes.catalog import ALL_THEMES, DEFAULT_BATCAVE
from core.ui.themes.schema import ThemeDefinition

# Regex pattern to disallow emojis in theme display names
_EMOJI_PATTERN = re.compile(
    r"[\U00010000-\U0010ffff"
    r"\u2600-\u26ff"
    r"\u2700-\u27bf"
    r"\U0001f300-\U0001f5ff"
    r"\U0001f600-\U0001f64f"
    r"\U0001f680-\U0001f6ff"
    r"\U0001f1e0-\U0001f1ff]"
)


class ThemeRegistry:
    """Singleton registry holding all active ThemeDefinitions."""

    _instance: Optional[ThemeRegistry] = None

    @classmethod
    def instance(cls) -> ThemeRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._by_id: Dict[str, ThemeDefinition] = {}
        self._by_hex: Dict[str, ThemeDefinition] = {}
        self._order: List[ThemeDefinition] = []

        for theme in ALL_THEMES:
            self.register(theme)

    def register(self, theme: ThemeDefinition) -> None:
        """Register a ThemeDefinition and enforce naming/structure validation."""
        tid = theme.id.strip().lower()
        if tid in self._by_id:
            raise ValueError(f"Duplicate theme id: {theme.id}")

        if _EMOJI_PATTERN.search(theme.display_name):
            raise ValueError(
                f"Theme display_name '{theme.display_name}' contains emoji characters. "
                "Display names must be clean text per ground rules."
            )

        self._by_id[tid] = theme
        self._by_hex[theme.hex.strip().lower()] = theme
        self._order.append(theme)

    def get_by_id(self, theme_id: str) -> Optional[ThemeDefinition]:
        """Look up theme by stable id (e.g. 'dossier', 'vector', 'beyond', 'joker')."""
        return self._by_id.get((theme_id or "").strip().lower())

    def get_by_hex(self, hex_code: str) -> Optional[ThemeDefinition]:
        """Look up theme by exact primary accent hex (e.g. '#8e9bff', '#a8ff3e')."""
        return self._by_hex.get((hex_code or "").strip().lower())

    LEGACY_ALIASES: Dict[str, str] = {
        "#a8ff3e": "vector",
        "#ff0037": "beyond",
        "#8e9bff": "dossier",
    }

    def get(self, id_or_hex: str) -> ThemeDefinition:
        """
        Universal lookup: attempts id match, then hex match, falling back to DEFAULT_BATCAVE.
        Guarantees never returning None.
        """
        clean = (id_or_hex or "").strip().lower()
        if clean in self._by_id:
            return self._by_id[clean]
        if clean in self._by_hex:
            return self._by_hex[clean]
        if clean in self.LEGACY_ALIASES:
            aliased = self.get_by_id(self.LEGACY_ALIASES[clean])
            if aliased:
                return aliased

        # Check for partial hex match if formatted as #RRGGBB
        for theme in self._order:
            if theme.hex.lower() == clean:
                return theme

        # Safe fallback
        return DEFAULT_BATCAVE

    def list_themes(self) -> List[ThemeDefinition]:
        """Return all registered themes in display order."""
        return list(self._order)
