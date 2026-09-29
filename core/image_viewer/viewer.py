"""
core/image_viewer/viewer.py — Image Viewer v2 (LAZY + FIT + FETCH).

Enforces:
- Top-level frameless window owned by MainWindow
- Layered below settings modals, toasts, and dropdowns
- Pure sizing via fit_size() without cropping or overflow
- Zero per-paint heap allocations (prescaled pixmaps, prebuilt pens/brushes)
- Letterboxing on resize preserving aspect ratio
- Host-only caption strip strictly below image (protecting privacy)
- Memory released on close (pixmap freed)
- Never auto-restored from saved geometry
"""

from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import Qt, QPoint, QRect, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QPixmap, QImage, QKeyEvent, QScreen
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.image_viewer.fit import fit_size, VIEWER_MIN_PX
from core.hud_video.layering import Z_VISUAL_HUD, Z_HUD_BUTTONS, make_frameless_overlay, raise_overlay

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named Constants
# ---------------------------------------------------------------------------
Z_IMAGE_VIEWER: int = 15
VIEWER_HEADER_H: int = 34
VIEWER_CAPTION_H: int = 28
VIEWER_BORDER_PX: int = 1

# Color Tokens
C_BG: str = "#000308"
C_PANEL: str = "#050b14"
C_PRI: str = "#00D4FF"
C_PRI_DIM: str = "#007A9A"
C_TEXT_DIM: str = "#405060"
C_WHITE: str = "#FFFFFF"


class _ImageCanvas(QWidget):
    """Custom-painted canvas that draws a prescaled pixmap letterboxed in the center."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

        # Prebuilt painting tools (zero allocations in paintEvent)
        self._bg_brush = QBrush(QColor(C_BG))
        self._bg_pen = QPen(Qt.PenStyle.NoPen)
        self._border_pen = QPen(QColor(C_PRI_DIM))
        self._border_pen.setWidth(1)

        self._raw_image: QImage | None = None
        self._cached_pixmap: QPixmap | None = None
        self._cached_size: tuple[int, int] = (0, 0)
        self._aspect_ratio: float = 1.0

    def set_image(self, image: QImage) -> None:
        """Assign raw QImage and invalidate cached pixmap."""
        self._raw_image = image
        if not image.isNull() and image.width() > 0 and image.height() > 0:
            self._aspect_ratio = float(image.width()) / float(image.height())
        else:
            self._aspect_ratio = 1.0
        self._cached_pixmap = None
        self._cached_size = (0, 0)
        self._update_cached_pixmap()
        self.update()

    def clear(self) -> None:
        """Release image memory immediately."""
        self._raw_image = None
        self._cached_pixmap = None
        self._cached_size = (0, 0)
        self.update()

    def _update_cached_pixmap(self) -> None:
        """Prescale pixmap on load or resize only."""
        if self._raw_image is None or self._raw_image.isNull():
            self._cached_pixmap = None
            return

        cw = max(1, self.width())
        ch = max(1, self.height())
        if self._cached_size == (cw, ch) and self._cached_pixmap is not None:
            return

        # Calculate letterbox dimensions
        canvas_aspect = float(cw) / float(ch)
        if self._aspect_ratio > canvas_aspect:
            # Constrained by width
            draw_w = cw
            draw_h = max(1, int(round(cw / self._aspect_ratio)))
        else:
            # Constrained by height
            draw_h = ch
            draw_w = max(1, int(round(ch * self._aspect_ratio)))

        dpr = self.devicePixelRatio()
        scaled = self._raw_image.scaled(
            int(draw_w * dpr),
            int(draw_h * dpr),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        scaled.setDevicePixelRatio(dpr)
        self._cached_pixmap = QPixmap.fromImage(scaled)
        self._cached_size = (cw, ch)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_cached_pixmap()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        w, h = self.width(), self.height()

        # 1. Fill solid background
        painter.setPen(self._bg_pen)
        painter.setBrush(self._bg_brush)
        painter.drawRect(0, 0, w, h)

        # 2. Draw centered letterboxed pixmap
        if self._cached_pixmap is not None and not self._cached_pixmap.isNull():
            pm = self._cached_pixmap
            dpr = pm.devicePixelRatio() or 1.0
            pw = int(pm.width() / dpr)
            ph = int(pm.height() / dpr)
            px = max(0, (w - pw) // 2)
            py = max(0, (h - ph) // 2)
            painter.drawPixmap(px, py, pm)

        painter.end()


class ImageViewerWindow(QWidget):
    """Top-level, frameless, aspect-ratio-fitted reference image viewer."""

    closed = pyqtSignal()
    next_requested = pyqtSignal()
    prev_requested = pyqtSignal()
    show_requested = pyqtSignal(object, str, str, str)  # (source, caption, host, candidate_info)
    close_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        make_frameless_overlay(self, parent)

        self._drag_pos: QPoint | None = None
        self._native_size: tuple[int, int] = (0, 0)

        # Prebuilt fonts
        self._font_title = QFont("Consolas", 8, QFont.Weight.Bold)
        self._font_btn = QFont("Consolas", 8)
        self._font_caption = QFont("Consolas", 7)

        # Connect thread marshalling signals
        self.show_requested.connect(self.show_image)
        self.close_requested.connect(self.close_viewer)

        self._build_ui()
        self.hide()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(1, 1, 1, 1)
        root.setSpacing(0)

        self.setStyleSheet(f"""
            ImageViewerWindow {{
                background: {C_BG};
                border: 1px solid {C_PRI_DIM};
                border-radius: 3px;
            }}
        """)

        # 1. Header Bar
        header = QFrame(self)
        header.setFixedHeight(VIEWER_HEADER_H)
        header.setStyleSheet(f"background: {C_PANEL}; border-bottom: 1px solid {C_PRI_DIM};")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(10, 0, 8, 0)
        h_lay.setSpacing(6)

        self._title_lbl = QLabel("◈  IMAGE VIEWER")
        self._title_lbl.setFont(self._font_title)
        self._title_lbl.setStyleSheet(f"color: {C_PRI}; background: transparent; letter-spacing: 1.5px;")
        h_lay.addWidget(self._title_lbl)

        h_lay.addStretch()

        self._prev_btn = QPushButton("❮")
        self._prev_btn.setFont(self._font_btn)
        self._prev_btn.setFixedSize(24, 22)
        self._prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._prev_btn.setToolTip("Previous candidate image [P]")
        self._prev_btn.setStyleSheet(f"""
            QPushButton {{ color: {C_TEXT_DIM}; background: transparent; border: 1px solid {C_TEXT_DIM}; border-radius: 2px; }}
            QPushButton:hover {{ color: {C_PRI}; border-color: {C_PRI}; }}
        """)
        self._prev_btn.clicked.connect(self.prev_requested.emit)
        h_lay.addWidget(self._prev_btn)

        self._next_btn = QPushButton("❯")
        self._next_btn.setFont(self._font_btn)
        self._next_btn.setFixedSize(24, 22)
        self._next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._next_btn.setToolTip("Next candidate image [N]")
        self._next_btn.setStyleSheet(f"""
            QPushButton {{ color: {C_TEXT_DIM}; background: transparent; border: 1px solid {C_TEXT_DIM}; border-radius: 2px; }}
            QPushButton:hover {{ color: {C_PRI}; border-color: {C_PRI}; }}
        """)
        self._next_btn.clicked.connect(self.next_requested.emit)
        h_lay.addWidget(self._next_btn)

        self._close_btn = QPushButton("✕")
        self._close_btn.setFont(self._font_btn)
        self._close_btn.setFixedSize(24, 22)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setToolTip("Close viewer [Esc]")
        self._close_btn.setStyleSheet(f"""
            QPushButton {{ color: {C_TEXT_DIM}; background: transparent; border: none; }}
            QPushButton:hover {{ color: #FF4444; }}
        """)
        self._close_btn.clicked.connect(self.close_viewer)
        h_lay.addWidget(self._close_btn)

        root.addWidget(header, stretch=0)

        # 2. Image Canvas Area
        self._canvas = _ImageCanvas(self)
        root.addWidget(self._canvas, stretch=1)

        # 3. Caption Strip (strictly below image, never floating over it)
        caption_bar = QFrame(self)
        caption_bar.setFixedHeight(VIEWER_CAPTION_H)
        caption_bar.setStyleSheet(f"background: {C_PANEL}; border-top: 1px solid {C_PRI_DIM};")
        c_lay = QHBoxLayout(caption_bar)
        c_lay.setContentsMargins(10, 0, 10, 0)
        c_lay.setSpacing(6)

        self._host_lbl = QLabel("")
        self._host_lbl.setFont(self._font_caption)
        self._host_lbl.setStyleSheet(f"color: {C_PRI}; background: transparent;")
        c_lay.addWidget(self._host_lbl)

        c_lay.addStretch()

        self._size_lbl = QLabel("")
        self._size_lbl.setFont(self._font_caption)
        self._size_lbl.setStyleSheet(f"color: {C_TEXT_DIM}; background: transparent;")
        c_lay.addWidget(self._size_lbl)

        root.addWidget(caption_bar, stretch=0)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_image(
        self,
        source: str | bytes | QImage,
        caption: str = "",
        host: str = "",
        candidate_info: str = "",
    ) -> bool:
        """Load, fit, position, and display an image."""
        qimg = QImage()
        if isinstance(source, QImage):
            qimg = source
        elif isinstance(source, bytes):
            qimg.loadFromData(source)
        elif isinstance(source, str):
            qimg.load(source)

        if qimg.isNull() or qimg.width() <= 0 or qimg.height() <= 0:
            log.warning("[ImageViewerWindow] failed to decode image")
            return False

        self._native_size = (qimg.width(), qimg.height())
        self._canvas.set_image(qimg)

        # Format host and attribution for caption (privacy-safe: host only)
        display_host = host or "Local File"
        if candidate_info:
            self._host_lbl.setText(f"◈  {display_host.upper()}  [{candidate_info}]")
        else:
            self._host_lbl.setText(f"◈  {display_host.upper()}")

        self._size_lbl.setText(f"{qimg.width()} × {qimg.height()} px")

        # Fit window to screen
        screen = self._target_screen()
        avail_geo = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)

        # Account for non-canvas chrome in sizing calculation
        chrome_h = VIEWER_HEADER_H + VIEWER_CAPTION_H + (VIEWER_BORDER_PX * 2)
        fit_w, fit_h = fit_size(
            qimg.width(),
            qimg.height(),
            avail_geo.width(),
            max(VIEWER_MIN_PX, avail_geo.height() - chrome_h),
        )

        total_w = fit_w + (VIEWER_BORDER_PX * 2)
        total_h = fit_h + chrome_h

        # Center on screen or anchor widget
        cx = avail_geo.x() + max(0, (avail_geo.width() - total_w) // 2)
        cy = avail_geo.y() + max(0, (avail_geo.height() - total_h) // 2)

        self.setGeometry(cx, cy, total_w, total_h)
        raise_overlay(self, self.parentWidget())
        return True

    def close_viewer(self) -> None:
        """Hide window and free pixmap resources immediately."""
        self.hide()
        self._canvas.clear()
        self._native_size = (0, 0)
        self.closed.emit()

    def clear_image(self) -> None:
        """Alias for freeing memory."""
        self._canvas.clear()

    # ------------------------------------------------------------------
    # Drag & Keyboard Handling
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.close_viewer()
            event.accept()
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_N):
            self.next_requested.emit()
            event.accept()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_P):
            self.prev_requested.emit()
            event.accept()
        else:
            super().keyPressEvent(event)

    def _target_screen(self) -> QScreen | None:
        """Return screen hosting parent or cursor."""
        parent = self.parentWidget()
        if parent is not None and parent.window():
            window_handle = parent.window().windowHandle()
            if window_handle and window_handle.screen():
                return window_handle.screen()
        return QApplication.primaryScreen()
