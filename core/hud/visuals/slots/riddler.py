"""
core/hud/visuals/slots/riddler.py — Riddler Theme Visual Set:
- Slot 1: Cipher Matrix Sweep (rotating green question marks & glyph coordinate sweep)
- Slot 2: Paradox Logic Gates (circuit puzzle tree with logic node pulses)
- Slot 3: Maze Traversal Schematic (procedural wireframe labyrinth with navigating blip)
"""
from __future__ import annotations

import math
from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen

from core.hud.visuals.base import HudSignals, SlotVisual, fast_cos, fast_sin
from core.ui.themes.schema import PaletteDefinition


class RiddlerCipherVisual(SlotVisual):
    def __init__(self) -> None:
        super().__init__()
        self.t: float = 0.0
        self.pen_cipher = QPen()
        self.pen_dim = QPen()
        self.font_hdr = QFont("Consolas", 7, QFont.Weight.Bold)
        self.font_glyph = QFont("Consolas", 8, QFont.Weight.Bold)
        self.rect_inner = QRectF()
        self.glyphs = ["?", "§", "¿", "¶", "≠", "ø", "λ", "?"]

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        c_pri = QColor(palette.pri)
        c_acc = QColor(palette.acc)
        self.pen_cipher = QPen(c_pri, 1.2)
        self.pen_dim = QPen(QColor(c_pri.red(), c_pri.green(), c_pri.blue(), 50), 1.0)
        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 22.0, rect.width() - 16.0, rect.height() - 30.0
        self.rect_inner = QRectF(bx, by, bw, bh)

    def tick(self, dt: float, signals: HudSignals) -> None:
        self.t = (self.t + dt * (1.5 + signals.cpu_pct * 0.02)) % (2.0 * math.pi)

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_cipher)
        painter.drawText(QRectF(rect.x() + 8, rect.y() + 4, rect.width() - 16, 14),
                         Qt.AlignmentFlag.AlignLeft, "● ● ●  CIPHER MATRIX // ENIGMA")
        painter.setPen(self.pen_dim)
        painter.drawRect(self.rect_inner)

        painter.setFont(self.font_glyph)
        painter.setPen(self.pen_cipher)
        bx, by, bw, bh = self.rect_inner.x(), self.rect_inner.y(), self.rect_inner.width(), self.rect_inner.height()
        cols = 4
        rows = 2
        cw = bw / cols
        ch = bh / rows
        for r in range(rows):
            for c in range(cols):
                idx = (r * cols + c + int(self.t * 2.0)) % len(self.glyphs)
                gx = bx + c * cw + (cw / 2.0) - 4
                gy = by + r * ch + (ch / 2.0) + 4
                painter.drawText(int(gx), int(gy), self.glyphs[idx])


class RiddlerLogicGatesVisual(SlotVisual):
    def __init__(self) -> None:
        super().__init__()
        self.t: float = 0.0
        self.pen_gate = QPen()
        self.pen_pulse = QPen()
        self.font_hdr = QFont("Consolas", 6, QFont.Weight.Bold)
        self.rect_inner = QRectF()
        self.lines = [QLineF() for _ in range(6)]

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        c_pri = QColor(palette.pri)
        c_acc = QColor(palette.acc)
        self.pen_gate = QPen(c_pri, 1.2)
        self.pen_pulse = QPen(c_acc, 1.6)
        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 20.0, rect.width() - 16.0, rect.height() - 28.0
        self.rect_inner = QRectF(bx, by, bw, bh)
        cx, cy = bx + bw / 2.0, by + bh / 2.0

        # Logic gate tree
        self.lines[0].setLine(bx + 8, cy - 10, cx - 12, cy - 10)
        self.lines[1].setLine(bx + 8, cy + 10, cx - 12, cy + 10)
        self.lines[2].setLine(cx - 12, cy - 10, cx, cy)
        self.lines[3].setLine(cx - 12, cy + 10, cx, cy)
        self.lines[4].setLine(cx, cy, cx + 18, cy)
        self.lines[5].setLine(cx + 18, cy, bx + bw - 8, cy)

    def tick(self, dt: float, signals: HudSignals) -> None:
        self.t = (self.t + dt * 4.0) % (2.0 * math.pi)

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_gate)
        painter.drawText(QRectF(rect.x() + 8, rect.y() + 4, rect.width() - 16, 12),
                         Qt.AlignmentFlag.AlignCenter, "PARADOX LOGIC GATES // NAND")
        painter.drawLines(self.lines)


class RiddlerMazeVisual(SlotVisual):
    def __init__(self) -> None:
        super().__init__()
        self.t: float = 0.0
        self.pen_maze = QPen()
        self.pen_dot = QPen()
        self.brush_dot = QBrush()
        self.font_hdr = QFont("Consolas", 6, QFont.Weight.Bold)
        self.rect_inner = QRectF()
        self.maze_lines = [QLineF() for _ in range(8)]
        self.dot_pos = QPointF()

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        c_pri = QColor(palette.pri)
        c_acc = QColor(palette.acc)
        self.pen_maze = QPen(c_pri, 1.2)
        self.pen_dot = QPen(c_acc, 1.4)
        self.brush_dot = QBrush(c_acc)

        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 18.0, rect.width() - 16.0, rect.height() - 24.0
        self.rect_inner = QRectF(bx, by, bw, bh)
        cx, cy = bx + bw / 2.0, by + bh / 2.0

        # Labyrinth brackets
        self.maze_lines[0].setLine(cx - 24, cy - 14, cx + 24, cy - 14)
        self.maze_lines[1].setLine(cx - 24, cy - 14, cx - 24, cy + 14)
        self.maze_lines[2].setLine(cx - 24, cy + 14, cx + 24, cy + 14)
        self.maze_lines[3].setLine(cx + 24, cy - 14, cx + 24, cy - 4)
        self.maze_lines[4].setLine(cx + 24, cy + 4, cx + 24, cy + 14)
        self.maze_lines[5].setLine(cx - 12, cy - 6, cx + 12, cy - 6)
        self.maze_lines[6].setLine(cx - 12, cy - 6, cx - 12, cy + 6)
        self.maze_lines[7].setLine(cx - 12, cy + 6, cx + 12, cy + 6)

    def tick(self, dt: float, signals: HudSignals) -> None:
        self.t = (self.t + dt * 2.0) % (2.0 * math.pi)
        cx = self.rect_inner.x() + self.rect_inner.width() / 2.0
        cy = self.rect_inner.y() + self.rect_inner.height() / 2.0
        dx = cx + fast_cos(self.t) * 16.0
        dy = cy + fast_sin(self.t * 2.0) * 8.0
        self.dot_pos.setX(dx)
        self.dot_pos.setY(dy)

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_maze)
        painter.drawText(QRectF(rect.x() + 8, rect.y() + 3, rect.width() - 16, 12),
                         Qt.AlignmentFlag.AlignCenter, "MAZE TRAVERSAL SCHEMATIC")
        painter.drawLines(self.maze_lines)
        painter.setPen(self.pen_dot)
        painter.setBrush(self.brush_dot)
        painter.drawEllipse(self.dot_pos, 2.5, 2.5)
