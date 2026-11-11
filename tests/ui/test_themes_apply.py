"""Behavioural tests for core.ui.themes.apply (ThemeChrome + apply_theme)."""
import sys
import types

import pytest

from core.ui.themes import apply as apply_mod
from core.ui.themes.apply import ThemeChrome, apply_theme
from core.ui.themes.catalog import ALL_THEMES, DEFAULT_BATCAVE


@pytest.fixture(autouse=True)
def _restore_chrome_state():
    saved_theme = ThemeChrome._active_theme
    saved_listeners = list(ThemeChrome._listeners)
    yield
    ThemeChrome._active_theme = saved_theme
    ThemeChrome._listeners[:] = saved_listeners


@pytest.fixture
def fake_ui(monkeypatch):
    """Stand-in for the top-level `ui` module so no real widgets are touched."""
    mod = types.ModuleType("ui")

    class C:
        PRI = "#000000"
        BG = "#111111"
        NOT_A_PALETTE_KEY = "keep"

    mod.C = C
    mod._ACTIVE_THEME_ID = "dossier"
    mod.current_palette = lambda: {"PRI": C.PRI, "BG": C.BG}
    mod.retheme_calls = []
    mod.retheme_all_widgets = lambda old, new: mod.retheme_calls.append((old, new))
    monkeypatch.setitem(sys.modules, "ui", mod)
    return mod


def _theme(theme_id):
    return next(t for t in ALL_THEMES if t.id == theme_id)


def test_accessors_reflect_active_theme():
    joker = _theme("joker")
    ThemeChrome.set_active(joker)
    assert ThemeChrome.get_active() is joker
    assert ThemeChrome.identity() is joker.identity
    assert ThemeChrome.chrome() is joker.chrome


def test_listeners_notified_and_deduplicated():
    seen = []
    cb = seen.append
    ThemeChrome.add_listener(cb)
    ThemeChrome.add_listener(cb)  # duplicate ignored
    ThemeChrome.set_active(_theme("arkham"))
    assert [t.id for t in seen] == ["arkham"]
    ThemeChrome.remove_listener(cb)
    ThemeChrome.remove_listener(cb)  # removing twice is harmless
    ThemeChrome.set_active(_theme("riddler"))
    assert len(seen) == 1


def test_failing_listener_does_not_block_others(capsys):
    seen = []

    def boom(_theme):
        raise RuntimeError("kaboom")

    ThemeChrome.add_listener(boom)
    ThemeChrome.add_listener(seen.append)
    ThemeChrome.set_active(DEFAULT_BATCAVE)
    assert seen == [DEFAULT_BATCAVE]
    assert "kaboom" in capsys.readouterr().out


def test_apply_theme_updates_ui_and_chrome(fake_ui):
    riddler = _theme("riddler")
    result = apply_theme("RIDDLER")
    assert result is riddler
    assert fake_ui.C.PRI == riddler.palette.pri
    assert fake_ui.C.BG == riddler.palette.bg
    assert fake_ui.C.NOT_A_PALETTE_KEY == "keep"
    # only existing attributes are set, palette keys absent on C are not added
    assert not hasattr(fake_ui.C, "ACC2")
    assert fake_ui._ACTIVE_THEME_ID == "riddler"
    assert ThemeChrome.get_active() is riddler
    assert fake_ui.retheme_calls == [
        ({"PRI": "#000000", "BG": "#111111"}, {"PRI": riddler.palette.pri, "BG": riddler.palette.bg})
    ]


def test_apply_theme_by_hex_without_retheme(fake_ui):
    result = apply_theme("#a8ff3e", notify_retheme=False)
    assert result.id == "vector"
    assert fake_ui.retheme_calls == []
    assert fake_ui._ACTIVE_THEME_ID == "vector"


def test_apply_theme_unknown_falls_back_to_default(fake_ui):
    assert apply_theme("not-a-theme") is DEFAULT_BATCAVE
    assert fake_ui._ACTIVE_THEME_ID == DEFAULT_BATCAVE.id
