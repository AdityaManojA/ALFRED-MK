"""
Shared helpers for HUD slot visual tests (not a test module itself).

Provides a deterministic test palette (pri=red, acc=green, acc2=blue), an
offscreen render helper, and a pixel counter so tests can assert that a
paint() call actually drew in the expected colour and region.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QRectF, Qt  # noqa: E402
from PyQt6.QtGui import QImage, QPainter  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.hud.visuals.base import HudSignals  # noqa: E402
from core.ui.themes.schema import PaletteDefinition  # noqa: E402

# A full QApplication (not just QGuiApplication) so widget tests can share it.
app = QApplication.instance() or QApplication(sys.argv)

W, H = 240, 140
RECT = QRectF(0.0, 0.0, float(W), float(H))

_PALETTE_FIELDS = (
    "bg panel panel2 panel_bg border border_b border_a pri pri_dim pri_gho acc acc2 "
    "green green_d red muted muted_c text text_dim text_med text_bright white dark bar_bg"
).split()


def make_palette(**overrides: str) -> PaletteDefinition:
    """Palette where every token is black except pri=red, acc=green, acc2=blue, pri_dim=grey."""
    values = {name: "#000000" for name in _PALETTE_FIELDS}
    values.update(pri="#FF0000", acc="#00FF00", acc2="#0000FF", pri_dim="#808080")
    values.update(overrides)
    return PaletteDefinition(**values)


def render(visual, *, ticks: int = 3, dt: float = 0.05, signals: HudSignals | None = None,
           rect: QRectF = RECT, prepare: bool = True) -> QImage:
    """prepare() + tick() N times + paint() onto a black offscreen image; returns the image."""
    sig = signals or HudSignals()
    if prepare:
        visual.prepare(make_palette(), rect)
    for _ in range(ticks):
        visual.tick(dt, sig)
    img = QImage(int(rect.width()), int(rect.height()), QImage.Format.Format_RGBA8888)
    img.fill(Qt.GlobalColor.black)
    p = QPainter(img)
    try:
        visual.paint(p, rect)
    finally:
        p.end()
    return img


def count_pixels(img: QImage, channel: str, *, y_min: int = 0, y_max: int | None = None,
                 x_min: int = 0, x_max: int | None = None, threshold: int = 100) -> int:
    """Count pixels whose `channel` ('r'|'g'|'b') is >= threshold while the other two are < 60."""
    img = img.convertToFormat(QImage.Format.Format_RGBA8888)
    w, h = img.width(), img.height()
    y_max = h if y_max is None else y_max
    x_max = w if x_max is None else x_max
    bpl = img.bytesPerLine()
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    data = bytes(ptr)
    idx = {"r": 0, "g": 1, "b": 2}[channel]
    others = [i for i in (0, 1, 2) if i != idx]
    n = 0
    for y in range(max(0, y_min), min(h, y_max)):
        row = y * bpl
        for x in range(max(0, x_min), min(w, x_max)):
            o = row + x * 4
            if data[o + idx] >= threshold and data[o + others[0]] < 60 and data[o + others[1]] < 60:
                n += 1
    return n


def rect_tuple(r) -> tuple[float, float, float, float]:
    """(x, y, w, h) for a QRectF."""
    return (r.x(), r.y(), r.width(), r.height())


def line_tuple(line) -> tuple[float, float, float, float]:
    """(x1, y1, x2, y2) for a QLineF."""
    return (line.x1(), line.y1(), line.x2(), line.y2())
