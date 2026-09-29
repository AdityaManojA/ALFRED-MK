"""
core/hud/visuals/slots/two_face.py — Two-Face Theme Visual Set:
- Slot 1: Split-Mirror Scan (left half clean grid, right half corrupted seam)
- Slot 2: Rotating Silver Dollar + Probability Split (50/50 variance bar)
- Slot 3: Bisected Figure (half blueprint, half noise)
"""
from __future__ import annotations

import math
from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen

from core.hud.visuals.base import HudSignals, SlotVisual, fast_cos, fast_sin
from core.hud.visuals.primitives import BarArray
from core.ui.themes.schema import PaletteDefinition


class TwoFaceSplitMirrorVisual(SlotVisual):
    def __init__(self) -> None:
        super().__init__()
        self.pen_clean = QPen()
        self.pen_dirty = QPen()
        self.font_hdr = QFont("Consolas", 7, QFont.Weight.Bold)
        self.rect_inner = QRectF()

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        c_pri = QColor(palette.pri)
        c_acc = QColor(palette.acc)
        self.pen_clean = QPen(c_pri, 1.0)
        self.pen_dirty = QPen(c_acc, 1.2, Qt.PenStyle.DashDotLine)
        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 22.0, rect.width() - 16.0, rect.height() - 30.0
        self.rect_inner = QRectF(bx, by, bw, bh)
        mid_x = bx + bw / 2.0
        self.mid_line = QLineF(mid_x, by, mid_x, by + bh)

    def tick(self, dt: float, signals: HudSignals) -> None:
        pass

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_clean)
        painter.drawText(QRectF(rect.x() + 8, rect.y() + 4, rect.width() - 16, 14),
                         Qt.AlignmentFlag.AlignLeft, "● ● ●  SPLIT-MIRROR SCAN // DUALITY")
        painter.drawLine(self.mid_line)


class TwoFaceSilverDollarVisual(SlotVisual):
    def __init__(self) -> None:
        super().__init__()
        self.rot: float = 0.0
        self.pen_coin = QPen()
        self.font_hdr = QFont("Consolas", 6, QFont.Weight.Bold)
        self.rect_inner = QRectF()

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        c_pri = QColor(palette.pri)
        self.pen_coin = QPen(c_pri, 1.5)
        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 20.0, rect.width() - 16.0, rect.height() - 28.0
        self.rect_inner = QRectF(bx, by, bw, bh)

    def tick(self, dt: float, signals: HudSignals) -> None:
        self.rot = (self.rot + dt * 3.0) % (2.0 * math.pi)

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_coin)
        painter.drawText(QRectF(rect.x() + 8, rect.y() + 4, rect.width() - 16, 12),
                         Qt.AlignmentFlag.AlignCenter, "ROTATING SILVER DOLLAR // 50-50")
        cx = self.rect_inner.x() + self.rect_inner.width() / 2.0
        cy = self.rect_inner.y() + self.rect_inner.height() / 2.0
        w = 32.0 * abs(fast_cos(self.rot))
        painter.drawEllipse(QRectF(cx - w / 2.0, cy - 16, w, 32))


class TwoFaceBisectedVisual(SlotVisual):
    def __init__(self) -> None:
        super().__init__()
        self.pen_half = QPen()
        self.font_hdr = QFont("Consolas", 6, QFont.Weight.Bold)
        self.rect_inner = QRectF()

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        c_pri = QColor(palette.pri)
        self.pen_half = QPen(c_pri, 1.2)
        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 18.0, rect.width() - 16.0, rect.height() - 24.0
        self.rect_inner = QRectF(bx, by, bw, bh)

    def tick(self, dt: float, signals: HudSignals) -> None:
        pass

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_half)
        painter.drawText(QRectF(rect.x() + 8, rect.y() + 3, rect.width() - 16, 12),
                         Qt.AlignmentFlag.AlignCenter, "BISECTED FIGURE METRICS")
        painter.drawRect(self.rect_inner)
