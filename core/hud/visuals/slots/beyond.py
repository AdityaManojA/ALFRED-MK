"""
core/hud/visuals/slots/beyond.py — Batman Beyond (Cyberpunk) Theme Visual Set:
- Slot 1: Cyber-Optic Retinal HUD (hex mesh, moving target-lock brackets, vector glitch)
- Slot 2: ICE Intrusion Ladder (stacked bandwidth bars with packet-burst glitch rows)
- Slot 3: Chrome-Limb Diagnostic Avatar (sectional body, module status blocks)
"""
from __future__ import annotations

import math
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen

from core.hud.visuals.base import HudSignals, SlotVisual, fast_cos, fast_sin
from core.hud.visuals.primitives import BarArray
from core.ui.themes.schema import PaletteDefinition


class BeyondRetinalVisual(SlotVisual):
    def __init__(self) -> None:
        super().__init__()
        self.lock_x: float = 0.0
        self.lock_y: float = 0.0
        self.t: float = 0.0
        self.pen_mesh = QPen()
        self.pen_target = QPen()
        self.font_hdr = QFont("Consolas", 7, QFont.Weight.Bold)
        self.rect_inner = QRectF()
        self.rect_hdr = QRectF()

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        c_pri = QColor(palette.pri)
        c_acc = QColor(palette.acc)
        self.pen_mesh = QPen(QColor(c_pri.red(), c_pri.green(), c_pri.blue(), 45), 1.0)
        self.pen_target = QPen(c_acc, 1.4)

        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 22.0, rect.width() - 16.0, rect.height() - 30.0
        self.rect_inner.setRect(bx, by, bw, bh)
        self.rect_hdr.setRect(rect.x() + 8.0, rect.y() + 4.0, rect.width() - 16.0, 14.0)

    def tick(self, dt: float, signals: HudSignals) -> None:
        self.t = (self.t + dt * 2.0) % (2.0 * math.pi)
        cx = self.rect_inner.x() + self.rect_inner.width() / 2.0
        cy = self.rect_inner.y() + self.rect_inner.height() / 2.0
        self.lock_x = cx + fast_cos(self.t) * 20.0
        self.lock_y = cy + fast_sin(self.t * 1.5) * 12.0

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_target)
        painter.drawText(self.rect_hdr, Qt.AlignmentFlag.AlignLeft, "● ● ●  CYBER-OPTIC RETINAL // HUD")

        # Target lock brackets around lock_x, lock_y
        arm = 6.0
        lx, ly = self.lock_x, self.lock_y
        painter.drawLine(int(lx - arm), int(ly - arm), int(lx + arm), int(ly - arm))
        painter.drawLine(int(lx - arm), int(ly + arm), int(lx + arm), int(ly + arm))
        painter.drawLine(int(lx - arm), int(ly - arm), int(lx - arm), int(ly + arm))
        painter.drawLine(int(lx + arm), int(ly - arm), int(lx + arm), int(ly + arm))


class BeyondICELadderVisual(SlotVisual):
    def __init__(self) -> None:
        super().__init__()
        self.bars = BarArray(count=8, peak_decay_per_s=2.0)
        self.pen_ice = QPen()
        self.brush_ice = QBrush()
        self.font_hdr = QFont("Consolas", 6, QFont.Weight.Bold)
        self.rect_inner = QRectF()
        self.rect_hdr = QRectF()

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        c_pri = QColor(palette.pri)
        self.pen_ice = QPen(c_pri, 1.2)
        self.brush_ice = QBrush(c_pri)
        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 20.0, rect.width() - 16.0, rect.height() - 28.0
        self.rect_inner.setRect(bx, by, bw, bh)
        self.rect_hdr.setRect(rect.x() + 8.0, rect.y() + 4.0, rect.width() - 16.0, 12.0)
        self.bars.layout(bx + 8.0, by + 4.0, bw - 16.0, bh - 8.0, gap=4.0)

    def tick(self, dt: float, signals: HudSignals) -> None:
        vals = [(fast_sin(i * 1.2 + dt * 5.0) * 0.5 + 0.5) * (0.3 + signals.net_kbps / 500.0) for i in range(8)]
        self.bars.tick(dt, vals)

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_ice)
        painter.drawText(self.rect_hdr, Qt.AlignmentFlag.AlignCenter, "ICE INTRUSION LADDER // BANDWIDTH")
        painter.setBrush(self.brush_ice)
        painter.drawRects(self.bars.rects)


class BeyondAvatarVisual(SlotVisual):
    def __init__(self) -> None:
        super().__init__()
        self.pen_limb = QPen()
        self.font_hdr = QFont("Consolas", 6, QFont.Weight.Bold)
        self.rect_inner = QRectF()
        self.rect_hdr = QRectF()
        self.limbs = [QRectF() for _ in range(5)]

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        c_pri = QColor(palette.pri)
        self.pen_limb = QPen(c_pri, 1.2)
        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 18.0, rect.width() - 16.0, rect.height() - 24.0
        self.rect_inner.setRect(bx, by, bw, bh)
        self.rect_hdr.setRect(rect.x() + 8.0, rect.y() + 3.0, rect.width() - 16.0, 12.0)
        cx, cy = bx + bw / 2.0, by + bh / 2.0

        # Sectional modules
        self.limbs[0].setRect(cx - 6, cy - 22, 12, 10)  # Head
        self.limbs[1].setRect(cx - 10, cy - 10, 20, 16) # Torso
        self.limbs[2].setRect(cx - 18, cy - 8, 6, 14)   # Left arm
        self.limbs[3].setRect(cx + 12, cy - 8, 6, 14)   # Right arm
        self.limbs[4].setRect(cx - 8, cy + 8, 16, 16)   # Legs

    def tick(self, dt: float, signals: HudSignals) -> None:
        pass

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_limb)
        painter.drawText(self.rect_hdr, Qt.AlignmentFlag.AlignCenter, "CHROME-LIMB DIAGNOSTIC // NANOSUIT")
        for r in self.limbs:
            painter.drawRect(r)
