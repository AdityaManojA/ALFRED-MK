"""
core/hud/datagrid/grid.py — 2x2 Developer / Power-User Telemetry Data Grid Widget.
Positions below Slot 3. Repaints only when formatted string values change.
"""
from __future__ import annotations

from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from core.hud.datagrid.providers import DataGridWorker, GridDataSnapshot
from core.ui.themes import ThemeChrome
from core.ui.themes.schema import PaletteDefinition


class DeveloperDataGridWidget(QWidget):
    """
    2x2 Developer Telemetry Grid:
    ┌───────────────────────┬───────────────────────┐
    │ GIT                   │ PORTS                 │
    │ main • clean          │ 11434 · 8000          │
    ├───────────────────────┼───────────────────────┤
    │ TOP PROC              │ SESSION               │
    │ python.exe • 185 MB   │ 00:14:22 • 12.4k tok  │
    └───────────────────────┴───────────────────────┘
    """
    _snapshot_updated = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(92)
        self.snapshot = GridDataSnapshot()
        self._cached_cells = ("", "", "", "")

        self._snapshot_updated.connect(self._apply_snapshot)
        self.worker = DataGridWorker.instance(self._on_worker_update)
        self.worker.start()

    def dispose(self) -> None:
        """Stop background worker if needed."""
        pass


    def _on_worker_update(self, snap: GridDataSnapshot) -> None:
        self._snapshot_updated.emit(snap)

    def _apply_snapshot(self, snap: GridDataSnapshot) -> None:
        new_cells = (snap.git_text, snap.ports_text, snap.proc_text, snap.session_text)
        if new_cells != self._cached_cells:
            self._cached_cells = new_cells
            self.snapshot = snap
            if self.isVisible():
                self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = float(self.width()), float(self.height())

        pal = ThemeChrome.get_active().palette
        c_bg = QColor(pal.panel)
        c_border = QColor(pal.border_a)
        c_pri = QColor(pal.pri)
        c_dim = QColor(pal.text_dim)
        c_warn = QColor(pal.acc2 or pal.acc)
        c_white = QColor(pal.text_bright or pal.white)

        def get_state_color(state: str) -> QColor:
            if state == "accent":
                return c_pri
            elif state == "warn":
                return c_warn
            return c_dim

        # Frame backplate
        p.fillRect(QRectF(1, 1, W - 2, H - 2), c_bg)
        p.setPen(QPen(c_border, 1.0))
        p.drawRect(QRectF(1, 1, W - 2, H - 2))

        # Grid dividing lines
        mid_x = W / 2.0
        mid_y = H / 2.0
        p.drawLine(QLineF(mid_x, 4.0, mid_x, H - 4.0))
        p.drawLine(QLineF(4.0, mid_y, W - 4.0, mid_y))

        f_lbl = QFont("Consolas", 6, QFont.Weight.Bold)
        f_val = QFont("Consolas", 7, QFont.Weight.DemiBold)

        # 1. GIT (Top-Left)
        p.setFont(f_lbl)
        p.setPen(c_dim)
        p.drawText(QRectF(6, 4, mid_x - 10, 12), Qt.AlignmentFlag.AlignLeft, "GIT BRANCH // STATUS")
        p.setFont(f_val)
        p.setPen(get_state_color(self.snapshot.git_state))
        p.drawText(QRectF(6, 18, mid_x - 10, 16), Qt.AlignmentFlag.AlignLeft, self.snapshot.git_text)

        # 2. PORTS (Top-Right)
        p.setFont(f_lbl)
        p.setPen(c_dim)
        p.drawText(QRectF(mid_x + 6, 4, mid_x - 10, 12), Qt.AlignmentFlag.AlignLeft, "LISTENING PORTS")
        p.setFont(f_val)
        p.setPen(get_state_color(self.snapshot.ports_state))
        p.drawText(QRectF(mid_x + 6, 18, mid_x - 10, 16), Qt.AlignmentFlag.AlignLeft, self.snapshot.ports_text)

        # 3. TOP PROC (Bottom-Left)
        p.setFont(f_lbl)
        p.setPen(c_dim)
        p.drawText(QRectF(6, mid_y + 4, mid_x - 10, 12), Qt.AlignmentFlag.AlignLeft, "TOP RES PROCESS")
        p.setFont(f_val)
        p.setPen(get_state_color(self.snapshot.proc_state))
        p.drawText(QRectF(6, mid_y + 18, mid_x - 10, 16), Qt.AlignmentFlag.AlignLeft, self.snapshot.proc_text)

        # 4. SESSION (Bottom-Right)
        p.setFont(f_lbl)
        p.setPen(c_dim)
        p.drawText(QRectF(mid_x + 6, mid_y + 4, mid_x - 10, 12), Qt.AlignmentFlag.AlignLeft, "SESSION TELEMETRY")
        p.setFont(f_val)
        p.setPen(get_state_color(self.snapshot.session_state))
        p.drawText(QRectF(mid_x + 6, mid_y + 18, mid_x - 10, 16), Qt.AlignmentFlag.AlignLeft, self.snapshot.session_text)
