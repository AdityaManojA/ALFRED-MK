"""Behavioural tests for core.ui.themes.registry.ThemeRegistry."""
import dataclasses

import pytest

from core.ui.themes import registry as registry_mod
from core.ui.themes.catalog import ALL_THEMES, DEFAULT_BATCAVE
from core.ui.themes.registry import ThemeRegistry


@pytest.fixture
def reg():
    return ThemeRegistry()


def test_registers_all_catalog_themes_in_order(reg):
    assert [t.id for t in reg.list_themes()] == [t.id for t in ALL_THEMES]


def test_list_themes_returns_copy(reg):
    lst = reg.list_themes()
    lst.clear()
    assert len(reg.list_themes()) == len(ALL_THEMES)


def test_get_by_id_normalises_case_and_whitespace(reg):
    assert reg.get_by_id("  JOKER ").id == "joker"
    assert reg.get_by_id("nope") is None
    assert reg.get_by_id(None) is None


def test_get_by_hex(reg):
    assert reg.get_by_hex("#A8FF3E").id == "vector"
    assert reg.get_by_hex("#000000") is None
    assert reg.get_by_hex("") is None


@pytest.mark.parametrize("key, expected", [
    ("riddler", "riddler"),
    ("#00E676", "riddler"),
    ("  mr_freeze ", "mr_freeze"),
    ("unknown-theme", "dossier"),
    ("", "dossier"),
    (None, "dossier"),
])
def test_get_universal_lookup_with_fallback(reg, key, expected):
    assert reg.get(key).id == expected


def test_get_unknown_returns_default_object(reg):
    assert reg.get("zzz") is DEFAULT_BATCAVE


def test_legacy_alias_resolves_when_hex_not_registered():
    reg = ThemeRegistry.__new__(ThemeRegistry)
    reg._by_id, reg._by_hex, reg._order = {}, {}, []
    beyond = next(t for t in ALL_THEMES if t.id == "beyond")
    # register under a different hex so only the alias path can find it
    reg.register(dataclasses.replace(beyond, hex="#123456"))
    assert reg.get("#ff0037").id == "beyond"


def test_register_rejects_duplicate_id(reg):
    dup = dataclasses.replace(DEFAULT_BATCAVE, id=" DOSSIER ", hex="#abcdef")
    with pytest.raises(ValueError, match="Duplicate theme id"):
        reg.register(dup)


def test_register_rejects_emoji_display_name(reg):
    bad = dataclasses.replace(DEFAULT_BATCAVE, id="emoji_theme", display_name="Bat \U0001F987")
    with pytest.raises(ValueError, match="emoji"):
        reg.register(bad)
    assert reg.get_by_id("emoji_theme") is None


def test_register_new_theme_is_findable(reg):
    new = dataclasses.replace(DEFAULT_BATCAVE, id="Custom", hex="#ABCDEF", display_name="Custom")
    reg.register(new)
    assert reg.get("custom") is new
    assert reg.get("#abcdef") is new
    assert reg.list_themes()[-1] is new


def test_instance_is_singleton(monkeypatch):
    monkeypatch.setattr(ThemeRegistry, "_instance", None)
    a = ThemeRegistry.instance()
    assert ThemeRegistry.instance() is a


def test_emoji_pattern_allows_plain_text():
    assert registry_mod._EMOJI_PATTERN.search("Batcave // Default") is None
    assert registry_mod._EMOJI_PATTERN.search("Sun ☀") is not None
