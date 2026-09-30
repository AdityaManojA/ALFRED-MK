"""
core/hud/visuals/slots/watchtower.py — Watchtower Omni Theme Visual Set:
- Slot 1: Arc-Reactor / Orbital Flux Ring (concentric flux rings, targeting reticle)
- Slot 2: Power Output + Suit Integrity (dual arcs with output curve)
- Slot 3: Armor Diagnostic Holo-Man (sectional wireframe with subsystem status)
"""
from __future__ import annotations

import math
from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen

from core.hud.visuals.base import HudSignals, SlotVisual, fast_cos, fast_sin
from core.ui.themes.schema import PaletteDefinition


class WatchtowerFluxRingVisual(SlotVisual):
    def __init__(self) -> None:
        super().__init__()
        self.rot: float = 0.0
        self.pen_ring = QPen()
        self.pen_reticle = QPen()
        self.font_hdr = QFont("Consolas", 7, QFont.Weight.Bold)
        self.rect_inner = QRectF()

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        c_pri = QColor(palette.pri)
        c_acc = QColor(palette.acc)
        self.pen_ring = QPen(c_pri, 1.4)
        self.pen_reticle = QPen(c_acc, 1.0, Qt.PenStyle.DashLine)
        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 22.0, rect.width() - 16.0, rect.height() - 30.0
        self.rect_inner = QRectF(bx, by, bw, bh)

    def tick(self, dt: float, signals: HudSignals) -> None:
        self.rot = (self.rot + dt * 1.5) % (2.0 * math.pi)

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_ring)
        painter.drawText(QRectF(rect.x() + 8, rect.y() + 4, rect.width() - 16, 14),
                         Qt.AlignmentFlag.AlignLeft, "● ● ●  ORBITAL FLUX RING // OMNI")
        cx = self.rect_inner.x() + self.rect_inner.width() / 2.0
        cy = self.rect_inner.y() + self.rect_inner.height() / 2.0
        r = min(self.rect_inner.width(), self.rect_inner.height()) * 0.38
        painter.drawEllipse(QPointF(cx, cy), r, r)
        painter.setPen(self.pen_reticle)
        painter.drawEllipse(QPointF(cx, cy), r * 0.65, r * 0.65)


class WatchtowerPowerOutputVisual(SlotVisual):
    def __init__(self) -> None:
        super().__init__()
        self.pen_arc = QPen()
        self.font_hdr = QFont("Consolas", 6, QFont.Weight.Bold)
        self.rect_inner = QRectF()

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        c_pri = QColor(palette.pri)
        self.pen_arc = QPen(c_pri, 2.0)
        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 20.0, rect.width() - 16.0, rect.height() - 28.0
        self.rect_inner = QRectF(bx, by, bw, bh)

    def tick(self, dt: float, signals: HudSignals) -> None:
        pass

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_arc)
        painter.drawText(QRectF(rect.x() + 8, rect.y() + 4, rect.width() - 16, 12),
                         Qt.AlignmentFlag.AlignCenter, "ORBITAL POWER OUTPUT // 1.21 GW")
        cx = self.rect_inner.x() + self.rect_inner.width() / 2.0
        cy = self.rect_inner.y() + self.rect_inner.height() / 2.0
        painter.drawArc(QRectF(cx - 30, cy - 20, 60, 40), 30 * 16, 120 * 16)


class WatchtowerHoloManVisual(SlotVisual):
    def __init__(self) -> None:
        super().__init__()
        self.pen_holo = QPen()
        self.font_hdr = QFont("Consolas", 6, QFont.Weight.Bold)
        self.rect_inner = QRectF()

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        c_pri = QColor(palette.pri)
        self.pen_holo = QPen(c_pri, 1.2)
        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 18.0, rect.width() - 16.0, rect.height() - 24.0
        self.rect_inner = QRectF(bx, by, bw, bh)

    def tick(self, dt: float, signals: HudSignals) -> None:
        pass

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_holo)
        painter.drawText(QRectF(rect.x() + 8, rect.y() + 3, rect.width() - 16, 12),
                         Qt.AlignmentFlag.AlignCenter, "ARMOR DIAGNOSTIC // HOLO-MAN")
        painter.drawRect(self.rect_inner)
