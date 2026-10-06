"""
ui/drag_handler.py — Cross-Platform Frameless Window Drag Handler and Position Manager.

Implements native compositor delegation for Wayland (via QWindow.startSystemMove)
and smooth delta-based move math for X11 (xcb), Windows, and macOS.
Manages persistent window coordinates in data/ui_state.json with top-right quadrant
defaults for first boot.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QGuiApplication, QMouseEvent, QScreen
from PyQt6.QtWidgets import QApplication, QWidget

# ── Named Constants ──────────────────────────────────────────────────────────
DRAG_THRESHOLD_PX: int = 5
MAX_HEADER_DRAG_Y_PX: int = 42
DEFAULT_TOP_RIGHT_MARGIN_X_PX: int = 24
DEFAULT_TOP_RIGHT_MARGIN_Y_PX: int = 48


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR: Path = _get_base_dir()
DATA_DIR: Path = BASE_DIR / "data"
UI_STATE_FILE: Path = DATA_DIR / "ui_state.json"
CONFIG_DIR: Path = BASE_DIR / "config"


def is_wayland() -> bool:
    """Check if the current display session is Wayland."""
    platform = (QGuiApplication.platformName() or "").lower()
    if "wayland" in platform:
        return True
    session_type = (os.environ.get("XDG_SESSION_TYPE") or "").lower()
    if session_type == "wayland":
        return True
    if bool(os.environ.get("WAYLAND_DISPLAY", "").strip()):
        return True
    return False


def is_tiling_wm() -> bool:
    """Detect if running under a known tiling window manager (i3, Sway, Hyprland, etc.)."""
    wm_env = " ".join([
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        os.environ.get("DESKTOP_SESSION", ""),
        os.environ.get("GDMSESSION", ""),
        os.environ.get("WINDOWMANAGER", ""),
    ]).lower()
    tiling_indicators = ("i3", "sway", "hyprland", "bspwm", "dwm", "awesome", "qtile", "xmonad")
    if any(t in wm_env for t in tiling_indicators):
        return True
    if "SWAYSOCK" in os.environ or "I3SOCK" in os.environ or "HYPRLAND_INSTANCE_SIGNATURE" in os.environ:
        return True
    return False


def calculate_top_right_quadrant(
    widget_w: int,
    widget_h: int,
    screen: Optional[QScreen] = None,
    margin_x: int = DEFAULT_TOP_RIGHT_MARGIN_X_PX,
    margin_y: int = DEFAULT_TOP_RIGHT_MARGIN_Y_PX,
) -> QPoint:
    """Compute default position in top-right quadrant based on available screen geometry."""
    scr = screen or QGuiApplication.primaryScreen()
    if scr is None:
        return QPoint(100, 100)
    bounds = scr.availableGeometry()
    x = max(bounds.left(), bounds.right() - widget_w - margin_x)
    y = max(bounds.top(), bounds.top() + margin_y)
    return QPoint(x, y)


def load_window_position(
    window_key: str,
    widget_w: int = 260,
    widget_h: int = 260,
    legacy_config_file: Optional[str] = None,
) -> QPoint:
    """
    Load saved window coordinates from data/ui_state.json.
    Falls back to legacy config file if present, or calculates top-right quadrant for first boot.
    """
    position: Optional[QPoint] = None

    # 1. Primary persistence: data/ui_state.json
    try:
        if UI_STATE_FILE.exists():
            data = json.loads(UI_STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and window_key in data:
                entry = data[window_key]
                if isinstance(entry, dict) and "x" in entry and "y" in entry:
                    position = QPoint(int(entry["x"]), int(entry["y"]))
    except Exception:
        pass

    # 2. Legacy fallback if primary missing
    if position is None and legacy_config_file:
        legacy_path = CONFIG_DIR / legacy_config_file
        try:
            if legacy_path.exists():
                legacy_data = json.loads(legacy_path.read_text(encoding="utf-8"))
                if isinstance(legacy_data, dict) and "x" in legacy_data and "y" in legacy_data:
                    position = QPoint(int(legacy_data["x"]), int(legacy_data["y"]))
        except Exception:
            pass

    # 3. Locate target screen and clamp or compute top-right default
    screen = QApplication.screenAt(position) if position is not None else None
    screen = screen or QApplication.primaryScreen()
    if screen is None:
        return position or QPoint(100, 100)

    bounds = screen.availableGeometry()
    if position is None:
        return calculate_top_right_quadrant(widget_w, widget_h, screen)

    # Clamp existing position inside desktop bounds
    x = max(bounds.left(), min(position.x(), bounds.right() - widget_w + 1))
    y = max(bounds.top(), min(position.y(), bounds.bottom() - widget_h + 1))
    return QPoint(x, y)


def save_window_position(window_key: str, x: int, y: int) -> None:
    """Persist window coordinates atomically to data/ui_state.json."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        data: dict = {}
        if UI_STATE_FILE.exists():
            try:
                content = json.loads(UI_STATE_FILE.read_text(encoding="utf-8"))
                if isinstance(content, dict):
                    data = content
            except Exception:
                data = {}
        data[window_key] = {"x": int(x), "y": int(y)}
        temp_file = DATA_DIR / f"{UI_STATE_FILE.name}.tmp"
        temp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temp_file.replace(UI_STATE_FILE)
    except Exception:
        pass


class CrossPlatformDragHandler:
    """
    Manages mouse drag interactions across display servers.

    On Wayland:
      Delegates window dragging to the compositor via QWindow.startSystemMove().
      This is the only permitted mechanism under Wayland xdg-shell protocol.

    On X11 (xcb), Windows (win32), and macOS (cocoa):
      Applies direct window position calculation via widget.move().
    """

    def __init__(self, threshold_px: int = DRAG_THRESHOLD_PX) -> None:
        self.threshold_px: int = threshold_px
        self._drag_start_pos: Optional[QPoint] = None
        self._drag_offset: Optional[QPoint] = None
        self._window_start_pos: Optional[QPoint] = None
        self._is_dragging: bool = False
        self._system_move_initiated: bool = False

    @property
    def is_dragging(self) -> bool:
        return self._is_dragging

    def handle_mouse_press(
        self,
        widget: QWidget,
        event: QMouseEvent,
        max_header_y: Optional[int] = None,
    ) -> bool:
        """
        Record initial click position if left button was pressed.
        Returns True if the press initiated a drag tracking sequence.
        """
        if event.button() != Qt.MouseButton.LeftButton:
            return False

        if max_header_y is not None and event.position().y() > max_header_y:
            return False

        global_pt = event.globalPosition().toPoint()
        self._drag_start_pos = global_pt
        self._window_start_pos = widget.pos()
        self._drag_offset = global_pt - widget.frameGeometry().topLeft()
        self._is_dragging = False
        self._system_move_initiated = False
        return True

    def handle_mouse_move(
        self,
        widget: QWidget,
        event: QMouseEvent,
    ) -> bool:
        """
        Process mouse move. On Wayland delegates to startSystemMove(); on X11/Win moves directly.
        Returns True if an active drag was handled.
        """
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return False

        if self._drag_start_pos is None:
            return False

        current_global = event.globalPosition().toPoint()
        dist = (current_global - self._drag_start_pos).manhattanLength()

        if not self._is_dragging and dist >= self.threshold_px:
            self._is_dragging = True

            # Wayland native compositor delegation
            if is_wayland():
                window_handle = widget.windowHandle()
                if window_handle is not None and hasattr(window_handle, "startSystemMove"):
                    self._system_move_initiated = True
                    window_handle.startSystemMove()
                    return True

        if self._is_dragging:
            if not is_wayland() or not self._system_move_initiated:
                if self._drag_offset is not None:
                    widget.move(current_global - self._drag_offset)
                elif self._window_start_pos is not None:
                    delta = current_global - self._drag_start_pos
                    widget.move(self._window_start_pos + delta)
            return True

        return False

    def handle_mouse_release(
        self,
        widget: QWidget,
        event: QMouseEvent,
    ) -> bool:
        """
        Finalize mouse release.
        Returns True if the release concluded a genuine drag gesture, or False if it was a click.
        """
        was_dragging = self._is_dragging
        self._drag_start_pos = None
        self._drag_offset = None
        self._window_start_pos = None
        self._is_dragging = False
        self._system_move_initiated = False
        return was_dragging
