"""
Unified apply path and runtime ThemeChrome provider for ALFRED-MK-VIII.
Manages live theme application, class C attribute updates, and widget notifications.
"""
from __future__ import annotations

import threading
from typing import Callable, List, Optional

from core.ui.themes.catalog import DEFAULT_BATCAVE
from core.ui.themes.registry import ThemeRegistry
from core.ui.themes.schema import ChromeDefinition, IdentityDefinition, ThemeDefinition


class ThemeChrome:
    """
    Centralized, thread-safe access point for the active theme's contextual chrome and identity strings.
    Widgets query ThemeChrome with zero performance overhead.
    """
    _lock = threading.RLock()
    _active_theme: ThemeDefinition = DEFAULT_BATCAVE
    _listeners: List[Callable[[ThemeDefinition], None]] = []

    @classmethod
    def get_active(cls) -> ThemeDefinition:
        with cls._lock:
            return cls._active_theme

    @classmethod
    def identity(cls) -> IdentityDefinition:
        with cls._lock:
            return cls._active_theme.identity

    @classmethod
    def chrome(cls) -> ChromeDefinition:
        with cls._lock:
            return cls._active_theme.chrome

    @classmethod
    def add_listener(cls, callback: Callable[[ThemeDefinition], None]) -> None:
        """Register a callback invoked whenever the theme is applied."""
        with cls._lock:
            if callback not in cls._listeners:
                cls._listeners.append(callback)

    @classmethod
    def remove_listener(cls, callback: Callable[[ThemeDefinition], None]) -> None:
        """Unregister a listener callback."""
        with cls._lock:
            if callback in cls._listeners:
                cls._listeners.remove(callback)

    @classmethod
    def _notify_listeners(cls, theme: ThemeDefinition) -> None:
        with cls._lock:
            listeners = list(cls._listeners)
        for cb in listeners:
            try:
                cb(theme)
            except Exception as e:
                print(f"[ThemeChrome] Listener error: {e}")

    @classmethod
    def set_active(cls, theme: ThemeDefinition) -> None:
        with cls._lock:
            cls._active_theme = theme
        cls._notify_listeners(theme)


def apply_theme(id_or_hex: str, notify_retheme: bool = True) -> ThemeDefinition:
    """
    Apply a theme by id or primary accent hex code.
    Updates:
      1. Class C palette attributes in ui.py
      2. _ACTIVE_THEME_ID in ui.py
      3. ThemeChrome active theme and notification listeners
      4. Qt widget stylesheets via retheme_all_widgets (if notify_retheme is True)
    """
    import ui

    theme = ThemeRegistry.instance().get(id_or_hex)
    old_palette = ui.current_palette()

    # Update class C attributes from theme palette
    for k, v in theme.palette.to_dict().items():
        if hasattr(ui.C, k):
            setattr(ui.C, k, v)

    # Set internal active theme ID
    ui._ACTIVE_THEME_ID = theme.id

    # Update ThemeChrome identity and chrome providers
    ThemeChrome.set_active(theme)

    # Update live widget stylesheets if requested
    if notify_retheme:
        new_palette = ui.current_palette()
        ui.retheme_all_widgets(old_palette, new_palette)

    return theme
