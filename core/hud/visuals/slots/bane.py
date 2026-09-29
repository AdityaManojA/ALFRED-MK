"""
core/hud/visuals/slots/bane.py — Bane Theme Visual Set:
- Slot 1: Venom Pressure Chamber (fluid oscillating waveform, systolic/diastolic spikes)
- Slot 2: Dosage Regulator (twin pressure columns, valve cycling, overload flare on alert_level)
- Slot 3: Musculature / Mask Schematic (venom tubing flow pulses with system load)
"""
from __future__ import annotations

import math
from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen

from core.hud.visuals.base import HudSignals, SlotVisual, fast_cos, fast_sin
from core.hud.visuals.primitives import BarArray, WaveTrace
from core.ui.themes.schema import PaletteDefinition


class BanePressureChamberVisual(SlotVisual):
    def __init__(self) -> None:
        super().__init__()
        self.wave = WaveTrace(sample_count=48)
        self.t: float = 0.0
        self.pen_wave = QPen()
        self.pen_border = QPen()
        self.font_hdr = QFont("Consolas", 7, QFont.Weight.Bold)
        self.rect_inner = QRectF()

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        c_pri = QColor(palette.pri)
        c_acc = QColor(palette.acc)
        self.pen_wave = QPen(c_pri, 1.5)
        self.pen_border = QPen(QColor(c_pri.red(), c_pri.green(), c_pri.blue(), 50), 1.0)
        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 22.0, rect.width() - 16.0, rect.height() - 30.0
        self.rect_inner = QRectF(bx, by, bw, bh)
        self.wave.layout(bx + 4.0, by + bh / 2.0, bw - 8.0, height_amp=bh * 0.38)

    def tick(self, dt: float, signals: HudSignals) -> None:
        self.t = (self.t + dt * (3.0 + signals.cpu_pct * 0.04)) % (2.0 * math.pi)
        samples = []
        for i in range(48):
            systolic = math.exp(-((i - 24) ** 2) / 18.0) * fast_sin(self.t * 2.0)
            base = fast_sin(i * 0.4 - self.t) * 0.4
            samples.append(base + systolic * 1.2)
        self.wave.update_samples(samples)

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        painter.setPen(self.pen_border)
        painter.drawRect(self.rect_inner)
        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_wave)
        painter.drawText(QRectF(rect.x() + 8, rect.y() + 4, rect.width() - 16, 14),
                         Qt.AlignmentFlag.AlignLeft, "● ● ●  VENOM PRESSURE // CHAMBER")
        painter.drawLines(self.wave.lines)


class BaneDosageRegulatorVisual(SlotVisual):
    def __init__(self) -> None:
        super().__init__()
        self.bars = BarArray(count=2, peak_decay_per_s=0.8)
        self.pen_col = QPen()
        self.brush_col = QBrush()
        self.font_hdr = QFont("Consolas", 6, QFont.Weight.Bold)
        self.rect_inner = QRectF()

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        c_pri = QColor(palette.pri)
        c_acc = QColor(palette.acc)
        self.pen_col = QPen(c_pri, 1.4)
        self.brush_col = QBrush(c_pri)
        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 20.0, rect.width() - 16.0, rect.height() - 28.0
        self.rect_inner = QRectF(bx, by, bw, bh)
        self.bars.layout(bx + bw * 0.25, by + 4.0, bw * 0.5, bh - 8.0, gap=16.0)

    def tick(self, dt: float, signals: HudSignals) -> None:
        v1 = min(1.0, signals.cpu_pct / 100.0 + 0.1)
        v2 = min(1.0, signals.mem_pct / 100.0 + 0.1)
        self.bars.tick(dt, [v1, v2])

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_col)
        painter.drawText(QRectF(rect.x() + 8, rect.y() + 4, rect.width() - 16, 12),
                         Qt.AlignmentFlag.AlignCenter, "TWIN DOSAGE REGULATOR // OCTANE")
        for i in range(2):
            painter.fillRect(self.bars.rects[i], self.brush_col)
        painter.setPen(self.pen_col)
        painter.drawLines(self.bars.peak_lines)


class BaneMaskSchematicVisual(SlotVisual):
    def __init__(self) -> None:
        super().__init__()
        self.pulse: float = 0.0
        self.pen_tube = QPen()
        self.font_hdr = QFont("Consolas", 6, QFont.Weight.Bold)
        self.rect_inner = QRectF()
        self.tubes = [QLineF() for _ in range(8)]

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        c_pri = QColor(palette.pri)
        self.pen_tube = QPen(c_pri, 1.8)
        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 18.0, rect.width() - 16.0, rect.height() - 24.0
        self.rect_inner = QRectF(bx, by, bw, bh)
        cx, cy = bx + bw / 2.0, by + bh / 2.0

        # Mask tubing layout
        self.tubes[0].setLine(cx - 24, cy - 16, cx - 12, cy)
        self.tubes[1].setLine(cx + 24, cy - 16, cx + 12, cy)
        self.tubes[2].setLine(cx - 12, cy, cx - 4, cy + 12)
        self.tubes[3].setLine(cx + 12, cy, cx + 4, cy + 12)
        self.tubes[4].setLine(cx - 4, cy + 12, cx + 4, cy + 12)
        self.tubes[5].setLine(cx, cy - 18, cx, cy - 6)
        self.tubes[6].setLine(cx - 18, cy + 8, cx - 8, cy + 18)
        self.tubes[7].setLine(cx + 18, cy + 8, cx + 8, cy + 18)

    def tick(self, dt: float, signals: HudSignals) -> None:
        self.pulse = (self.pulse + dt * 4.0) % (2.0 * math.pi)

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_tube)
        painter.drawText(QRectF(rect.x() + 8, rect.y() + 3, rect.width() - 16, 12),
                         Qt.AlignmentFlag.AlignCenter, "VENOM MASK FLOW SCHEMATIC")
        painter.drawLines(self.tubes)
