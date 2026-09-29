"""
core/hud/visuals/slots/joker.py — Joker Theme Visual Set:
- Slot 1: Entropy Card Scatter (cards tumbling on chaos field)
- Slot 2: Distorted Laugh Waveform + Jack-in-the-Box Coil (erratic scope)
- Slot 3: Grinning Mask Morph (silhouette warping between faces)
"""
from __future__ import annotations

import math
from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen

from core.hud.visuals.base import HudSignals, SlotVisual, fast_cos, fast_sin
from core.hud.visuals.primitives import WaveTrace
from core.ui.themes.schema import PaletteDefinition


class JokerCardScatterVisual(SlotVisual):
    def __init__(self) -> None:
        super().__init__()
        self.t: float = 0.0
        self.pen_card = QPen()
        self.brush_card = QBrush()
        self.font_hdr = QFont("Consolas", 7, QFont.Weight.Bold)
        self.rect_inner = QRectF()
        self.cards = [QRectF() for _ in range(5)]

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        c_pri = QColor(palette.pri)
        c_acc = QColor(palette.acc)
        self.pen_card = QPen(c_acc, 1.2)
        self.brush_card = QBrush(QColor(c_pri.red(), c_pri.green(), c_pri.blue(), 50))
        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 22.0, rect.width() - 16.0, rect.height() - 30.0
        self.rect_inner = QRectF(bx, by, bw, bh)

    def tick(self, dt: float, signals: HudSignals) -> None:
        self.t = (self.t + dt * 2.5) % (2.0 * math.pi)
        cx = self.rect_inner.x() + self.rect_inner.width() / 2.0
        cy = self.rect_inner.y() + self.rect_inner.height() / 2.0
        for i in range(5):
            ox = fast_cos(self.t + i * 1.2) * 22.0
            oy = fast_sin(self.t * 1.4 + i * 0.8) * 14.0
            self.cards[i].setRect(cx + ox - 8, cy + oy - 12, 16, 24)

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_card)
        painter.drawText(QRectF(rect.x() + 8, rect.y() + 4, rect.width() - 16, 14),
                         Qt.AlignmentFlag.AlignLeft, "● ● ●  ENTROPY CARD // SCATTER")
        for card in self.cards:
            painter.fillRect(card, self.brush_card)
            painter.drawRect(card)


class JokerLaughWaveVisual(SlotVisual):
    def __init__(self) -> None:
        super().__init__()
        self.wave = WaveTrace(sample_count=40)
        self.t: float = 0.0
        self.pen_laugh = QPen()
        self.font_hdr = QFont("Consolas", 6, QFont.Weight.Bold)
        self.rect_inner = QRectF()

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        c_acc = QColor(palette.acc)
        self.pen_laugh = QPen(c_acc, 1.4)
        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 20.0, rect.width() - 16.0, rect.height() - 28.0
        self.rect_inner = QRectF(bx, by, bw, bh)
        self.wave.layout(bx + 4.0, by + bh / 2.0, bw - 8.0, height_amp=bh * 0.4)

    def tick(self, dt: float, signals: HudSignals) -> None:
        self.t = (self.t + dt * 6.0) % (2.0 * math.pi)
        samples = [fast_sin(i * 0.8 + self.t) * (fast_cos(i * 1.5 - self.t * 2.0)) for i in range(40)]
        self.wave.update_samples(samples)

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_laugh)
        painter.drawText(QRectF(rect.x() + 8, rect.y() + 4, rect.width() - 16, 12),
                         Qt.AlignmentFlag.AlignCenter, "DISTORTED LAUGH WAVEFORM // HA-HA")
        painter.drawLines(self.wave.lines)


class JokerGrinningMaskVisual(SlotVisual):
    def __init__(self) -> None:
        super().__init__()
        self.pen_grin = QPen()
        self.font_hdr = QFont("Consolas", 6, QFont.Weight.Bold)
        self.rect_inner = QRectF()

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        c_pri = QColor(palette.pri)
        self.pen_grin = QPen(c_pri, 1.6)
        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 18.0, rect.width() - 16.0, rect.height() - 24.0
        self.rect_inner = QRectF(bx, by, bw, bh)

    def tick(self, dt: float, signals: HudSignals) -> None:
        pass

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_grin)
        painter.drawText(QRectF(rect.x() + 8, rect.y() + 3, rect.width() - 16, 12),
                         Qt.AlignmentFlag.AlignCenter, "GRINNING MASK MORPH // SMILE")
        cx = self.rect_inner.x() + self.rect_inner.width() / 2.0
        cy = self.rect_inner.y() + self.rect_inner.height() / 2.0
        # Wild smile arc
        smile_box = QRectF(cx - 20, cy - 6, 40, 20)
        painter.drawArc(smile_box, 200 * 16, 140 * 16)
