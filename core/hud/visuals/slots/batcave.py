"""
core/hud/visuals/slots/batcave.py — Reference Batcave Theme Visual Set:
- Slot 1: Orbital Bat-Satellite Radar (counter-rotating reticles, blips from CPU share, ping on alert_level)
- Slot 2: 16-Band Audio Spectrum Analyzer (peak-hold caps, real mic + sys audio drive)
- Slot 3: Batwing Vector Blueprint (rotating 3D wireframe + subsystem readouts)
"""
from __future__ import annotations

import math
from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen

from core.hud.visuals.base import HudSignals, SlotVisual, fast_cos, fast_sin
from core.hud.visuals.primitives import BarArray, RadarSweep, Wireframe3D
from core.ui.themes.schema import PaletteDefinition


# ── Slot 1: Orbital Bat-Satellite Radar ───────────────────────────────────────
class BatcaveRadarVisual(SlotVisual):
    def __init__(self) -> None:
        super().__init__()
        self.radar = RadarSweep(max_blips=8)
        self.reticle_angle1: float = 0.0
        self.reticle_angle2: float = 0.0
        self.pen_reticle = QPen()
        self.pen_sweep = QPen()
        self.pen_blip = QPen()
        self.brush_blip = QBrush()
        self.pen_grid = QPen()
        self.font_hdr = QFont("Consolas", 7, QFont.Weight.Bold)
        self.rect_inner = QRectF()
        self.rect_hdr = QRectF()
        self.center_pt = QPointF()
        self.crosshair_h = QLineF()
        self.crosshair_v = QLineF()
        self.cx: float = 0.0
        self.cy: float = 0.0
        self.radius: float = 0.0
        self.reticle_lines1: list[QLineF] = [QLineF() for _ in range(8)]
        self.reticle_lines2: list[QLineF] = [QLineF() for _ in range(8)]
        self.blip_points: list[QPointF] = [QPointF() for _ in range(self.radar.max_blips)]
        self.align_hdr: int = int(Qt.AlignmentFlag.AlignLeft)
        self.title_text: str = "● ● ●  ORBITAL RECON // RADAR"

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        c_pri = QColor(palette.pri)
        c_acc = QColor(palette.acc)
        c_dim = QColor(palette.pri_dim)
        c_bg = QColor(palette.bg)

        self.pen_reticle = QPen(c_dim, 1.0, Qt.PenStyle.DashLine)
        self.pen_sweep = QPen(c_pri, 1.4)
        self.pen_blip = QPen(c_acc, 1.2)
        self.brush_blip = QBrush(c_acc)
        self.pen_grid = QPen(QColor(c_pri.red(), c_pri.green(), c_pri.blue(), 40), 1.0)

        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 22.0, rect.width() - 16.0, rect.height() - 30.0
        self.rect_inner = QRectF(bx, by, bw, bh)
        self.cx = bx + bw / 2.0
        self.cy = by + bh / 2.0
        self.radius = min(bw, bh) * 0.42

        self.rect_hdr = QRectF(rect.x() + 8.0, rect.y() + 4.0, rect.width() - 16.0, 14.0)
        self.center_pt = QPointF(self.cx, self.cy)
        self.crosshair_h = QLineF(self.cx - self.radius, self.cy, self.cx + self.radius, self.cy)
        self.crosshair_v = QLineF(self.cx, self.cy - self.radius, self.cx, self.cy + self.radius)
        self.blip_points = [QPointF() for _ in range(self.radar.max_blips)]

    def tick(self, dt: float, signals: HudSignals) -> None:
        speed = 2.0 + (signals.alert_level * 1.5)
        self.radar.tick(dt, speed_rad_per_s=speed)
        self.reticle_angle1 = (self.reticle_angle1 + dt * 0.5) % (2.0 * math.pi)
        self.reticle_angle2 = (self.reticle_angle2 - dt * 0.7) % (2.0 * math.pi)
        self.radar.update_sweep_line(self.cx, self.cy, self.radius)

        # Trigger blip based on CPU load and proc count
        blip_r = (self.radius * 0.7) * (0.3 + signals.cpu_pct / 150.0)
        bx = self.cx + fast_cos(self.reticle_angle1 * 3.0) * blip_r
        by = self.cy + fast_sin(self.reticle_angle1 * 3.0) * blip_r
        self.radar.trigger_blip(0, bx, by, size=3.0 + signals.cpu_pct * 0.05, alpha=1.0)
        self.blip_points[0].setX(bx)
        self.blip_points[0].setY(by)

        # Precompute tick lines for reticles
        for i in range(8):
            ang1 = self.reticle_angle1 + (i * math.pi / 4.0)
            self.reticle_lines1[i].setLine(
                self.cx + fast_cos(ang1) * (self.radius - 4),
                self.cy + fast_sin(ang1) * (self.radius - 4),
                self.cx + fast_cos(ang1) * self.radius,
                self.cy + fast_sin(ang1) * self.radius,
            )
            ang2 = self.reticle_angle2 + (i * math.pi / 4.0)
            self.reticle_lines2[i].setLine(
                self.cx + fast_cos(ang2) * (self.radius * 0.6),
                self.cy + fast_sin(ang2) * (self.radius * 0.6),
                self.cx + fast_cos(ang2) * (self.radius * 0.6 + 4),
                self.cy + fast_sin(ang2) * (self.radius * 0.6 + 4),
            )

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        # Panel boundary & title
        painter.setPen(self.pen_grid)
        painter.drawRect(self.rect_inner)
        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_sweep)
        painter.drawText(self.rect_hdr, self.align_hdr, self.title_text)

        # Range rings
        painter.setPen(self.pen_grid)
        painter.drawEllipse(self.center_pt, self.radius, self.radius)
        painter.drawEllipse(self.center_pt, self.radius * 0.6, self.radius * 0.6)
        painter.drawEllipse(self.center_pt, self.radius * 0.25, self.radius * 0.25)

        # Crosshairs & Reticles
        painter.drawLine(self.crosshair_h)
        painter.drawLine(self.crosshair_v)
        painter.setPen(self.pen_reticle)
        painter.drawLines(self.reticle_lines1)
        painter.drawLines(self.reticle_lines2)

        # Sweep line
        painter.setPen(self.pen_sweep)
        painter.drawLine(self.radar.sweep_line)

        # Blips
        for i in range(self.radar.max_blips):
            if self.radar.blip_alpha[i] > 0.05:
                painter.setPen(self.pen_blip)
                painter.setBrush(self.brush_blip)
                sz = self.radar.blip_size[i]
                painter.drawEllipse(self.blip_points[i], sz, sz)
                painter.setBrush(Qt.BrushStyle.NoBrush)


# ── Slot 2: 16-Band Audio Spectrum ───────────────────────────────────────────
class BatcaveSpectrumVisual(SlotVisual):
    def __init__(self) -> None:
        super().__init__()
        self.bars = BarArray(count=16, peak_decay_per_s=1.2)
        self.pen_bar = QPen()
        self.brush_bar = QBrush()
        self.pen_peak = QPen()
        self.pen_border = QPen()
        self.font_hdr = QFont("Consolas", 6, QFont.Weight.Bold)
        self.rect_inner = QRectF()
        self.rect_hdr = QRectF()
        self.align_hdr: int = int(Qt.AlignmentFlag.AlignCenter)
        self.title_text: str = "16-BAND ACOUSTIC SPECTRUM // COWL"
        self.sim_values = [0.0] * 16

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        c_pri = QColor(palette.pri)
        c_acc = QColor(palette.acc2 or palette.acc)
        c_dim = QColor(palette.pri_dim)

        self.pen_bar = QPen(c_pri, 1.0)
        self.brush_bar = QBrush(c_pri)
        self.pen_peak = QPen(c_acc, 1.2)
        self.pen_border = QPen(QColor(c_pri.red(), c_pri.green(), c_pri.blue(), 50), 1.0)

        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 20.0, rect.width() - 16.0, rect.height() - 28.0
        self.rect_inner = QRectF(bx, by, bw, bh)
        self.rect_hdr = QRectF(rect.x() + 8.0, rect.y() + 4.0, rect.width() - 16.0, 12.0)
        self.bars.layout(bx + 4.0, by + 4.0, bw - 8.0, bh - 8.0, gap=3.0)

    def tick(self, dt: float, signals: HudSignals) -> None:
        base_level = max(signals.mic_level, signals.sys_audio_level)
        for i in range(16):
            # Synthesize 16-band EQ envelope off acoustic level + deterministic jitter
            factor = math.sin((i * 0.4) + (time_val := time_step(i))) * 0.35 + 0.65
            self.sim_values[i] = min(1.0, (base_level * factor * 1.5) + 0.05 * fast_sin(i * 1.2))
        self.bars.tick(dt, self.sim_values)

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        painter.setPen(self.pen_border)
        painter.drawRect(self.rect_inner)
        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_bar)
        painter.drawText(self.rect_hdr, self.align_hdr, self.title_text)

        painter.setBrush(self.brush_bar)
        for i in range(self.bars.count):
            painter.fillRect(self.bars.rects[i], self.brush_bar)
        painter.setPen(self.pen_peak)
        painter.drawLines(self.bars.peak_lines)


def time_step(i: int) -> float:
    return (i * 17) % 31 * 0.1


# ── Slot 3: Batwing Vector Blueprint ─────────────────────────────────────────
BATWING_VERTICES = [
    # Nose / Cockpit
    (0.0, -35.0, 0.0),
    (0.0, -10.0, 5.0),
    (-10.0, 5.0, 2.0),
    (10.0, 5.0, 2.0),
    # Wings
    (-45.0, -5.0, -2.0),
    (-55.0, 25.0, -4.0),
    (-30.0, 30.0, 0.0),
    (-15.0, 20.0, 3.0),
    (15.0, 20.0, 3.0),
    (30.0, 30.0, 0.0),
    (55.0, 25.0, -4.0),
    (45.0, -5.0, -2.0),
    # Tail / Engines
    (0.0, 25.0, 8.0),
]

BATWING_EDGES = [
    (0, 1), (1, 2), (1, 3), (2, 3),
    (0, 4), (4, 5), (5, 6), (6, 7), (7, 2),
    (0, 11), (11, 10), (10, 9), (9, 8), (8, 3),
    (7, 12), (8, 12), (1, 12),
]


class BatcaveBlueprintVisual(SlotVisual):
    def __init__(self) -> None:
        super().__init__()
        self.model = Wireframe3D(BATWING_VERTICES, BATWING_EDGES)
        self.yaw: float = 0.0
        self.pitch: float = math.radians(25.0)
        self.pen_wire = QPen()
        self.pen_border = QPen()
        self.font_hdr = QFont("Consolas", 6, QFont.Weight.Bold)
        self.font_tele = QFont("Consolas", 5, QFont.Weight.Normal)
        self.rect_inner = QRectF()
        self.rect_hdr = QRectF()
        self.rect_aero = QRectF()
        self.rect_vector = QRectF()
        self.align_center: int = int(Qt.AlignmentFlag.AlignCenter)
        self.align_left: int = int(Qt.AlignmentFlag.AlignLeft)
        self.align_right: int = int(Qt.AlignmentFlag.AlignRight)
        self.title_text: str = "BATWING MK-VIII BLUEPRINT // 3D"
        self.aero_text: str = "AERO: 99.4%"
        self.vector_text: str = "VECTOR: LOCK"
        self.cx: float = 0.0
        self.cy: float = 0.0

    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        c_pri = QColor(palette.pri)
        c_dim = QColor(palette.pri_dim)

        self.pen_wire = QPen(c_pri, 1.2)
        self.pen_border = QPen(QColor(c_pri.red(), c_pri.green(), c_pri.blue(), 50), 1.0)

        bx, by, bw, bh = rect.x() + 8.0, rect.y() + 18.0, rect.width() - 16.0, rect.height() - 24.0
        self.rect_inner = QRectF(bx, by, bw, bh)
        self.rect_hdr = QRectF(rect.x() + 8.0, rect.y() + 3.0, rect.width() - 16.0, 12.0)
        self.rect_aero = QRectF(self.rect_inner.x() + 4.0, self.rect_inner.bottom() - 12.0, 100.0, 10.0)
        self.rect_vector = QRectF(self.rect_inner.right() - 84.0, self.rect_inner.bottom() - 12.0, 80.0, 10.0)
        self.cx = bx + bw / 2.0
        self.cy = by + bh / 2.0

    def tick(self, dt: float, signals: HudSignals) -> None:
        # Rotation driven by CPU & system status
        self.yaw = (self.yaw + dt * (0.8 + signals.cpu_pct * 0.01)) % (2.0 * math.pi)
        self.model.update_geometry(self.cx, self.cy, scale=0.85, yaw=self.yaw, pitch=self.pitch)

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        painter.setPen(self.pen_border)
        painter.drawRect(self.rect_inner)
        painter.setFont(self.font_hdr)
        painter.setPen(self.pen_wire)
        painter.drawText(self.rect_hdr, self.align_center, self.title_text)

        # 3D Mesh
        self.model.draw(painter, self.pen_wire)

        # Micro telemetry
        painter.setFont(self.font_tele)
        painter.drawText(self.rect_aero, self.align_left, self.aero_text)
        painter.drawText(self.rect_vector, self.align_right, self.vector_text)
