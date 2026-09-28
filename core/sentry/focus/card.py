"""Floating Desktop Countdown Card for Sentry Focus Mode.

Unobtrusive floating card with cyan progress bar/ring, mm:ss countdown,
drift warning glow, drag repositioning, and quick actions context menu.
"""
from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import Qt, QPoint, QRectF
from PyQt6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QBrush,
    QFont,
    QPaintEvent,
    QMouseEvent,
    QContextMenuEvent,
)
from PyQt6.QtWidgets import QWidget, QMenu, QApplication

from core.sentry.focus.state import FocusState
from core.sentry.focus.engine import get_focus_engine

_LOGGER = logging.getLogger(__name__)


class FloatingFocusCard(QWidget):
    """Semi-transparent, always-on-top draggable countdown card for Focus Mode."""

    WIDTH = 170
    HEIGHT = 48

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self.setObjectName("floatingFocusCard")

        # Dragging state
        self._dragging = False
        self._drag_start_pos = QPoint()

        # Cached display state (no per-frame allocations in paintEvent)
        self._active = False
        self._paused = False
        self._drifting = False
        self._remaining_s = 0
        self._planned_s = 1
        self._countdown_text = "00:00"
        self._progress = 1.0

        # Pre-cached styling objects
        self._font_countdown = QFont("Consolas", 12, QFont.Weight.Bold)
        self._font_small = QFont("Segoe UI", 7, QFont.Weight.Bold)

        self._bg_color = QColor(10, 16, 26, 225)
        self._border_pen_normal = QPen(QColor(0, 240, 255, 120), 1.5)
        self._border_pen_drift = QPen(QColor(255, 50, 75, 230), 2.0)
        self._progress_pen = QPen(QColor(0, 240, 255, 220), 3.0)
        self._progress_bg_pen = QPen(QColor(0, 80, 100, 80), 3.0)
        self._text_color = QColor(240, 248, 255)
        self._drift_text_color = QColor(255, 80, 100)
        self._paused_text_color = QColor(255, 200, 60)

        self.hide()

    def update_state(self, state: FocusState) -> None:
        """Update display values from FocusState."""
        if not state.active:
            if self.isVisible():
                self.hide()
            self._active = False
            return

        self._active = True
        self._paused = state.paused
        self._drifting = state.drifting
        self._remaining_s = max(0, state.remaining_s)
        self._planned_s = max(1, state.planned_s)

        mins = self._remaining_s // 60
        secs = self._remaining_s % 60
        self._countdown_text = f"{mins:02d}:{secs:02d}"
        self._progress = max(0.0, min(1.0, self._remaining_s / self._planned_s))

        if not self.isVisible():
            self.show()

        self.update()

    def clamp_to_screen(self, pos: QPoint) -> QPoint:
        """Ensure card stays completely within desktop screen boundaries."""
        screen = QApplication.primaryScreen()
        if not screen:
            return pos
        geom = screen.availableGeometry()

        x = max(geom.left(), min(pos.x(), geom.right() - self.width()))
        y = max(geom.top(), min(pos.y(), geom.bottom() - self.height()))
        return QPoint(x, y)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_start_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging and event.buttons() & Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self._drag_start_pos
            clamped = self.clamp_to_screen(new_pos)
            self.move(clamped)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            event.accept()

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        engine = get_focus_engine()
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: rgba(10, 16, 26, 240);
                color: #e0f0ff;
                border: 1px solid rgba(0, 240, 255, 120);
                padding: 4px;
            }
            QMenu::item:selected {
                background: rgba(0, 240, 255, 40);
                color: #ffffff;
            }
        """)

        act_snooze = menu.addAction("Snooze (15s)")
        act_lock_tab = menu.addAction("Lock on this tab")
        act_extend = menu.addAction("Extend (+10m)")
        act_excuse = menu.addAction("Excuse (Research)")
        menu.addSeparator()
        if self._paused:
            act_toggle_pause = menu.addAction("Resume")
        else:
            act_toggle_pause = menu.addAction("Pause")
        act_end = menu.addAction("End session")

        action = menu.exec(event.globalPos())
        if action == act_snooze:
            engine.snooze(15)
        elif action == act_lock_tab:
            engine.lock_current_surface(from_card=True)
        elif action == act_extend:
            engine.extend(10)
        elif action == act_excuse:
            engine.excuse("Research")
        elif action == act_toggle_pause:
            if self._paused:
                engine.resume()
            else:
                engine.pause()
        elif action == act_end:
            engine.abort("Ended from focus card")

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background rounded rect
        rect = QRectF(1.0, 1.0, float(self.width() - 2), float(self.height() - 2))
        painter.setBrush(QBrush(self._bg_color))
        painter.setPen(self._border_pen_drift if self._drifting else self._border_pen_normal)
        painter.drawRoundedRect(rect, 8.0, 8.0)

        # Progress Arc (left-hand ring)
        ring_rect = QRectF(10.0, 8.0, 32.0, 32.0)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(self._progress_bg_pen)
        painter.drawEllipse(ring_rect)

        # Progress fraction (sweep angle in 16ths of a degree)
        span_angle = int(-self._progress * 360 * 16)
        painter.setPen(self._progress_pen)
        painter.drawArc(ring_rect, 90 * 16, span_angle)

        # Play / Pause glyph in center of ring
        painter.setFont(self._font_small)
        painter.setPen(self._paused_text_color if self._paused else self._text_color)
        glyph = "||" if not self._paused else ">"
        painter.drawText(ring_rect, Qt.AlignmentFlag.AlignCenter, glyph)

        # Text Section: Status label + mm:ss countdown
        painter.setFont(self._font_small)
        painter.setPen(QColor(0, 240, 255, 180) if not self._drifting else self._drift_text_color)
        status_label = "DRIFTING" if self._drifting else ("PAUSED" if self._paused else "FOCUS")
        painter.drawText(QRectF(50.0, 8.0, 110.0, 14.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, status_label)

        painter.setFont(self._font_countdown)
        painter.setPen(self._drift_text_color if self._drifting else self._text_color)
        painter.drawText(QRectF(50.0, 22.0, 110.0, 20.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._countdown_text)
