"""
core/hud_video/surface.py — HudVideoSurface widget.

A QWidget that hosts QVideoWidget + on-theme loading chrome.
Sits in slot 2 of MainWindow._hud_cam_stack.

When IDLE:  invisible (stack shows HudCanvas)
When RESOLVING / LOADING:  spinner + status text in HUD palette
When PLAYING / PAUSED:  QVideoWidget fills the region
When ERROR:  brief error flash then IDLE

Theme integration: reads C.PRI, C.PRI_DIM, C.BG, C.TEXT_DIM from ui.py
class C at construction. A theme switch triggers a stylesheet refresh.
"""

from __future__ import annotations

import math
import time
import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QPushButton,
)

from .controller import HudVideoController, VideoState

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

SURFACE_SPINNER_INTERVAL_MS: int = 40   # ~25 fps spinner animation
SURFACE_MUTE_INDICATOR_TIMEOUT_MS: int = 2_000  # "MUTED" badge auto-hide


# ---------------------------------------------------------------------------
# Internal: animated spinner widget (no emoji spam, on-theme)
# ---------------------------------------------------------------------------

class _SpinnerWidget(QWidget):
    """Minimal ALFRED-style spinner: rotating arc in theme primary colour."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(56, 56)
        self._angle: float = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(SURFACE_SPINNER_INTERVAL_MS)
        self._timer.timeout.connect(self._tick)
        self._color = QColor("#00D4FF")  # refreshed on theme change

    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def set_color(self, color: QColor) -> None:
        self._color = color

    def _tick(self) -> None:
        self._angle = (self._angle + 6.0) % 360.0
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        r = min(w, h) / 2 - 4

        # Background ring
        pen = QPen(self._color.darker(250))
        pen.setWidth(3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawEllipse(
            int(w / 2 - r), int(h / 2 - r), int(r * 2), int(r * 2)
        )

        # Spinning arc
        pen.setColor(self._color)
        pen.setWidth(3)
        p.setPen(pen)
        start_angle = int(self._angle * 16)
        span_angle = int(240 * 16)
        p.drawArc(
            int(w / 2 - r), int(h / 2 - r), int(r * 2), int(r * 2),
            start_angle, span_angle,
        )
        p.end()


# ---------------------------------------------------------------------------
# HudVideoSurface
# ---------------------------------------------------------------------------

class HudVideoSurface(QWidget):
    """Replaces (via QStackedWidget) the HudCanvas during video playback.

    Layout:
        _content_stack (QStackedWidget):
            0 -> _loading_panel  (spinner + status label)
            1 -> _video_widget   (QVideoWidget — fills region when playing)
            2 -> _error_panel    (brief flash)
    """

    # Emitted when the close/stop button is clicked on the surface
    stop_requested = pyqtSignal()

    def __init__(
        self,
        controller: HudVideoController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._mute_hide_timer = QTimer(self)
        self._mute_hide_timer.setSingleShot(True)
        self._mute_hide_timer.timeout.connect(self._hide_mute_badge)

        self._build_ui()
        self._connect_controller()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def video_widget(self) -> QVideoWidget:
        """Return the QVideoWidget for the backend to attach to."""
        return self._video_widget

    def apply_theme(self, pri: str, pri_dim: str, bg: str, text_dim: str) -> None:
        """Refresh theme colours. Call when theme changes mid-playback."""
        self._pri = pri
        self._pri_dim = pri_dim
        self._bg = bg
        self._text_dim = text_dim
        self._spinner.set_color(QColor(pri))
        self._apply_stylesheet()

    # ------------------------------------------------------------------
    # Controller signal handlers
    # ------------------------------------------------------------------

    def _on_state_changed(self, state: VideoState) -> None:
        if state == VideoState.RESOLVING:
            self._spinner.start()
            self._content_stack.setCurrentIndex(0)  # loading panel
            self._status_lbl.setText("RESOLVING…")
            self._close_btn.show()
        elif state == VideoState.LOADING:
            self._spinner.start()
            self._content_stack.setCurrentIndex(0)
            self._close_btn.show()
        elif state == VideoState.PLAYING:
            self._spinner.stop()
            self._content_stack.setCurrentIndex(1)  # video widget
            self._close_btn.show()
            self._pause_overlay.hide()
            log.info("[hud_video] embed loaded, player visible")

        elif state == VideoState.PAUSED:
            self._content_stack.setCurrentIndex(1)
            self._pause_overlay.show()
            self._close_btn.show()
        elif state == VideoState.ERROR:
            self._spinner.stop()
            self._content_stack.setCurrentIndex(2)  # error panel
            self._close_btn.show()
        elif state == VideoState.IDLE:
            self._spinner.stop()
            self._pause_overlay.hide()

    def _on_status_text(self, text: str) -> None:
        self._status_lbl.setText(text.upper())
        self._error_lbl.setText(text.upper())

    # ------------------------------------------------------------------
    # UI build
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Default palette (overridden by apply_theme)
        self._pri = "#00D4FF"
        self._pri_dim = "#007A9A"
        self._bg = "#000308"
        self._text_dim = "#405060"

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header bar with title + close button
        header = self._build_header()
        root.addLayout(header)

        # Inner content stack
        self._content_stack = QStackedWidget()
        self._content_stack.addWidget(self._build_loading_panel())   # 0
        self._content_stack.addWidget(self._build_video_panel())     # 1
        self._content_stack.addWidget(self._build_error_panel())     # 2
        self._content_stack.setCurrentIndex(0)
        root.addWidget(self._content_stack, stretch=1)

        # Mute indicator badge (absolute position over content_stack)
        self._mute_badge = QLabel("MUTED", self)
        self._mute_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._mute_badge.hide()

        # Pause overlay label (absolute position)
        self._pause_overlay = QLabel("⏸  PAUSED", self)
        self._pause_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pause_overlay.hide()

        self._apply_stylesheet()

    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(10, 5, 10, 5)
        row.setSpacing(6)

        self._title_lbl = QLabel("◈  HUD PLAYER")
        self._title_lbl.setFont(self._tech_font(8, bold=True))

        self._close_btn = QPushButton("✕  CLOSE")
        self._close_btn.setFont(self._tech_font(8))
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setFlat(True)
        self._close_btn.clicked.connect(self.stop_requested.emit)
        self._close_btn.hide()

        row.addWidget(self._title_lbl)
        row.addStretch()
        row.addWidget(self._close_btn)
        return row

    def _build_loading_panel(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.setSpacing(12)

        self._spinner = _SpinnerWidget()
        self._status_lbl = QLabel("LOADING…")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_lbl.setFont(self._tech_font(9, bold=True))
        self._status_lbl.setWordWrap(True)

        v.addWidget(self._spinner, alignment=Qt.AlignmentFlag.AlignHCenter)
        v.addWidget(self._status_lbl)
        return w

    def _build_video_panel(self) -> QWidget:
        self._video_widget = QVideoWidget()
        self._video_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._video_widget.setStyleSheet("background: #000000;")
        return self._video_widget

    def _build_error_panel(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_lbl = QLabel("ERROR")
        self._error_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_lbl.setFont(self._tech_font(10, bold=True))
        self._error_lbl.setWordWrap(True)
        v.addWidget(self._error_lbl)
        return w

    def _connect_controller(self) -> None:
        self._controller.state_changed.connect(self._on_state_changed)
        self._controller.status_text_changed.connect(self._on_status_text)

    def _apply_stylesheet(self) -> None:
        pri = self._pri
        pri_dim = self._pri_dim
        bg = self._bg
        dim = self._text_dim

        self.setStyleSheet(f"""
            HudVideoSurface {{
                background: {bg};
                border: 1px solid {pri_dim};
            }}
        """)
        self._title_lbl.setStyleSheet(
            f"color: {pri}; background: transparent;"
            f" letter-spacing: 2px;"
        )
        self._close_btn.setStyleSheet(f"""
            QPushButton {{
                color: {dim}; background: transparent; border: none; padding: 2px 8px;
            }}
            QPushButton:hover {{ color: {pri}; }}
        """)
        self._status_lbl.setStyleSheet(
            f"color: {pri}; background: transparent;"
            f" letter-spacing: 1px;"
        )
        self._error_lbl.setStyleSheet(
            f"color: #FF4444; background: transparent;"
            f" letter-spacing: 2px;"
        )
        self._mute_badge.setStyleSheet(f"""
            QLabel {{
                color: {bg}; background: {pri};
                border-radius: 3px; padding: 2px 10px;
                font-size: 8pt; letter-spacing: 2px;
            }}
        """)
        self._pause_overlay.setStyleSheet(f"""
            QLabel {{
                color: {pri}; background: rgba(0,0,0,0.55);
                border-radius: 4px; padding: 4px 14px;
                font-size: 11pt; letter-spacing: 3px;
            }}
        """)

    @staticmethod
    def _tech_font(size: int, bold: bool = False) -> QFont:
        """Return a monospaced tech font matching HUD style."""
        try:
            from ui import tech_font  # type: ignore[import]
            w = QFont.Weight.Bold if bold else QFont.Weight.Normal
            return tech_font(size, w)
        except Exception:
            f = QFont("Courier New", size)
            if bold:
                f.setBold(True)
            return f

    def _hide_mute_badge(self) -> None:
        self._mute_badge.hide()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Keep mute badge top-right and pause overlay centred
        if hasattr(self, "_mute_badge"):
            bw, bh = 80, 22
            self._mute_badge.setGeometry(self.width() - bw - 8, 36, bw, bh)
        if hasattr(self, "_pause_overlay"):
            pw, ph = 160, 36
            self._pause_overlay.setGeometry(
                (self.width() - pw) // 2,
                (self.height() - ph) // 2,
                pw, ph,
            )
