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

        # Pre-allocated static styles, fonts, colors, and pens
        self._font_lbl = QFont("Consolas", 6, QFont.Weight.Bold)
        self._font_val = QFont("Consolas", 7, QFont.Weight.DemiBold)
        self._cached_theme_name: str | None = None
        self._c_bg = QColor("#0c0d14")
        self._c_border = QColor("#222748")
        self._c_pri = QColor("#00D4FF")
        self._c_dim = QColor("#5A6588")
        self._c_warn = QColor("#FFD166")
        self._c_white = QColor("#FFFFFF")

        self._pen_border = QPen(self._c_border, 1.0)
        self._pen_dim = QPen(self._c_dim)
        self._pen_pri = QPen(self._c_pri)
        self._pen_warn = QPen(self._c_warn)

        self.prepare()

        # Cached layout rects
        self._rect_backplate = QRectF()
        self._rect_git_lbl = QRectF()
        self._rect_git_val = QRectF()
        self._rect_ports_lbl = QRectF()
        self._rect_ports_val = QRectF()
        self._rect_proc_lbl = QRectF()
        self._rect_proc_val = QRectF()
        self._rect_sess_lbl = QRectF()
        self._rect_sess_val = QRectF()
        self._mid_x = 0
        self._mid_y = 0
        self._w_int = 0
        self._h_int = 0

        self._snapshot_updated.connect(self._apply_snapshot)
        self.worker = DataGridWorker.instance(self._on_worker_update)
        self.worker.start()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        W, H = float(self.width()), float(self.height())
        self._w_int = int(W)
        self._h_int = int(H)
        mid_x = W / 2.0
        mid_y = H / 2.0
        self._mid_x = int(mid_x)
        self._mid_y = int(mid_y)

        self._rect_backplate.setRect(1, 1, W - 2, H - 2)
        self._rect_git_lbl.setRect(6, 4, mid_x - 10, 12)
        self._rect_git_val.setRect(6, 18, mid_x - 10, 16)
        self._rect_ports_lbl.setRect(mid_x + 6, 4, mid_x - 10, 12)
        self._rect_ports_val.setRect(mid_x + 6, 18, mid_x - 10, 16)
        self._rect_proc_lbl.setRect(6, mid_y + 4, mid_x - 10, 12)
        self._rect_proc_val.setRect(6, mid_y + 18, mid_x - 10, 16)
        self._rect_sess_lbl.setRect(mid_x + 6, mid_y + 4, mid_x - 10, 12)
        self._rect_sess_val.setRect(mid_x + 6, mid_y + 18, mid_x - 10, 16)

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

    def prepare(self) -> None:
        """Pre-allocate static QFont, QColor, and QPen instances."""
        self._update_theme_cache()

    def _update_theme_cache(self) -> None:
        active = ThemeChrome.get_active()
        t_name = getattr(active, "name", "")
        if self._cached_theme_name == t_name:
            return
        self._cached_theme_name = t_name
        pal = active.palette
        self._c_bg = QColor(pal.panel)
        self._c_border = QColor(pal.border_a)
        self._c_pri = QColor(pal.pri)
        self._c_dim = QColor(pal.text_dim)
        self._c_warn = QColor(pal.acc2 or pal.acc)
        self._c_white = QColor(pal.text_bright or pal.white)

        self._pen_border = QPen(self._c_border, 1.0)
        self._pen_dim = QPen(self._c_dim)
        self._pen_pri = QPen(self._c_pri)
        self._pen_warn = QPen(self._c_warn)

    def paintEvent(self, _):
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        self._update_theme_cache()

        pen_pri = self._pen_pri
        pen_warn = self._pen_warn
        pen_dim = self._pen_dim

        # Frame backplate
        p.fillRect(self._rect_backplate, self._c_bg)
        p.setPen(self._pen_border)
        p.drawRect(self._rect_backplate)

        # Grid dividing lines
        mid_x = self._mid_x
        mid_y = self._mid_y
        p.drawLine(mid_x, 4, mid_x, self._h_int - 4)
        p.drawLine(4, mid_y, self._w_int - 4, mid_y)

        # 1. GIT (Top-Left)
        p.setFont(self._font_lbl)
        p.setPen(pen_dim)
        p.drawText(self._rect_git_lbl, Qt.AlignmentFlag.AlignLeft, "GIT BRANCH // STATUS")
        p.setFont(self._font_val)
        git_st = self.snapshot.git_state
        p.setPen(pen_pri if git_st == "accent" else (pen_warn if git_st == "warn" else pen_dim))
        p.drawText(self._rect_git_val, Qt.AlignmentFlag.AlignLeft, self.snapshot.git_text)

        # 2. PORTS (Top-Right)
        p.setFont(self._font_lbl)
        p.setPen(pen_dim)
        p.drawText(self._rect_ports_lbl, Qt.AlignmentFlag.AlignLeft, "LISTENING PORTS")
        p.setFont(self._font_val)
        ports_st = self.snapshot.ports_state
        p.setPen(pen_pri if ports_st == "accent" else (pen_warn if ports_st == "warn" else pen_dim))
        p.drawText(self._rect_ports_val, Qt.AlignmentFlag.AlignLeft, self.snapshot.ports_text)

        # 3. TOP PROC (Bottom-Left)
        p.setFont(self._font_lbl)
        p.setPen(pen_dim)
        p.drawText(self._rect_proc_lbl, Qt.AlignmentFlag.AlignLeft, "TOP RES PROCESS")
        p.setFont(self._font_val)
        proc_st = self.snapshot.proc_state
        p.setPen(pen_pri if proc_st == "accent" else (pen_warn if proc_st == "warn" else pen_dim))
        p.drawText(self._rect_proc_val, Qt.AlignmentFlag.AlignLeft, self.snapshot.proc_text)

        # 4. SESSION (Bottom-Right)
        p.setFont(self._font_lbl)
        p.setPen(pen_dim)
        p.drawText(self._rect_sess_lbl, Qt.AlignmentFlag.AlignLeft, "SESSION TELEMETRY")
        p.setFont(self._font_val)
        sess_st = self.snapshot.session_state
        p.setPen(pen_pri if sess_st == "accent" else (pen_warn if sess_st == "warn" else pen_dim))
        p.drawText(self._rect_sess_val, Qt.AlignmentFlag.AlignLeft, self.snapshot.session_text)
