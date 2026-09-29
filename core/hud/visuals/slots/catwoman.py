"""
core/hud/visuals/slots/catwoman.py — Catwoman Theme Visual Set:
- Slot 1: Rooftop Sonar Wire-Grid (isometric scanning laser line)
- Slot 2: Lockpick Tumbler Waveform (4 pins + acoustic vibration trace)
- Slot 3: Feline Acrobat Silhouette (interpolated jump arc with center-of-mass vector)
"""
from __future__ import annotations

import math
from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen

from core.hud.visuals.base import HudSignals, SlotVisual, fast_cos, fast_sin
from core.hud.visuals.primitives import WaveTrace
from core.ui.themes.schema import PaletteDefinition


class CatwomanSonarVisual(SlotVisual):
    def __init__(self) -> None:
        super().__init__()
        self.scan_y: float = 0.0
        self.pen_grid = QPen()
        self.pen_laser = QPen()
        self.brush_laser = QBrush()
        self.font_hdr = QFont("Consolas", 7, QFont.Weight.Bold)
        self.rect_inner = QRectF()
        self.scan_line = QLineF()
        self.scan_rect = QRectF()
        self.grid_lines: list[QLineF] = []

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        c_pri = QColor(palette.pri)
        c_acc = QColor(palette.acc)
        self.pen_grid = QPen(QColor(c_pri.red(), c_pri.green(), c_pri.blue(), 60), 1.0)
        self.pen_laser = QPen(c_acc, 1.4)
        self.brush_laser = QBrush(QColor(c_acc.red(), c_acc.green(), c_acc.blue(), 40))

        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 22.0, rect.width() - 16.0, rect.height() - 30.0
        self.rect_inner = QRectF(bx, by, bw, bh)
        self.scan_line = QLineF(bx, by, bx + bw, by)
        self.scan_rect = QRectF(bx, by, bw, 8.0)

        # Build isometric rooftop grid
        self.grid_lines.clear()
        step = 20.0
        for x in range(0, int(bw), int(step)):
            self.grid_lines.append(QLineF(bx + x, by, bx + x - 16, by + bh))
        for y in range(0, int(bh), int(step)):
            self.grid_lines.append(QLineF(bx, by + y, bx + bw, by + y))

    def tick(self, dt: float, signals: HudSignals) -> None:
        self.scan_y = (self.scan_y + dt * (0.8 + signals.drift * 2.0)) % 1.0
        ly = self.rect_inner.y() + self.scan_y * self.rect_inner.height()
        self.scan_line.setLine(self.rect_inner.x(), ly, self.rect_inner.right(), ly)
        self.scan_rect.setRect(self.rect_inner.x(), max(self.rect_inner.y(), ly - 4.0), self.rect_inner.width(), 8.0)

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        painter.setPen(self.pen_grid)
        painter.drawRect(self.rect_inner)
        painter.drawLines(self.grid_lines)

        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_laser)
        painter.drawText(QRectF(rect.x() + 8, rect.y() + 4, rect.width() - 16, 14),
                         Qt.AlignmentFlag.AlignLeft, "● ● ●  ROOFTOP SONAR // EAST END")

        # Laser scan bar
        painter.setBrush(self.brush_laser)
        painter.drawRect(self.scan_rect)
        painter.drawLine(self.scan_line)


class CatwomanLockpickVisual(SlotVisual):
    def __init__(self) -> None:
        super().__init__()
        self.wave = WaveTrace(sample_count=32)
        self.pins = [0.2, 0.5, 0.8, 0.4]
        self.pin_lines = [QLineF() for _ in range(4)]
        self.pen_pin = QPen()
        self.pen_shear = QPen()
        self.pen_wave = QPen()
        self.font_hdr = QFont("Consolas", 6, QFont.Weight.Bold)
        self.rect_inner = QRectF()

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        c_pri = QColor(palette.pri)
        c_acc = QColor(palette.acc)
        self.pen_pin = QPen(c_pri, 2.0)
        self.pen_shear = QPen(c_acc, 1.0, Qt.PenStyle.DashLine)
        self.pen_wave = QPen(c_acc, 1.2)

        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 20.0, rect.width() - 16.0, rect.height() - 28.0
        self.rect_inner = QRectF(bx, by, bw, bh)
        self.wave.layout(bx + 4.0, by + bh * 0.75, bw - 8.0, height_amp=10.0)

    def tick(self, dt: float, signals: HudSignals) -> None:
        t = (dt * 4.0)
        samples = [fast_sin(i * 0.6 + t) * (0.2 + signals.mic_level * 0.8) for i in range(32)]
        self.wave.update_samples(samples)

        shear_y = self.rect_inner.y() + self.rect_inner.height() * 0.4
        pw = self.rect_inner.width() / 5.0
        for i in range(4):
            px = self.rect_inner.x() + (i + 1) * pw
            self.pins[i] = (self.pins[i] + dt * (0.4 + i * 0.2)) % 1.0
            pin_h = 6.0 + self.pins[i] * 18.0
            self.pin_lines[i].setLine(px, shear_y - pin_h, px, shear_y + 4.0)

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_wave)
        painter.drawText(QRectF(rect.x() + 8, rect.y() + 4, rect.width() - 16, 12),
                         Qt.AlignmentFlag.AlignCenter, "TUMBLER LOCKPICK // ACOUSTIC VIBRATION")

        # Shear line
        shear_y = self.rect_inner.y() + self.rect_inner.height() * 0.4
        painter.setPen(self.pen_shear)
        painter.drawLine(QLineF(self.rect_inner.x(), shear_y, self.rect_inner.right(), shear_y))

        # Pins
        painter.setPen(self.pen_pin)
        painter.drawLines(self.pin_lines)

        # Vibration wave
        painter.setPen(self.pen_wave)
        painter.drawLines(self.wave.lines)


class CatwomanAcrobatVisual(SlotVisual):
    def __init__(self) -> None:
        super().__init__()
        self.phase: float = 0.0
        self.pen_body = QPen()
        self.pen_vector = QPen()
        self.font_hdr = QFont("Consolas", 6, QFont.Weight.Bold)
        self.rect_inner = QRectF()
        self.body_lines = [QLineF() for _ in range(6)]

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        c_pri = QColor(palette.pri)
        c_acc = QColor(palette.acc)
        self.pen_body = QPen(c_pri, 1.6)
        self.pen_vector = QPen(c_acc, 1.0, Qt.PenStyle.DotLine)

        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 18.0, rect.width() - 16.0, rect.height() - 24.0
        self.rect_inner = QRectF(bx, by, bw, bh)

    def tick(self, dt: float, signals: HudSignals) -> None:
        self.phase = (self.phase + dt * 1.6) % (2.0 * math.pi)
        cx = self.rect_inner.x() + self.rect_inner.width() * (0.3 + 0.4 * fast_sin(self.phase))
        cy = self.rect_inner.y() + self.rect_inner.height() * (0.5 - 0.3 * abs(fast_cos(self.phase)))

        # Feline agile wireframe pose
        self.body_lines[0].setLine(cx, cy, cx - 12, cy + 8)
        self.body_lines[1].setLine(cx, cy, cx + 14, cy - 6)
        self.body_lines[2].setLine(cx - 12, cy + 8, cx - 18, cy + 18)
        self.body_lines[3].setLine(cx + 14, cy - 6, cx + 22, cy + 4)
        self.body_lines[4].setLine(cx, cy, cx - 8, cy - 14)  # spine/head
        self.body_lines[5].setLine(cx - 8, cy - 14, cx - 14, cy - 18)  # tail

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_body)
        painter.drawText(QRectF(rect.x() + 8, rect.y() + 3, rect.width() - 16, 12),
                         Qt.AlignmentFlag.AlignCenter, "FELINE ACROBAT SILHOUETTE // KINEMATICS")

        painter.drawLines(self.body_lines)
