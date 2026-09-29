"""
core/hud_video/layering.py — Visual HUD Layering, Z-order, and overlay elevation coordination.

Enforces:
- Single source of truth for Z_* constants:
  Z_VISUAL_HUD < Z_HUD_BUTTONS < Z_DROPDOWN_CARD_TOAST < Z_SETTINGS_MODAL
- raise_overlay(widget) helper used across panels
- Frameless top-level ownership configuration to solve native QVideoWidget airspace occlusion
"""

from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtWidgets import QWidget

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named Z-Order Constants
# ---------------------------------------------------------------------------

Z_VISUAL_HUD: int = 10
Z_HUD_BUTTONS: int = 20
Z_DROPDOWN_CARD_TOAST: int = 30
Z_SETTINGS_MODAL: int = 40


# ---------------------------------------------------------------------------
# Layering Helpers
# ---------------------------------------------------------------------------

def make_frameless_overlay(widget: QWidget, parent: Optional[QWidget] = None) -> None:
    """Configure a widget as a frameless top-level window owned by parent.

    A native QVideoWidget HWND occludes non-native child widgets of the same
    window. Making the overlay a frameless window (Qt.WindowType.Tool) owned by
    the MainWindow creates an independent Win32 HWND that the Desktop Window
    Manager (DWM) paints cleanly above the native video surface.
    """
    if parent is not None:
        widget.setParent(parent)
    widget.setWindowFlags(
        Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.Tool
    )
    widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)


def raise_overlay(widget: QWidget, parent: Optional[QWidget] = None) -> None:
    """Raise an overlay widget above the Visual HUD and sibling elements.

    Safe for both top-level Tool overlays and child widgets.
    """
    if widget is None:
        return
    try:
        if parent is not None and widget.parent() is None:
            widget.setParent(parent)
        widget.show()
        widget.raise_()
    except Exception as exc:
        log.debug("[Layering] raise_overlay error: %s", exc)


def centre_overlay_globally(widget: QWidget, anchor_widget: QWidget) -> None:
    """Centre a top-level overlay over an anchor widget using global coordinates."""
    if widget is None or anchor_widget is None:
        return
    widget.adjustSize()
    w = widget.width()
    h = widget.height()
    aw = anchor_widget.width()
    ah = anchor_widget.height()

    target_local_x = max(0, (aw - w) // 2)
    target_local_y = max(0, (ah - h) // 2)

    global_pos = anchor_widget.mapToGlobal(QPoint(target_local_x, target_local_y))
    widget.move(global_pos)
    raise_overlay(widget, anchor_widget.window())
