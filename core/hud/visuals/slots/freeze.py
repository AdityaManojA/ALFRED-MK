"""
core/hud/visuals/slots/freeze.py — Mr. Freeze Theme Visual Set:
- Slot 1: Cryogenic Core Lattice (hex snowflake grid growing/refracting with thermal delta)
- Slot 2: Thermal Delta Column (freeze-point gauge, frost creep at edges)
- Slot 3: Cryo-Suit Coolant Loop (schematic with circulating coolant pulses)
"""
from __future__ import annotations

import math
from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen

from core.hud.visuals.base import HudSignals, SlotVisual, fast_cos, fast_sin
from core.ui.themes.schema import PaletteDefinition


class FreezeCoreLatticeVisual(SlotVisual):
    def __init__(self) -> None:
        super().__init__()
        self.rot: float = 0.0
        self.pen_ice = QPen()
        self.font_hdr = QFont("Consolas", 7, QFont.Weight.Bold)
        self.rect_inner = QRectF()
        self.spokes = [QLineF() for _ in range(6)]

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        c_pri = QColor(palette.pri)
        self.pen_ice = QPen(c_pri, 1.4)
        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 22.0, rect.width() - 16.0, rect.height() - 30.0
        self.rect_inner = QRectF(bx, by, bw, bh)

    def tick(self, dt: float, signals: HudSignals) -> None:
        self.rot = (self.rot + dt * 0.5) % (2.0 * math.pi)
        cx = self.rect_inner.x() + self.rect_inner.width() / 2.0
        cy = self.rect_inner.y() + self.rect_inner.height() / 2.0
        r = min(self.rect_inner.width(), self.rect_inner.height()) * 0.35
        for i in range(6):
            ang = self.rot + (i * math.pi / 3.0)
            self.spokes[i].setLine(cx, cy, cx + fast_cos(ang) * r, cy + fast_sin(ang) * r)

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_ice)
        painter.drawText(QRectF(rect.x() + 8, rect.y() + 4, rect.width() - 16, 14),
                         Qt.AlignmentFlag.AlignLeft, "● ● ●  CRYOGENIC CORE // LATTICE")
        painter.drawLines(self.spokes)


class FreezeThermalColumnVisual(SlotVisual):
    def __init__(self) -> None:
        super().__init__()
        self.col_rect = QRectF()
        self.fill_rect = QRectF()
        self.pen_ice = QPen()
        self.brush_ice = QBrush()
        self.font_hdr = QFont("Consolas", 6, QFont.Weight.Bold)

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        c_pri = QColor(palette.pri)
        self.pen_ice = QPen(c_pri, 1.2)
        self.brush_ice = QBrush(c_pri)
        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 20.0, rect.width() - 16.0, rect.height() - 28.0
        self.col_rect = QRectF(bx + bw * 0.35, by + 4.0, bw * 0.3, bh - 8.0)
        self.fill_rect = QRectF(self.col_rect)

    def tick(self, dt: float, signals: HudSignals) -> None:
        h = self.col_rect.height() * 0.75
        self.fill_rect.setRect(self.col_rect.x(), self.col_rect.bottom() - h, self.col_rect.width(), h)

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_ice)
        painter.drawText(QRectF(rect.x() + 8, rect.y() + 4, rect.width() - 16, 12),
                         Qt.AlignmentFlag.AlignCenter, "THERMAL DELTA // 0 KELVIN")
        painter.drawRect(self.col_rect)
        painter.setBrush(self.brush_ice)
        painter.drawRect(self.fill_rect)


class FreezeCoolantLoopVisual(SlotVisual):
    def __init__(self) -> None:
        super().__init__()
        self.pen_loop = QPen()
        self.font_hdr = QFont("Consolas", 6, QFont.Weight.Bold)
        self.loop_rect = QRectF()

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        c_pri = QColor(palette.pri)
        self.pen_loop = QPen(c_pri, 1.5, Qt.PenStyle.DashDotLine)
        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 18.0, rect.width() - 16.0, rect.height() - 24.0
        cx, cy = bx + bw / 2.0, by + bh / 2.0
        self.loop_rect = QRectF(cx - 24, cy - 14, 48, 28)

    def tick(self, dt: float, signals: HudSignals) -> None:
        pass

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_loop)
        painter.drawText(QRectF(rect.x() + 8, rect.y() + 3, rect.width() - 16, 12),
                         Qt.AlignmentFlag.AlignCenter, "CRYO-SUIT COOLANT LOOP")
        painter.drawRoundedRect(self.loop_rect, 6, 6)
