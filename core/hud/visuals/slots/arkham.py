"""
core/hud/visuals/slots/arkham.py — Arkham Asylum Theme Visual Set:
- Slot 1: Cell-Block Floorplan Sweep (top-down plan, sweeping light, occupancy pings)
- Slot 2: EEG Brainwave Monitor (multi-channel delta/theta, agitation from alert_level)
- Slot 3: Patient Vitals Silhouette (body outline with pulse ring)
"""
from __future__ import annotations

import math
from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen

from core.hud.visuals.base import HudSignals, SlotVisual, fast_cos, fast_sin
from core.hud.visuals.primitives import WaveTrace
from core.ui.themes.schema import PaletteDefinition


class ArkhamFloorplanVisual(SlotVisual):
    def __init__(self) -> None:
        super().__init__()
        self.sweep_x: float = 0.0
        self.pen_wall = QPen()
        self.pen_light = QPen()
        self.font_hdr = QFont("Consolas", 7, QFont.Weight.Bold)
        self.rect_inner = QRectF()
        self.cells = [QRectF() for _ in range(6)]

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        c_pri = QColor(palette.pri)
        c_acc = QColor(palette.acc)
        self.pen_wall = QPen(c_pri, 1.2)
        self.pen_light = QPen(c_acc, 1.4)

        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 22.0, rect.width() - 16.0, rect.height() - 30.0
        self.rect_inner = QRectF(bx, by, bw, bh)
        self.sweep_line = QLineF()
        cw, ch = bw / 3.0 - 4.0, bh / 2.0 - 4.0
        for row in range(2):
            for col in range(3):
                self.cells[row * 3 + col].setRect(bx + col * (cw + 4.0), by + row * (ch + 4.0), cw, ch)

    def tick(self, dt: float, signals: HudSignals) -> None:
        self.sweep_x = (self.sweep_x + dt * 0.4) % 1.0
        lx = self.rect_inner.x() + self.sweep_x * self.rect_inner.width()
        self.sweep_line.setLine(lx, self.rect_inner.y(), lx, self.rect_inner.bottom())

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_wall)
        painter.drawText(QRectF(rect.x() + 8, rect.y() + 4, rect.width() - 16, 14),
                         Qt.AlignmentFlag.AlignLeft, "● ● ●  CELL-BLOCK FLOORPLAN // BLOCK B")
        for cell in self.cells:
            painter.drawRect(cell)
        painter.setPen(self.pen_light)
        painter.drawLine(self.sweep_line)


class ArkhamEEGVisual(SlotVisual):
    def __init__(self) -> None:
        super().__init__()
        self.wave = WaveTrace(sample_count=48)
        self.t: float = 0.0
        self.pen_eeg = QPen()
        self.font_hdr = QFont("Consolas", 6, QFont.Weight.Bold)
        self.rect_inner = QRectF()

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        c_pri = QColor(palette.pri)
        self.pen_eeg = QPen(c_pri, 1.2)
        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 20.0, rect.width() - 16.0, rect.height() - 28.0
        self.rect_inner = QRectF(bx, by, bw, bh)
        self.wave.layout(bx + 4.0, by + bh / 2.0, bw - 8.0, height_amp=bh * 0.35)

    def tick(self, dt: float, signals: HudSignals) -> None:
        self.t = (self.t + dt * (4.0 + signals.alert_level * 3.0)) % (2.0 * math.pi)
        samples = [fast_sin(i * 0.5 + self.t) * 0.6 + fast_sin(i * 1.8 - self.t * 2.0) * 0.4 for i in range(48)]
        self.wave.update_samples(samples)

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_eeg)
        painter.drawText(QRectF(rect.x() + 8, rect.y() + 4, rect.width() - 16, 12),
                         Qt.AlignmentFlag.AlignCenter, "EEG BRAINWAVE MONITOR // DELTA/THETA")
        painter.drawLines(self.wave.lines)


class ArkhamVitalsVisual(SlotVisual):
    def __init__(self) -> None:
        super().__init__()
        self.pulse: float = 0.0
        self.pen_vital = QPen()
        self.font_hdr = QFont("Consolas", 6, QFont.Weight.Bold)
        self.rect_inner = QRectF()

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        c_pri = QColor(palette.pri)
        self.pen_vital = QPen(c_pri, 1.4)
        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 18.0, rect.width() - 16.0, rect.height() - 24.0
        self.rect_inner = QRectF(bx, by, bw, bh)

    def tick(self, dt: float, signals: HudSignals) -> None:
        self.pulse = (self.pulse + dt * 2.0) % 1.0

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_vital)
        painter.drawText(QRectF(rect.x() + 8, rect.y() + 3, rect.width() - 16, 12),
                         Qt.AlignmentFlag.AlignCenter, "PATIENT VITALS SILHOUETTE")
        cx = self.rect_inner.x() + self.rect_inner.width() / 2.0
        cy = self.rect_inner.y() + self.rect_inner.height() / 2.0
        r = 6.0 + self.pulse * 18.0
        painter.drawEllipse(QPointF(cx, cy), r, r)
