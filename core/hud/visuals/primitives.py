"""
core/hud/visuals/primitives.py — Shared, zero-allocation visual primitives.
Includes:
- Wireframe3D (rotatable vertex/edge geometry projected with zero allocations in paint)
- RadarSweep (blip tracking with ping fading and reticles)
- BarArray (vertical frequency analyzer / spectrum with peak hold and decay)
- WaveTrace (fixed ring buffer trace)
- SilhouetteInterp (polygon keyframe interpolation)
"""
from __future__ import annotations

import math
from typing import List, Tuple

from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen

from core.hud.visuals.base import fast_cos, fast_sin


class Wireframe3D:
    """
    Zero-allocation 3D wireframe projection.
    Precomputes vertices and edge indices; applies yaw/pitch/roll rotations on tick.
    """

    def __init__(self, vertices: list[tuple[float, float, float]], edges: list[tuple[int, int]]):
        self.raw_vertices = tuple(vertices)
        self.edges = tuple(edges)
        self.transformed_points = [QPointF(0.0, 0.0) for _ in self.raw_vertices]
        self.edge_lines = [QLineF(0.0, 0.0, 0.0, 0.0) for _ in self.edges]
        self.yaw: float = 0.0
        self.pitch: float = 0.0
        self.roll: float = 0.0
        self.scale: float = 1.0
        self.cx: float = 0.0
        self.cy: float = 0.0

    def update_geometry(self, cx: float, cy: float, scale: float, yaw: float, pitch: float, roll: float = 0.0) -> None:
        self.cx = cx
        self.cy = cy
        self.scale = scale
        self.yaw = yaw
        self.pitch = pitch
        self.roll = roll

        cyaw, syaw = fast_cos(yaw), fast_sin(yaw)
        cpitch, spitch = fast_cos(pitch), fast_sin(pitch)
        croll, sroll = fast_cos(roll), fast_sin(roll)

        for i, (x, y, z) in enumerate(self.raw_vertices):
            # Yaw (Y-axis)
            x1 = x * cyaw + z * syaw
            y1 = y
            z1 = -x * syaw + z * cyaw

            # Pitch (X-axis)
            x2 = x1
            y2 = y1 * cpitch - z1 * spitch
            z2 = y1 * spitch + z1 * cpitch

            # Roll (Z-axis)
            x3 = x2 * croll - y2 * sroll
            y3 = x2 * sroll + y2 * croll

            # Perspective weak projection
            pz = 1.0 + (z2 * 0.002)
            px = cx + (x3 * scale) / pz
            py = cy + (y3 * scale) / pz

            self.transformed_points[i].setX(px)
            self.transformed_points[i].setY(py)

        for idx, (e1, e2) in enumerate(self.edges):
            p1 = self.transformed_points[e1]
            p2 = self.transformed_points[e2]
            self.edge_lines[idx].setLine(p1.x(), p1.y(), p2.x(), p2.y())

    def draw(self, painter: QPainter, pen: QPen) -> None:
        painter.setPen(pen)
        painter.drawLines(self.edge_lines)


class RadarSweep:
    """
    Tactical rotating radar reticle with blips and persistence fading.
    """

    def __init__(self, max_blips: int = 12):
        self.angle: float = 0.0
        self.sweep_line = QLineF(0.0, 0.0, 0.0, 0.0)
        self.blip_x = [0.0] * max_blips
        self.blip_y = [0.0] * max_blips
        self.blip_alpha = [0.0] * max_blips
        self.blip_size = [2.0] * max_blips
        self.max_blips = max_blips

    def tick(self, dt: float, speed_rad_per_s: float = 1.8) -> None:
        self.angle = (self.angle + speed_rad_per_s * dt) % (2.0 * math.pi)
        for i in range(self.max_blips):
            if self.blip_alpha[i] > 0.0:
                self.blip_alpha[i] = max(0.0, self.blip_alpha[i] - dt * 0.8)

    def trigger_blip(self, idx: int, x: float, y: float, size: float = 3.0, alpha: float = 1.0) -> None:
        if 0 <= idx < self.max_blips:
            self.blip_x[idx] = x
            self.blip_y[idx] = y
            self.blip_size[idx] = size
            self.blip_alpha[idx] = alpha

    def update_sweep_line(self, cx: float, cy: float, radius: float) -> None:
        sa = fast_sin(self.angle)
        ca = fast_cos(self.angle)
        self.sweep_line.setLine(cx, cy, cx + ca * radius, cy + sa * radius)


class BarArray:
    """
    Spectrum analyzer / segmented gauge with peak hold and decay.
    """

    def __init__(self, count: int = 16, peak_decay_per_s: float = 1.4):
        self.count = count
        self.values = [0.0] * count
        self.peaks = [0.0] * count
        self.peak_decay_per_s = peak_decay_per_s
        self.rects = [QRectF(0, 0, 0, 0) for _ in range(count)]
        self.peak_lines = [QLineF(0, 0, 0, 0) for _ in range(count)]

    def tick(self, dt: float, new_values: list[float] | tuple[float, ...]) -> None:
        for i in range(min(self.count, len(new_values))):
            target = max(0.0, min(1.0, float(new_values[i])))
            # Smooth follow
            self.values[i] += (target - self.values[i]) * min(1.0, dt * 14.0)
            if self.values[i] > self.peaks[i]:
                self.peaks[i] = self.values[i]
            else:
                self.peaks[i] = max(0.0, self.peaks[i] - self.peak_decay_per_s * dt)

    def layout(self, x0: float, y0: float, width: float, height: float, gap: float = 2.0) -> None:
        total_gaps = gap * (self.count - 1)
        bar_w = max(1.0, (width - total_gaps) / self.count)
        for i in range(self.count):
            bx = x0 + i * (bar_w + gap)
            bh = height * self.values[i]
            by = y0 + height - bh
            self.rects[i].setRect(bx, by, bar_w, max(1.0, bh))
            pk_y = y0 + height - (height * self.peaks[i])
            self.peak_lines[i].setLine(bx, pk_y, bx + bar_w, pk_y)


class WaveTrace:
    """
    Fixed ring buffer oscilloscope / acoustic vibration trace.
    """

    def __init__(self, sample_count: int = 64):
        self.sample_count = sample_count
        self.samples = [0.0] * sample_count
        self.points = [QPointF(0.0, 0.0) for _ in range(sample_count)]
        self.lines = [QLineF(0.0, 0.0, 0.0, 0.0) for _ in range(sample_count - 1)]

    def update_samples(self, new_samples: list[float] | tuple[float, ...]) -> None:
        n = min(self.sample_count, len(new_samples))
        for i in range(n):
            self.samples[i] = float(new_samples[i])

    def layout(self, x0: float, cy: float, width: float, height_amp: float) -> None:
        step_x = width / max(1, self.sample_count - 1)
        for i in range(self.sample_count):
            px = x0 + i * step_x
            py = cy + self.samples[i] * height_amp
            self.points[i].setX(px)
            self.points[i].setY(py)

        for i in range(self.sample_count - 1):
            p1 = self.points[i]
            p2 = self.points[i + 1]
            self.lines[i].setLine(p1.x(), p1.y(), p2.x(), p2.y())
