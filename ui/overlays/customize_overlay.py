"""
ui/overlays/customize_overlay.py — Persona, vocal profiles, and chromatic customization overlay.
"""
from __future__ import annotations

import math
import threading
from pathlib import Path
from typing import Any, Callable

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QConicalGradient,
    QFont,
    QPainter,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui import (
    C,
    DEFAULT_UI_COLOR,
    TacticalHoverHelpManager,
    _scaled_icon_pixmap,
    attach_hover_help,
    get_available_app_icons,
    mono_font,
    qcol,
    tech_font,
)


class HueWheel(QWidget):
    """Circular colour picker.

    The user drags the handle (small white circle) around the wheel to choose
    from ALL hues. The filled circle in the centre is a live preview of the
    selected colour.
    """

    hue_picked = pyqtSignal(str)     # while dragging (live)
    hue_committed = pyqtSignal(str)  # when the handle is released

    _RING = 16   # ring thickness (px)

    def __init__(self, initial_hex: str = DEFAULT_UI_COLOR, parent=None):
        super().__init__(parent)
        self.setFixedSize(148, 148)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hue = 0.53
        self._drag = False
        self.set_color(initial_hex)

    # ── API ──────────────────────────────────────────────────────────────────
    def color(self) -> str:
        return QColor.fromHsvF(self._hue, 1.0, 1.0).name()

    def set_color(self, hex_str: str):
        c = QColor((hex_str or "").strip())
        if c.isValid() and c.hsvHueF() >= 0:
            self._hue = c.hsvHueF()
            self.update()

    # ── geometry helpers ─────────────────────────────────────────────────────
    def _ring_rect(self) -> QRectF:
        m = self._RING / 2 + 3
        return QRectF(self.rect()).adjusted(m, m, -m, -m)

    def _hue_from_pos(self, pos: QPointF) -> float:
        c = QRectF(self.rect()).center()
        dx = pos.x() - c.x()
        dy = c.y() - pos.y()          # screen y goes down — flip to math axis
        ang = math.atan2(dy, dx)      # [-π, π], counter-clockwise
        return (ang / (2 * math.pi)) % 1.0

    # ── drawing ──────────────────────────────────────────────────────────────
    def paintEvent(self, _):
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self._ring_rect()
        center = rect.center()

        grad = QConicalGradient(center, 0)
        for i in range(0, 361, 20):
            grad.setColorAt(i / 360.0, QColor.fromHsvF((i % 360) / 360.0, 1.0, 1.0))
        p.setPen(QPen(QBrush(grad), self._RING))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(rect)

        # centre preview circle
        preview = QColor.fromHsvF(self._hue, 1.0, 1.0)
        p.setPen(QPen(qcol(C.BORDER_B), 1))
        p.setBrush(QBrush(preview))
        # draggable handle
        r = rect.width() / 2
        ang = self._hue * 2 * math.pi
        hx = center.x() + r * math.cos(ang)
        hy = center.y() - r * math.sin(ang)
        p.setPen(QPen(QColor("#00060a"), 2))
        p.setBrush(QBrush(QColor("#ffffff")))
        p.drawEllipse(QPointF(hx, hy), 7.5, 7.5)
        p.end()

    # ── mouse events ─────────────────────────────────────────────────────────
    def mousePressEvent(self, e):
        self._drag = True
        self._hue = self._hue_from_pos(e.position())
        self.update()
        self.hue_picked.emit(self.color())

    def mouseMoveEvent(self, e):
        if self._drag:
            self._hue = self._hue_from_pos(e.position())
            self.update()
            self.hue_picked.emit(self.color())

    def mouseReleaseEvent(self, e):
        if self._drag:
            self._drag = False
            self.hue_committed.emit(self.color())


class CustomizeOverlay(QWidget):
    """Floating glassmorphic overlay for configuring Assistant Persona,
    Commander Designation, Vocal Profile, and Chromatic Matrix.
    Built with a responsive, scrollable core so controls never clip on any display.
    """
    saved = pyqtSignal(str, str, str, str)   # assistant_name, user_name, ui_color, voice
    setup_api_requested = pyqtSignal()
    setup_neural_requested = pyqtSignal()
    _OW, _OH = 560, 680

    def __init__(self, assistant_name="Alfred", user_name="",
                 ui_color=DEFAULT_UI_COLOR, voice="", current_icon="", voice_engine=None, parent=None):
        super().__init__(parent)
        self._current_icon = (current_icon or "").strip()
        self._initial_icon = self._current_icon
        self.on_icon_change = None
        self.on_preview_voice = None
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            CustomizeOverlay {{
                background: rgba(4, 12, 22, 0.96);
                border: 1px solid rgba(0, 240, 255, 0.35);
                border-radius: 16px;
            }}
        """)
        outer_lay = QVBoxLayout(self)
        outer_lay.setContentsMargins(20, 18, 20, 18)
        outer_lay.setSpacing(10)

        # Header with Title and Close Button
        hdr_row = QHBoxLayout()
        hdr_box = QVBoxLayout(); hdr_box.setSpacing(2)
        title = QLabel("⚙  RECONFIGURE BATCOMPUTER MATRIX")
        title.setFont(tech_font(11, QFont.Weight.Bold, letter_spacing=1.8))
        title.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        hdr_box.addWidget(title)

        sub = QLabel("PERSONA PROFILES // NEURAL VOCAL SYNTHESIS // CHROMATICS")
        sub.setFont(tech_font(7, QFont.Weight.Medium, letter_spacing=1.0))
        sub.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        hdr_box.addWidget(sub)
        hdr_row.addLayout(hdr_box)
        hdr_row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setFont(tech_font(10, QFont.Weight.Bold))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255, 255, 255, 0.05);
                color: {C.TEXT_MED};
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 14px;
            }}
            QPushButton:hover {{
                background: rgba(255, 42, 85, 0.25);
                color: #ffffff;
                border-color: #ff2a55;
            }}
        """)
        close_btn.clicked.connect(self._cancel)
        attach_hover_help(close_btn, "Discard changes and close the reconfiguration window.")
        hdr_row.addWidget(close_btn)
        outer_lay.addLayout(hdr_row)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: rgba(0, 240, 255, 0.16); margin: 2px 0;")
        outer_lay.addWidget(sep)

        # Scrollable container for all settings so it never overflows or clips
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: rgba(0, 0, 0, 0.2);
                width: 6px;
                border-radius: 3px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(0, 240, 255, 0.35);
                min-height: 24px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(0, 240, 255, 0.65);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        body_widget = QWidget()
        body_widget.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(body_widget)
        lay.setContentsMargins(4, 4, 10, 4)
        lay.setSpacing(10)

        def _lbl(txt, fs=8, bold=False, color=C.PRI, align=Qt.AlignmentFlag.AlignLeft):
            w = QLabel(txt); w.setAlignment(align)
            w.setFont(tech_font(fs,
                                QFont.Weight.Bold if bold else QFont.Weight.Medium,
                                letter_spacing=0.8 if bold else 0.3))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        _fs = (f"QLineEdit {{ background: {C.PANEL2}; color: {C.WHITE}; "
               f"border: 1px solid {C.BORDER_A}; border-radius: 2px; padding: 6px 12px; font-size: 13px; }}"
               f"QLineEdit:focus {{ border: 1px solid {C.PRI}; background: rgba(142, 155, 255, 0.08); }}")

        # ── Codename & Designation ───────────────────────────────────────
        lbl_codename = _lbl("ASSISTANT CODENAME", 8, bold=True, color=C.TEXT_DIM)
        lay.addWidget(lbl_codename)
        self._name_input = QLineEdit(assistant_name)
        self._name_input.setFont(mono_font(10, QFont.Weight.DemiBold, letter_spacing=0.5))
        self._name_input.setFixedHeight(34)
        self._name_input.setStyleSheet(_fs)
        attach_hover_help(self._name_input, "The codename ALFRED uses when speaking and displaying system status headers.", lbl_codename)
        lay.addWidget(self._name_input)

        lbl_designation = _lbl("COMMANDER DESIGNATION  (e.g. Master Wayne, Sir)", 8,
                               bold=True, color=C.TEXT_DIM)
        lay.addWidget(lbl_designation)
        self._user_input = QLineEdit(user_name)
        self._user_input.setPlaceholderText("e.g.  Master Wayne   (leave blank for default)")
        self._user_input.setFont(mono_font(10, letter_spacing=0.3))
        self._user_input.setFixedHeight(34)
        self._user_input.setStyleSheet(_fs)
        attach_hover_help(self._user_input, "How the assistant addresses you during conversations and briefings (e.g. Master Wayne, Sir).", lbl_designation)
        lay.addWidget(self._user_input)

        # ── Tactical Bat-Insignia & Application Icon ─────────────────────
        lbl_insignia = _lbl("TACTICAL BAT-INSIGNIA & APPLICATION ICON", 8, bold=True, color=C.TEXT_DIM)
        lay.addWidget(lbl_insignia)
        icon_sub = QLabel("SELECT CHASSIS BADGE // SYSTEM TRAY & TASKBAR ICON // REALTIME UPLINK")
        icon_sub.setFont(tech_font(7, QFont.Weight.Medium, letter_spacing=0.8))
        icon_sub.setStyleSheet(f"color: {C.TEXT_MUTED}; background: transparent; margin-bottom: 2px;")
        lay.addWidget(icon_sub)

        self._icon_cards: dict[str, QPushButton] = {}
        icon_grid = QGridLayout()
        icon_grid.setSpacing(8)
        icon_grid.setContentsMargins(0, 0, 0, 4)

        avail_icons = get_available_app_icons()
        if not self._current_icon and avail_icons:
            self._current_icon = avail_icons[0]["path"]

        cols = 3
        for idx, ic in enumerate(avail_icons):
            row = idx // cols
            col = idx % cols

            btn = QPushButton()
            btn.setFixedHeight(58)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

            btn_lay = QHBoxLayout(btn)
            btn_lay.setContentsMargins(8, 6, 8, 6)
            btn_lay.setSpacing(8)

            ico_lbl = QLabel()
            ico_lbl.setFixedSize(36, 36)
            ico_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ico_lbl.setStyleSheet("background: transparent;")
            pm = _scaled_icon_pixmap(ic["path"], 32, 32)
            if not pm.isNull():
                ico_lbl.setPixmap(pm)
            btn_lay.addWidget(ico_lbl)

            txt_box = QVBoxLayout()
            txt_box.setSpacing(2)
            txt_box.setAlignment(Qt.AlignmentFlag.AlignVCenter)

            name_lbl = QLabel(ic["name"])
            name_lbl.setFont(mono_font(8, QFont.Weight.Bold, letter_spacing=0.4))
            name_lbl.setStyleSheet("color: #ffffff; background: transparent;")
            txt_box.addWidget(name_lbl)

            file_lbl = QLabel(ic["filename"][:22])
            file_lbl.setFont(tech_font(6, letter_spacing=0.2))
            file_lbl.setStyleSheet(f"color: {C.TEXT_MUTED}; background: transparent;")
            txt_box.addWidget(file_lbl)

            btn_lay.addLayout(txt_box)
            btn_lay.addStretch()

            btn.clicked.connect(lambda _=False, p=ic["path"]: self._on_icon_picked(p))
            attach_hover_help(btn, f"Select '{ic['name']}' chassis insignia for HUD, taskbar, and tray badge.")
            self._icon_cards[ic["path"]] = btn
            icon_grid.addWidget(btn, row, col)

        lay.addLayout(icon_grid)
        self._refresh_icon_cards()

        # ── Assistant voice — Gemini prebuilt voices ─────────────────────
        from memory.config_manager import AVAILABLE_VOICES, DEFAULT_VOICE
        lbl_voice = _lbl("VOCAL SYNTHESIS PROFILE", 8, bold=True, color=C.TEXT_DIM)
        lay.addWidget(lbl_voice)
        self._sel_voice = (voice or DEFAULT_VOICE)
        if self._sel_voice not in AVAILABLE_VOICES:
            self._sel_voice = DEFAULT_VOICE
        self._voice_btns: dict[str, QPushButton] = {}
        voice_row = QHBoxLayout(); voice_row.setSpacing(6)
        for _v in AVAILABLE_VOICES:
            b = QPushButton(_v)
            b.setCheckable(True)
            b.setFixedHeight(29)
            b.setFont(mono_font(8, QFont.Weight.Bold, letter_spacing=0.4))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, name=_v: self._on_voice_pick(name))
            attach_hover_help(b, f"Use the neural vocal profile '{_v}' for spoken responses.", lbl_voice)
            self._voice_btns[_v] = b
            voice_row.addWidget(b)
        lay.addLayout(voice_row)
        self._refresh_voice_btns()

        # ── Voice Engine Architecture (Standard vs Jarvis VoxCPM2) ──────────
        from memory.config_manager import (
            get_voice_engine, save_voice_engine,
            get_jarvis_allow_cpu, save_jarvis_allow_cpu,
        )
        from core.tts.capability import check_jarvis_capability, Capability

        lbl_engine = _lbl("TTS SYNTHESIS ENGINE", 8, bold=True, color=C.TEXT_DIM)
        lay.addWidget(lbl_engine)

        self._sel_voice_engine = (voice_engine or get_voice_engine() or "default").lower()
        if self._sel_voice_engine not in ("default", "jarvis"):
            self._sel_voice_engine = "default"

        self._engine_btns: dict[str, QPushButton] = {}
        engine_row = QHBoxLayout()
        engine_row.setSpacing(6)
        engines = [
            ("default", "STANDARD / DEFAULT"),
            ("jarvis", "JARVIS (VOXCPM2 LORA)"),
        ]
        for eng_id, eng_label in engines:
            eb = QPushButton(eng_label)
            eb.setCheckable(True)
            eb.setFixedHeight(29)
            eb.setFont(mono_font(8, QFont.Weight.Bold, letter_spacing=0.4))
            eb.setCursor(Qt.CursorShape.PointingHandCursor)
            eb.clicked.connect(lambda _=False, eid=eng_id: self._on_engine_pick(eid))
            attach_hover_help(eb, f"Select '{eng_label}' backend architecture for local vocal synthesis.", lbl_engine)
            self._engine_btns[eng_id] = eb
            engine_row.addWidget(eb)
        lay.addLayout(engine_row)

        # Status Line & Preview Button Row
        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        self._lbl_engine_status = QLabel("")
        self._lbl_engine_status.setFont(tech_font(7, QFont.Weight.Medium, letter_spacing=0.3))
        self._lbl_engine_status.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        self._lbl_engine_status.setWordWrap(True)
        status_row.addWidget(self._lbl_engine_status, stretch=3)

        self._btn_preview_voice = QPushButton("▶ PREVIEW VOICE")
        self._btn_preview_voice.setFixedHeight(26)
        self._btn_preview_voice.setFont(mono_font(7, QFont.Weight.Bold, letter_spacing=0.5))
        self._btn_preview_voice.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_preview_voice.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL2};
                color: {C.PRI};
                border: 1px solid {C.BORDER_A};
                border-radius: 2px;
                padding: 0 8px;
            }}
            QPushButton:hover {{
                background: rgba(0, 240, 255, 0.15);
                border-color: {C.PRI};
                color: #ffffff;
            }}
        """)
        self._btn_preview_voice.clicked.connect(self._preview_voice)
        attach_hover_help(self._btn_preview_voice, "Speak a fixed tactical verification phrase using the active voice engine.", lbl_engine)
        status_row.addWidget(self._btn_preview_voice, stretch=1)
        lay.addLayout(status_row)

        self._refresh_engine_ui()

        # ── Single Authentic CRT Themes Selector // Chromatics ─────────────
        from core.ui.themes import ThemeRegistry
        lbl_theme = _lbl("AUTHENTIC CRT THEMES // CHROMATICS", 8, bold=True, color=C.TEXT_DIM)
        lay.addWidget(lbl_theme)
        swatch_grid = QGridLayout()
        swatch_grid.setSpacing(6)
        swatch_grid.setContentsMargins(0, 0, 0, 0)

        all_themes = ThemeRegistry.instance().list_themes()
        self._theme_btns: dict[str, QPushButton] = {}
        for idx, th in enumerate(all_themes):
            r = idx // 2
            c = idx % 2
            sb = QPushButton(th.display_name)
            sb.setFixedHeight(30)
            sb.setFont(mono_font(7, QFont.Weight.Bold, letter_spacing=0.5))
            sb.setCursor(Qt.CursorShape.PointingHandCursor)
            sb.clicked.connect(lambda _, h=th.hex: self._set_color(h, update_wheel=True, preview=True))
            attach_hover_help(sb, f"{th.display_name} ({th.hex}) — {th.tagline}", lbl_theme)
            self._theme_btns[th.display_name] = sb
            swatch_grid.addWidget(sb, r, c)
        lay.addLayout(swatch_grid)

        # ── HueWheel & Hex input ─────────────────────────────────────────
        self._initial_color = (ui_color or DEFAULT_UI_COLOR).strip().lower()
        self._sel_color     = self._initial_color
        self.on_preview     = None

        self._wheel = HueWheel(self._sel_color)
        wheel_row = QHBoxLayout()
        wheel_row.addStretch(); wheel_row.addWidget(self._wheel); wheel_row.addStretch()
        lay.addLayout(wheel_row)
        self._wheel.hue_picked.connect(self._on_wheel_pick)
        self._wheel.hue_committed.connect(self._on_wheel_commit)
        attach_hover_help(self._wheel, "Drag the color wheel to interactively tune custom HUD accent colors in real time.")

        self._hex_input = QLineEdit(self._sel_color)
        self._hex_input.setPlaceholderText("#ff0037   (custom hex colour)")
        self._hex_input.setFont(mono_font(10))
        self._hex_input.setFixedHeight(30)
        self._hex_input.setStyleSheet(_fs)
        self._hex_input.textEdited.connect(self._on_hex_edited)
        attach_hover_help(self._hex_input, "Enter a custom 6-digit hex color code (e.g. #8e9bff, #00f0ff) for HUD styling.")
        lay.addWidget(self._hex_input)

        lay.addSpacing(8)
        lbl_api = _lbl("BACKEND SERVICES & API INTEGRATIONS", 8, bold=True, color=C.TEXT_DIM)
        lay.addWidget(lbl_api)

        # 1. External API Services (Spotify, Gmail, Google Workspace)
        self._services_api_btn = QPushButton("[ ◈ ]  SETUP SPOTIFY, GMAIL & WORKSPACE")
        self._services_api_btn.setFixedHeight(32)
        self._services_api_btn.setFont(mono_font(8, QFont.Weight.Bold, letter_spacing=0.8))
        self._services_api_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._services_api_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL2};
                color: {C.PRI};
                border: 1px solid {C.PRI};
                border-radius: 2px;
                padding: 0 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {C.PRI};
                color: {C.DARK};
            }}
        """)
        self._services_api_btn.clicked.connect(lambda: self.setup_api_requested.emit())
        attach_hover_help(self._services_api_btn, "Configure encrypted credentials and OAuth tokens for Spotify, Gmail, and Google Workspace.", lbl_api)
        lay.addWidget(self._services_api_btn)
        self._refresh_services_btn()

        lay.addSpacing(4)
        # 2. Neural LLM Backend (Gemini, OpenRouter, Local Models)
        neural_btn = QPushButton("◈  CONFIGURE NEURAL LLM PROVIDERS")
        neural_btn.setFixedHeight(28)
        neural_btn.setFont(mono_font(7, QFont.Weight.Bold, letter_spacing=0.6))
        neural_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        neural_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255, 255, 255, 0.04);
                color: {C.TEXT_MED};
                border: 1px solid {C.BORDER_A};
                border-radius: 2px;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background: {C.PANEL2};
                color: {C.WHITE};
                border-color: {C.PRI};
            }}
        """)
        neural_btn.clicked.connect(lambda: self.setup_neural_requested.emit())
        attach_hover_help(neural_btn, "Open the neural engine setup window to configure Gemini, OpenRouter, Groq, or local LLM credentials.", lbl_api)
        lay.addWidget(neural_btn)

        scroll.setWidget(body_widget)
        outer_lay.addWidget(scroll, stretch=1)

        # Fixed Bottom Action Bar (ALWAYS visible!)
        sep_bottom = QFrame(); sep_bottom.setFrameShape(QFrame.Shape.HLine)
        sep_bottom.setStyleSheet(f"color: {C.BORDER_A}; margin: 2px 0;")
        outer_lay.addWidget(sep_bottom)

        btn_row = QHBoxLayout(); btn_row.setSpacing(10)
        save_btn = QPushButton("▸  COMMIT DIRECTIVE")
        save_btn.setFixedHeight(36)
        save_btn.setFont(mono_font(8, QFont.Weight.Bold, letter_spacing=1.0))
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PRI};
                color: {C.DARK};
                border: 1px solid {C.PRI};
                border-radius: 2px;
            }}
            QPushButton:hover {{
                background: {C.TEXT_BRIGHT};
                color: #000000;
                border-color: #ffffff;
            }}
            QPushButton:pressed {{
                background: {C.PRI_DIM};
            }}
        """)
        save_btn.clicked.connect(self._save)
        attach_hover_help(save_btn, "Save and apply all persona, voice, insignia, and theme changes to your configuration.")
        btn_row.addWidget(save_btn, stretch=2)

        cancel_btn = QPushButton("DISCARD")
        cancel_btn.setFixedHeight(36)
        cancel_btn.setFont(mono_font(8, letter_spacing=0.8))
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL2};
                color: {C.TEXT_MED};
                border: 1px solid {C.BORDER_A};
                border-radius: 2px;
            }}
            QPushButton:hover {{ color: #ffffff; border-color: {C.PRI}; background: rgba(142, 155, 255, 0.12); }}
            QPushButton:pressed {{ background: rgba(142, 155, 255, 0.05); }}
        """)
        cancel_btn.clicked.connect(self._cancel)
        attach_hover_help(cancel_btn, "Discard all unsaved changes and close the reconfiguration window.")
        btn_row.addWidget(cancel_btn, stretch=1)
        outer_lay.addLayout(btn_row)

    def _apply_preset(self, name: str, user: str, color: str, voice: str):
        self._name_input.setText(name)
        self._user_input.setText(user)
        self._sel_voice = voice
        self._refresh_voice_btns()
        self._set_color(color, update_wheel=True, preview=True)

    def reset_values(self, assistant_name: str, user_name: str, ui_color: str,
                     voice: str, current_icon: str, voice_engine: str | None = None) -> None:
        """Refresh reusable controls from persisted settings before showing."""
        self._name_input.setText(assistant_name or "Alfred")
        self._user_input.setText(user_name or "")
        self._initial_color = (ui_color or DEFAULT_UI_COLOR).strip().lower()
        self._set_color(self._initial_color, update_wheel=True, preview=False)
        self._sel_voice = voice if voice in self._voice_btns else next(iter(self._voice_btns), self._sel_voice)
        self._refresh_voice_btns()
        self._current_icon = (current_icon or "").strip()
        self._initial_icon = self._current_icon
        self._refresh_icon_cards()
        if voice_engine:
            self._sel_voice_engine = voice_engine.lower()
        else:
            from memory.config_manager import get_voice_engine
            self._sel_voice_engine = get_voice_engine()
        self._refresh_engine_ui()
        self._refresh_services_btn()

    def _refresh_services_btn(self) -> None:
        if not hasattr(self, "_services_api_btn") or self._services_api_btn is None:
            return
        try:
            from core.apis.registry import get_configured_backends_count
            configured, total = get_configured_backends_count()
            self._services_api_btn.setText(f"[ ◈ ]  SETUP SPOTIFY, GMAIL & WORKSPACE ({configured}/{total})")
        except Exception:
            self._services_api_btn.setText("[ ◈ ]  SETUP SPOTIFY, GMAIL & WORKSPACE")

    # ── voice selection ──────────────────────────────────────────────────────
    def _on_voice_pick(self, name: str):
        self._sel_voice = name
        self._refresh_voice_btns()

    def _refresh_voice_btns(self):
        """Highlight the selected voice pill; dim the rest."""
        for name, b in self._voice_btns.items():
            on = (name == self._sel_voice)
            b.setChecked(on)
            if on:
                b.setStyleSheet(f"""
                    QPushButton {{ background: {C.PRI}; color: {C.DARK};
                        border: 1px solid {C.PRI}; border-radius: 2px; font-weight: bold; }}
                """)
            else:
                b.setStyleSheet(f"""
                    QPushButton {{ background: {C.PANEL2}; color: {C.TEXT_MED};
                        border: 1px solid {C.BORDER_A}; border-radius: 2px; }}
                    QPushButton:hover {{ color: #ffffff; border-color: {C.PRI}; background: rgba(142, 155, 255, 0.10); }}
                """)

    # ── voice engine selection & verification ────────────────────────────────
    def _on_engine_pick(self, eid: str):
        from core.tts.capability import check_jarvis_capability, Capability
        from memory.config_manager import get_jarvis_allow_cpu

        if eid == "jarvis":
            allow_cpu = get_jarvis_allow_cpu()
            cap = check_jarvis_capability(allow_cpu=allow_cpu, use_cache=True)
            if not cap.is_usable(allow_cpu=allow_cpu):
                self._sel_voice_engine = "default"
                self._refresh_engine_ui(warning_reason=cap.display_status())
                return
        self._sel_voice_engine = eid
        self._refresh_engine_ui()

    def _refresh_engine_ui(self, warning_reason: str | None = None):
        from core.tts.capability import check_jarvis_capability, Capability
        from memory.config_manager import get_jarvis_allow_cpu

        for eid, b in self._engine_btns.items():
            on = (eid == self._sel_voice_engine)
            b.setChecked(on)
            if on:
                b.setStyleSheet(f"""
                    QPushButton {{ background: {C.PRI}; color: {C.DARK};
                        border: 1px solid {C.PRI}; border-radius: 2px; font-weight: bold; }}
                """)
            else:
                b.setStyleSheet(f"""
                    QPushButton {{ background: {C.PANEL2}; color: {C.TEXT_MED};
                        border: 1px solid {C.BORDER_A}; border-radius: 2px; }}
                    QPushButton:hover {{ color: #ffffff; border-color: {C.PRI}; background: rgba(142, 155, 255, 0.10); }}
                """)

        allow_cpu = get_jarvis_allow_cpu()
        cap = check_jarvis_capability(allow_cpu=allow_cpu, use_cache=True)

        if warning_reason:
            self._lbl_engine_status.setText(f"⚠ JARVIS BLOCKED: {warning_reason}")
            self._lbl_engine_status.setStyleSheet("color: #ffaa00; background: transparent;")
        elif self._sel_voice_engine == "jarvis":
            self._lbl_engine_status.setText(f"● ACTIVE: Jarvis Voice ({cap.display_status()})")
            color = "#00f0ff" if cap.is_usable(allow_cpu) else "#ffaa00"
            self._lbl_engine_status.setStyleSheet(f"color: {color}; background: transparent;")
        else:
            self._lbl_engine_status.setText(f"● ACTIVE: Standard Voice (Jarvis: {cap.display_status()})")
            self._lbl_engine_status.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")

    def _preview_voice(self):
        eng = self._sel_voice_engine
        if getattr(self, "on_preview_voice", None):
            try:
                self.on_preview_voice(eng)
                return
            except Exception as e:
                print(f"[Voice Preview] Custom handler error: {e}")

        def _worker():
            try:
                from core.tts import get_engine
                engine = get_engine(eng)
                engine.speak("All systems nominal, sir. Tactical audio matrix online.")
            except Exception as exc:
                print(f"[Voice Preview] Synthesis error: {exc}")

        threading.Thread(target=_worker, daemon=True).start()

    # ── colour flow ──────────────────────────────────────────────────────────
    def _set_color(self, hx: str, update_wheel: bool = True, preview: bool = True):
        """Updates the selected colour; hex box + wheel stay in sync, theme is live-previewed."""
        self._sel_color = hx.strip().lower()
        self._hex_input.blockSignals(True)
        self._hex_input.setText(self._sel_color)
        self._hex_input.blockSignals(False)
        if update_wheel:
            self._wheel.set_color(self._sel_color)
        self._refresh_theme_buttons()
        if preview and self.on_preview:
            self.on_preview(self._sel_color)

    def _refresh_theme_buttons(self):
        """Highlight active theme button; dim others with authentic styling."""
        from core.ui.themes import ThemeRegistry
        cur_theme = ThemeRegistry.instance().get(self._sel_color)
        for theme in ThemeRegistry.instance().list_themes():
            btn = self._theme_btns.get(theme.display_name)
            if not btn:
                continue
            is_active = (theme.id == cur_theme.id) or (self._sel_color.lower() == theme.hex.lower())
            accent_hex = theme.hex
            bg_hex = theme.palette.panel2
            if is_active:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {accent_hex}33;
                        color: #ffffff;
                        border: 1.5px solid {accent_hex};
                        border-radius: 2px;
                        padding: 0 10px;
                        font-weight: bold;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {bg_hex};
                        color: {accent_hex};
                        border: 1px solid {accent_hex}55;
                        border-radius: 2px;
                        padding: 0 10px;
                    }}
                    QPushButton:hover {{
                        background: {accent_hex}22;
                        border-color: {accent_hex};
                        color: #ffffff;
                    }}
                """)

    def _on_wheel_pick(self, hx: str):
        self._sel_color = hx
        self._hex_input.blockSignals(True)
        self._hex_input.setText(hx)
        self._hex_input.blockSignals(False)

    def _on_wheel_commit(self, hx: str):
        self._set_color(hx, update_wheel=False)

    def _on_hex_edited(self, text: str):
        t = text.strip().lower()
        if t.startswith("#") and len(t) == 7:
            try:
                int(t[1:], 16)
            except ValueError:
                return
            self._set_color(t, update_wheel=True, preview=True)

    def _refresh_icon_cards(self):
        norm_cur = Path(self._current_icon).name.lower() if self._current_icon else ""
        style_key = (norm_cur, C.PRI, C.PANEL2, C.BORDER_A)
        if getattr(self, "_icon_style_key", None) == style_key:
            return
        for path_key, btn in self._icon_cards.items():
            is_active = (path_key == self._current_icon) or (norm_cur and Path(path_key).name.lower() == norm_cur)
            if is_active:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: rgba(0, 240, 255, 0.16);
                        border: 1.5px solid {C.PRI};
                        border-radius: 4px;
                        text-align: left;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {C.PANEL2};
                        border: 1px solid {C.BORDER_A};
                        border-radius: 4px;
                        text-align: left;
                    }}
                    QPushButton:hover {{
                        background: rgba(142, 155, 255, 0.12);
                        border-color: {C.PRI};
                    }}
                """)
        self._icon_style_key = style_key

    def _on_icon_picked(self, path: str):
        self._current_icon = path
        self._refresh_icon_cards()
        if self.on_icon_change:
            try:
                self.on_icon_change(path)
            except Exception as e:
                print(f"[Icon] Realtime change error: {e}")

    def _cancel(self):
        TacticalHoverHelpManager.instance().dismiss()
        if self.on_preview and self._sel_color != self._initial_color:
            self.on_preview(self._initial_color)
        if self.on_icon_change and self._current_icon != self._initial_icon:
            self.on_icon_change(self._initial_icon)
        self.hide()

    def _save(self):
        TacticalHoverHelpManager.instance().dismiss()
        name = self._name_input.text().strip() or "Alfred"
        user = self._user_input.text().strip()
        from memory.config_manager import save_voice_engine
        save_voice_engine(self._sel_voice_engine)
        self.saved.emit(name, user, self._sel_color or DEFAULT_UI_COLOR, self._sel_voice)
        if self._current_icon and self.on_icon_change:
            self.on_icon_change(self._current_icon)
        self.hide()

    def hideEvent(self, event):
        TacticalHoverHelpManager.instance().dismiss()
        super().hideEvent(event)
