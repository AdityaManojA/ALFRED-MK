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
    """Slot 1: 2x3 cell-block floorplan with a vertical light line sweeping left to right."""

    def __init__(self) -> None:
        """Initialise pens, font and geometry placeholders for this slot."""
        super().__init__()
        self.sweep_x: float = 0.0
        self.pen_wall = QPen()
        self.pen_light = QPen()
        self.font_hdr = QFont("Consolas", 7, QFont.Weight.Bold)
        self.rect_inner = QRectF()
        self.sweep_line = QLineF()
        self.cells = [QRectF() for _ in range(6)]

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        """Build pens from the palette and lay out the 2x3 cell grid inside the panel."""
        c_pri = QColor(palette.pri)
        c_acc = QColor(palette.acc)
        self.pen_wall = QPen(c_pri, 1.2)
        self.pen_light = QPen(c_acc, 1.4)

        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 22.0, rect.width() - 16.0, rect.height() - 30.0
        self.rect_inner = QRectF(bx, by, bw, bh)
        cw, ch = bw / 3.0 - 4.0, bh / 2.0 - 4.0
        for row in range(2):
            for col in range(3):
                self.cells[row * 3 + col].setRect(bx + col * (cw + 4.0), by + row * (ch + 4.0), cw, ch)

    def tick(self, dt: float, signals: HudSignals) -> None:
        """Advance the horizontal light sweep across the floorplan."""
        self.sweep_x = (self.sweep_x + dt * 0.4) % 1.0
        lx = self.rect_inner.x() + self.sweep_x * self.rect_inner.width()
        self.sweep_line.setLine(lx, self.rect_inner.y(), lx, self.rect_inner.bottom())

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        """Draw the floorplan header, cell rectangles and sweep line."""
        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_wall)
        painter.drawText(QRectF(rect.x() + 8, rect.y() + 4, rect.width() - 16, 14),
                         Qt.AlignmentFlag.AlignLeft, "● ● ●  CELL-BLOCK FLOORPLAN // BLOCK B")
        for cell in self.cells:
            painter.drawRect(cell)
        painter.setPen(self.pen_light)
        painter.drawLine(self.sweep_line)


class ArkhamEEGVisual(SlotVisual):
    """Slot 2: 48-sample EEG trace whose phase speed rises with alert_level."""

    def __init__(self) -> None:
        """Initialise pens, font and geometry placeholders for this slot."""
        super().__init__()
        self.wave = WaveTrace(sample_count=48)
        self.t: float = 0.0
        self.pen_eeg = QPen()
        self.font_hdr = QFont("Consolas", 6, QFont.Weight.Bold)
        self.rect_inner = QRectF()

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        """Build the EEG pen and lay out the wave trace inside the panel."""
        c_pri = QColor(palette.pri)
        self.pen_eeg = QPen(c_pri, 1.2)
        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 20.0, rect.width() - 16.0, rect.height() - 28.0
        self.rect_inner = QRectF(bx, by, bw, bh)
        self.wave.layout(bx + 4.0, by + bh / 2.0, bw - 8.0, height_amp=bh * 0.35)

    def tick(self, dt: float, signals: HudSignals) -> None:
        """Advance the phase (faster with alert level) and recompute the two-sine EEG samples."""
        self.t = (self.t + dt * (4.0 + signals.alert_level * 3.0)) % (2.0 * math.pi)
        samples = [fast_sin(i * 0.5 + self.t) * 0.6 + fast_sin(i * 1.8 - self.t * 2.0) * 0.4 for i in range(48)]
        self.wave.update_samples(samples)

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        """Draw the EEG header and wave trace."""
        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_eeg)
        painter.drawText(QRectF(rect.x() + 8, rect.y() + 4, rect.width() - 16, 12),
                         Qt.AlignmentFlag.AlignCenter, "EEG BRAINWAVE MONITOR // DELTA/THETA")
        painter.drawLines(self.wave.lines)


class ArkhamVitalsVisual(SlotVisual):
    """Slot 3: pulse ring centred in the panel whose radius cycles from 6 to 24 px."""

    def __init__(self) -> None:
        """Initialise pens, font and geometry placeholders for this slot."""
        super().__init__()
        self.pulse: float = 0.0
        self.pen_vital = QPen()
        self.font_hdr = QFont("Consolas", 6, QFont.Weight.Bold)
        self.rect_inner = QRectF()

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        """Build the vitals pen and compute the inner panel rect."""
        c_pri = QColor(palette.pri)
        self.pen_vital = QPen(c_pri, 1.4)
        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 18.0, rect.width() - 16.0, rect.height() - 24.0
        self.rect_inner = QRectF(bx, by, bw, bh)

    def tick(self, dt: float, signals: HudSignals) -> None:
        """Advance the pulse phase."""
        self.pulse = (self.pulse + dt * 2.0) % 1.0

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        """Draw the vitals header and a pulsing circle at the panel centre."""
        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_vital)
        painter.drawText(QRectF(rect.x() + 8, rect.y() + 3, rect.width() - 16, 12),
                         Qt.AlignmentFlag.AlignCenter, "PATIENT VITALS SILHOUETTE")
        cx = self.rect_inner.x() + self.rect_inner.width() / 2.0
        cy = self.rect_inner.y() + self.rect_inner.height() / 2.0
        r = 6.0 + self.pulse * 18.0
        painter.drawEllipse(QPointF(cx, cy), r, r)
