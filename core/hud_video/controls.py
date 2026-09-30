"""
core/hud_video/controls.py — Tactical transport controls strip for the Visual HUD.

Features:
- Laid out below the video surface (not floating over it)
- [⏯] Play/Pause toggle
- [⟲] Replay button (always visible, highlights on ENDED)
- Custom-painted timeline scrubber (click to seek, drag scrubs with live time label, commits ON RELEASE ONLY)
- Live or unknown duration shows 'LIVE' and disables bar
- Prebuilt pens, brushes, and fonts (zero per-frame allocations in paintEvent)
- Keyboard shortcuts when focused: Space (toggle), Left/Right (skip 10s), Home (start)
- Repaints strictly on video_state_changed, and only while visible
"""

from __future__ import annotations

import math
from typing import Optional

from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPen, QBrush, QPainter, QKeyEvent, QMouseEvent, QPolygonF
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel, QSizePolicy

from core.hud_video.controller import HudVideoController
from core.hud_video.transport import (
    SKIP_S,
    VideoStatus,
    VideoState,
    format_timestamp,
    clamp_seek,
)

# ---------------------------------------------------------------------------
# Named Constants
# ---------------------------------------------------------------------------

STRIP_HEIGHT: int = 36               # Height of the bottom controls strip (px)
BTN_SIZE: int = 26                  # Width & height of square transport buttons (px)
TRACK_HEIGHT: float = 4.0           # Height of timeline bar track (px)
THUMB_RADIUS: float = 5.5           # Radius of timeline scrubber handle (px)
TIMELINE_MIN_WIDTH: int = 120       # Minimum width for scrubber bar (px)
TIME_LABEL_WIDTH: int = 95          # Fixed width for time readout (px)


# ---------------------------------------------------------------------------
# Custom-Painted Scrubber Timeline
# ---------------------------------------------------------------------------

class VideoTimeline(QWidget):
    """Custom-painted timeline scrubber.

    Zero per-frame allocations in paintEvent.
    Drags with live label and commits seek to player on release only.
    """

    def __init__(
        self,
        controller: HudVideoController,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(int(TRACK_HEIGHT + THUMB_RADIUS * 2 + 8))

        # Playback state cache
        self._position_s: float = 0.0
        self._duration_s: float = 0.0
        self._seekable: bool = False
        self._is_live: bool = False

        # Interaction state
        self._scrubbing: bool = False
        self._scrub_pos_s: float = 0.0
        self._hovered: bool = False

        # Prebuilt pens, brushes, and fonts (rebuilt only on theme change)
        self._pri_color = QColor("#00D4FF")
        self._pri_dim_color = QColor("#007A9A")
        self._bg_color = QColor("#000308")
        self._border_color = QColor("#222748")
        self._rect_track = QRectF()
        self._rect_fill = QRectF()
        self._pt_thumb = QPointF()

        self._update_palette()

    def _update_palette(self) -> None:
        """Cache brushes and pens in _update_palette()."""
        self._pen_track_bg = QPen(self._pri_dim_color, 1.0)
        self._brush_track_bg = QBrush(QColor(16, 18, 34))
        self._brush_track_fg = QBrush(self._pri_color)
        self._pen_thumb_normal = QPen(QColor(255, 255, 255), 1.5)
        self._brush_thumb_normal = QBrush(self._pri_color)
        self._brush_thumb_hover = QBrush(QColor("#00FFFF"))
        self._pen_live = QPen(QColor("#FF4466"), 1.0)
        self._brush_live = QBrush(QColor(255, 68, 102, 60))

    def apply_theme(self, pri: str, pri_dim: str, bg: str, text_dim: str) -> None:
        """Prebuild GDI pens and brushes when theme palette changes."""
        self._pri_color = QColor(pri)
        self._pri_dim_color = QColor(pri_dim)
        self._bg_color = QColor(bg)
        self._text_dim_color = QColor(text_dim)
        self._update_palette()
        if self.isVisible():
            self.update()

    def update_state(self, state: VideoState) -> None:
        """Called when video_state_changed is emitted. Only repaints if visible."""
        self._position_s = state.position_s
        self._duration_s = state.duration_s
        self._seekable = state.seekable
        self._is_live = (self._duration_s <= 0.0 and state.status == VideoStatus.PLAYING)

        # Repaint strictly while visible and not currently dragging
        if self.isVisible() and not self._scrubbing:
            self.update()

    @property
    def display_position_s(self) -> float:
        return self._scrub_pos_s if self._scrubbing else self._position_s

    # ------------------------------------------------------------------
    # Mouse Events
    # ------------------------------------------------------------------

    def _x_to_seconds(self, x: float) -> float:
        w = max(1.0, float(self.width() - THUMB_RADIUS * 2))
        pos_x = max(0.0, min(x - THUMB_RADIUS, w))
        pct = pos_x / w
        return pct * max(0.0, self._duration_s)

    def enterEvent(self, event) -> None:
        self._hovered = True
        if self._seekable and not self._is_live:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._seekable and not self._is_live:
            self._scrubbing = True
            self._scrub_pos_s = self._x_to_seconds(event.position().x())
            self.update()
            # Inform parent strip to update live readout
            p = self.parentWidget()
            if hasattr(p, "update_time_label"):
                p.update_time_label(self._scrub_pos_s, self._duration_s)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._scrubbing and self._seekable and not self._is_live:
            self._scrub_pos_s = self._x_to_seconds(event.position().x())
            self.update()
            p = self.parentWidget()
            if hasattr(p, "update_time_label"):
                p.update_time_label(self._scrub_pos_s, self._duration_s)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._scrubbing:
            self._scrubbing = False
            # Commit seek to player on release only!
            target = self._x_to_seconds(event.position().x())
            self._controller.seek(target)
            self.update()
            p = self.parentWidget()
            if hasattr(p, "update_time_label"):
                p.update_time_label(target, self._duration_s)
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------
    # Keyboard Events (focus shortcuts)
    # ------------------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        k = event.key()
        if k == Qt.Key.Key_Space:
            self._controller.toggle()
            event.accept()
            return
        elif k == Qt.Key.Key_Left:
            self._controller.seek_rel(-SKIP_S)
            event.accept()
            return
        elif k == Qt.Key.Key_Right:
            self._controller.seek_rel(+SKIP_S)
            event.accept()
            return
        elif k == Qt.Key.Key_Home:
            self._controller.seek(0.0)
            event.accept()
            return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Paint (Zero per-frame allocations)
    # ------------------------------------------------------------------

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        W = float(self.width())
        H = float(self.height())
        track_y = (H - TRACK_HEIGHT) / 2.0
        track_w = max(1.0, W - THUMB_RADIUS * 2.0)
        track_x = THUMB_RADIUS

        self._rect_track.setRect(track_x, track_y, track_w, TRACK_HEIGHT)

        # 1. Background channel groove
        p.setPen(self._pen_track_bg)
        p.setBrush(self._brush_track_bg)
        p.drawRoundedRect(self._rect_track, 2.0, 2.0)

        # 2. Live or unseekable fallback
        if self._is_live or not self._seekable or self._duration_s <= 0.0:
            p.setPen(self._pen_live)
            p.setBrush(self._brush_live)
            p.drawRoundedRect(self._rect_track, 2.0, 2.0)
            p.end()
            return

        # 3. Active progress bar
        current = self._scrub_pos_s if self._scrubbing else self._position_s
        progress = max(0.0, min(1.0, current / self._duration_s))
        fill_w = track_w * progress

        if fill_w > 0:
            self._rect_fill.setRect(track_x, track_y, fill_w, TRACK_HEIGHT)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(self._brush_track_fg)
            p.drawRoundedRect(self._rect_fill, 2.0, 2.0)

        # 4. Scrubber thumb handle
        thumb_cx = track_x + fill_w
        thumb_cy = H / 2.0

        p.setPen(self._pen_thumb_normal)
        p.setBrush(self._brush_thumb_hover if (self._hovered or self._scrubbing) else self._brush_thumb_normal)
        self._pt_thumb.setX(thumb_cx)
        self._pt_thumb.setY(thumb_cy)
        p.drawEllipse(self._pt_thumb, THUMB_RADIUS, THUMB_RADIUS)

        p.end()


# ---------------------------------------------------------------------------
# Tactical Cyber Transport Button
# ---------------------------------------------------------------------------

class CyberTransportButton(QPushButton):
    """Square tactical button with hover glow and vector icon."""

    def __init__(self, mode: str = "play", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._mode = mode  # "play", "pause", "replay"
        self._highlighted = False
        self._hovered = False
        self._pressed = False
        self.setFixedSize(BTN_SIZE, BTN_SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._pri_color = QColor("#00D4FF")
        self._border_color = QColor("#222748")

        self._update_palette()

        self._rect_btn = QRectF(1, 1, BTN_SIZE - 2, BTN_SIZE - 2)
        self._rect_bar1 = QRectF()
        self._rect_bar2 = QRectF()
        self._tri_poly = QPolygonF()
        self._arrow_p1 = QPointF()
        self._arrow_p2 = QPointF()
        self._arrow_p3 = QPointF()
        self._arc_x = 0
        self._arc_y = 0
        self._arc_w = 0
        self._arc_h = 0
        self._update_geometry_cache()

    def _update_palette(self, pri: Optional[str] = None, border: Optional[str] = None) -> None:
        """Cache brushes and pens in _update_palette()."""
        if pri:
            self._pri_color = QColor(pri)
        if border:
            self._border_color = QColor(border)

        self._c_hl_bdr = QColor("#FFD166")
        self._c_hl_bg = QColor(255, 209, 102, 50)
        self._c_white = QColor("#FFFFFF")
        self._c_norm_bg = QColor(13, 15, 30, 180)
        self._c_hover_bg = QColor(self._pri_color.red(), self._pri_color.green(), self._pri_color.blue(), 40)
        self._c_press_bg = QColor(self._pri_color.red(), self._pri_color.green(), self._pri_color.blue(), 80)

        self._pen_hl_bdr = QPen(self._c_hl_bdr, 1.0)
        self._pen_pri_bdr = QPen(self._pri_color, 1.0)
        self._pen_norm_bdr = QPen(self._border_color, 1.0)

        self._pen_white_fg = QPen(self._c_white, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        self._pen_pri_fg = QPen(self._pri_color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        self._pen_arrow_white = QPen(self._c_white, 1.5)
        self._pen_arrow_pri = QPen(self._pri_color, 1.5)

        self._brush_white = QBrush(self._c_white)
        self._brush_pri = QBrush(self._pri_color)
        self._brush_hl_bg = QBrush(self._c_hl_bg)
        self._brush_norm_bg = QBrush(self._c_norm_bg)
        self._brush_hover_bg = QBrush(self._c_hover_bg)
        self._brush_press_bg = QBrush(self._c_press_bg)

    def apply_theme(self, pri: str, border: str) -> None:
        """Apply theme palette and rebuild cached pens and brushes."""
        self._update_palette(pri=pri, border=border)
        if self.isVisible():
            self.update()

    def _update_geometry_cache(self) -> None:
        cx = BTN_SIZE / 2.0
        cy = BTN_SIZE / 2.0
        r = 4.5
        self._tri_poly = QPolygonF([
            QPointF(cx - r * 0.7, cy - r),
            QPointF(cx + r * 1.0, cy),
            QPointF(cx - r * 0.7, cy + r),
        ])
        bw = 2.5
        bh = 9.0
        self._rect_bar1.setRect(cx - 4.5, cy - bh / 2.0, bw, bh)
        self._rect_bar2.setRect(cx + 2.0, cy - bh / 2.0, bw, bh)
        ar = 5.0
        self._arc_x = int(cx - ar)
        self._arc_y = int(cy - ar)
        self._arc_w = int(ar * 2)
        self._arc_h = int(ar * 2)
        self._arrow_p1 = QPointF(cx + 3.0, cy - 5.5)
        self._arrow_p2 = QPointF(cx + 5.5, cy - 3.0)
        self._arrow_p3 = QPointF(cx + 2.0, cy - 2.5)

    def set_mode(self, mode: str) -> None:
        if self._mode != mode:
            self._mode = mode
            self.update()

    def set_highlighted(self, hl: bool) -> None:
        if self._highlighted != hl:
            self._highlighted = hl
            self.update()

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._pressed = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._pressed = False
        self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # State-based selection of precomputed resources
        if self._highlighted:
            pen_bdr = self._pen_hl_bdr
            bg_brush = self._brush_hl_bg
            pen_fg = self._pen_white_fg
            brush_fg = self._brush_white
            pen_arrow = self._pen_arrow_white
        elif self._hovered:
            pen_bdr = self._pen_pri_bdr
            bg_brush = self._brush_press_bg if self._pressed else self._brush_hover_bg
            pen_fg = self._pen_white_fg
            brush_fg = self._brush_white
            pen_arrow = self._pen_arrow_white
        else:
            pen_bdr = self._pen_norm_bdr
            bg_brush = self._brush_press_bg if self._pressed else self._brush_norm_bg
            pen_fg = self._pen_pri_fg
            brush_fg = self._brush_pri
            pen_arrow = self._pen_arrow_pri

        # Background box
        p.fillRect(self._rect_btn, bg_brush)
        p.setPen(pen_bdr)
        p.drawRect(self._rect_btn)

        # Vector Icon
        p.setPen(pen_fg)

        if self._mode == "play":
            p.setBrush(brush_fg)
            p.drawPolygon(self._tri_poly)
        elif self._mode == "pause":
            p.setBrush(brush_fg)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(self._rect_bar1)
            p.drawRect(self._rect_bar2)
        elif self._mode == "replay":
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(self._arc_x, self._arc_y, self._arc_w, self._arc_h, 45 * 16, 280 * 16)
            p.setPen(pen_arrow)
            p.drawLine(self._arrow_p1, self._arrow_p2)
            p.drawLine(self._arrow_p2, self._arrow_p3)

        p.end()


# ---------------------------------------------------------------------------
# Controls Strip Widget (Placed strictly BELOW the video)
# ---------------------------------------------------------------------------

class HudVideoControlsStrip(QWidget):
    """Full transport strip laid out below the video surface.

    Contains:
    [Play/Pause ⏯] [Replay ⟲] [Timeline ──●────] [Time label 1:12 / 4:10]
    """

    def __init__(
        self,
        controller: HudVideoController,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self.setFixedHeight(STRIP_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        self.setStyleSheet("""
            HudVideoControlsStrip {
                background: #090a12;
                border-top: 1px solid #222748;
            }
        """)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 4, 10, 4)
        lay.setSpacing(8)

        # 1. Play / Pause Button
        self._play_btn = CyberTransportButton("play", self)
        self._play_btn.setToolTip("Toggle Play/Pause (Space)")
        self._play_btn.clicked.connect(self._controller.toggle)
        lay.addWidget(self._play_btn)

        # 2. Replay Button
        self._replay_btn = CyberTransportButton("replay", self)
        self._replay_btn.setToolTip("Replay from Start (Home)")
        self._replay_btn.clicked.connect(self._controller.replay)
        lay.addWidget(self._replay_btn)

        # 3. Custom Scrubber Timeline
        self._timeline = VideoTimeline(self._controller, self)
        lay.addWidget(self._timeline, stretch=1)

        # 4. Time Readout Label
        self._time_lbl = QLabel("0:00 / 0:00")
        self._time_lbl.setFixedWidth(TIME_LABEL_WIDTH)
        self._time_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        font = QFont("JetBrains Mono", 8, QFont.Weight.Bold)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._time_lbl.setFont(font)
        self._time_lbl.setStyleSheet("color: #8E9BFF; background: transparent;")
        lay.addWidget(self._time_lbl)

    def _connect_signals(self) -> None:
        self._controller.video_state_changed.connect(self._on_video_state_changed)

    def _on_video_state_changed(self, state: VideoState) -> None:
        """Update buttons and timeline on state change. Only repaints when visible."""
        # 1. Update play/pause mode
        if state.status == VideoStatus.PLAYING:
            self._play_btn.set_mode("pause")
            self._replay_btn.set_highlighted(False)
        else:
            self._play_btn.set_mode("play")

        # 2. Highlight replay button on ENDED
        if state.status == VideoStatus.ENDED:
            self._replay_btn.set_highlighted(True)
        else:
            self._replay_btn.set_highlighted(False)

        # 3. Update timeline
        self._timeline.update_state(state)

        # 4. Update time label
        if not self._timeline._scrubbing:
            self.update_time_label(state.position_s, state.duration_s, state.status)

    def update_time_label(
        self,
        position_s: float,
        duration_s: float,
        status: VideoStatus = VideoStatus.PLAYING,
    ) -> None:
        if duration_s <= 0.0:
            if status == VideoStatus.PLAYING:
                self._time_lbl.setText("● LIVE")
                self._time_lbl.setStyleSheet("color: #FF4466; font-weight: bold;")
            else:
                self._time_lbl.setText("--:-- / --:--")
                self._time_lbl.setStyleSheet("color: #707AB0;")
            return

        cur_str = format_timestamp(position_s)
        dur_str = format_timestamp(duration_s)
        self._time_lbl.setText(f"{cur_str} / {dur_str}")
        self._time_lbl.setStyleSheet("color: #8E9BFF;")

    def apply_theme(self, pri: str, pri_dim: str, bg: str, text_dim: str) -> None:
        """Propagate theme updates to child elements."""
        self._timeline.apply_theme(pri, pri_dim, bg, text_dim)
        self._time_lbl.setStyleSheet(f"color: {pri};")
        self.setStyleSheet(f"""
            HudVideoControlsStrip {{
                background: {bg};
                border-top: 1px solid {pri_dim};
            }}
        """)
