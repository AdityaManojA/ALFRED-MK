"""
core/ui/alexa_permissions_dialog.py — Themed popup for managing approved Alexa capabilities.
"""
from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.hud_video.layering import make_frameless_overlay, raise_overlay
from core.integrations.alexa.policy import AlexaActionPolicy
from core.secrets.store import SecretStore, get_secret_store
from core.ui.themes import ThemeChrome


CAPABILITY_DEFINITIONS = [
    ("telemetry_and_status", "Read System Status && Telemetry", "Query CPU, RAM, time, weather, and assistant status.", True),
    ("focus_mode", "Start / Stop Focus Sessions", "Start or end Sentry Focus timer blocks.", True),
    ("media_playback", "Pause / Resume Media", "Control Spotify and Audio Core local playback.", True),
    ("internet_speed", "Run Internet Speed Test", "Queue non-blocking internet diagnostics.", True),
    ("reminders", "Set Reminders && Alarms", "Add reminders to local schedule.", True),
    ("calendar_summary", "Read Calendar / Schedule Summary", "Speak high-level schedule without private body details.", True),
    ("microphone_mute", "Toggle System Microphone Mute", "Mute or unmute desktop microphone.", True),
]

PROHIBITED_CAPABILITIES = [
    ("Send emails or messages", "Strictly denied by security policy."),
    ("Control keyboard / mouse automation", "Strictly denied by security policy."),
    ("Access screen / screenshots", "Strictly denied by security policy."),
    ("Execute shell / terminal commands", "Strictly denied by security policy."),
    ("Delete or modify files", "Strictly denied by security policy."),
]


class AlexaPermissionsDialog(QDialog):
    """Tactical permissions manager for Alexa capabilities."""

    def __init__(self, parent: Optional[QWidget] = None, policy: Optional[AlexaActionPolicy] = None, store: Optional[SecretStore] = None):
        """Create the frameless modal dialog, resolve the action policy and secret store, then build the UI and load stored values."""
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setModal(True)

        self.policy = policy or AlexaActionPolicy()
        self.store = store or get_secret_store()
        self._checkboxes: dict[str, QCheckBox] = {}

        self._init_ui()
        self._load_values()

    def showEvent(self, event) -> None:
        """Center the dialog over its parent widget when it is shown."""
        super().showEvent(event)
        if self.parent() and isinstance(self.parent(), QWidget):
            parent_geo = self.parent().geometry()
            self.move(
                parent_geo.x() + (parent_geo.width() - self.width()) // 2,
                parent_geo.y() + (parent_geo.height() - self.height()) // 2,
            )

    def _init_ui(self) -> None:
        """Build the dialog layout: header with close button, per-capability checkboxes, and reset/save buttons."""
        pal = ThemeChrome.get_active().palette
        self.setFixedSize(540, 580)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #040c16;
                border: 1px solid {pal.border_b};
                border-radius: 8px;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # Header
        hdr = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("◈  ALEXA CAPABILITY PERMISSIONS")
        title.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {pal.pri};")
        title_box.addWidget(title)

        sub = QLabel("ENABLE OR RESTRICT VOICE-CALLABLE DIRECTIVES")
        sub.setFont(QFont("Consolas", 7))
        sub.setStyleSheet(f"color: {pal.text_dim};")
        title_box.addWidget(sub)
        hdr.addLayout(title_box)
        hdr.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: {pal.panel2};
                color: {pal.text_med};
                border: 1px solid {pal.border_a};
                border-radius: 12px;
            }}
            QPushButton:hover {{ color: #ffffff; border-color: {pal.red}; }}
        """)
        close_btn.clicked.connect(self.reject)
        hdr.addWidget(close_btn)
        root.addLayout(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {pal.border_a};")
        root.addWidget(sep)

        # Approved Capabilities Section
        sec_lbl = QLabel("APPROVED VOICE DIRECTIVES")
        sec_lbl.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        sec_lbl.setStyleSheet(f"color: {pal.acc};")
        root.addWidget(sec_lbl)

        for cap_id, cap_title, cap_desc, default_val in CAPABILITY_DEFINITIONS:
            row = QHBoxLayout()
            cb = QCheckBox(f"✓  {cap_title}")
            cb.setFont(QFont("Consolas", 8, QFont.Weight.DemiBold))
            cb.setStyleSheet(f"""
                QCheckBox {{
                    color: {pal.text_bright};
                    spacing: 6px;
                }}
                QCheckBox::indicator {{
                    width: 14px;
                    height: 14px;
                    border: 1px solid {pal.pri};
                    background: {pal.panel2};
                    border-radius: 2px;
                }}
                QCheckBox::indicator:checked {{
                    background: {pal.pri};
                }}
            """)
            cb.setChecked(default_val)
            self._checkboxes[cap_id] = cb
            row.addWidget(cb, stretch=1)
            root.addLayout(row)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {pal.border_a}; margin: 4px 0;")
        root.addWidget(sep2)

        # Prohibited Capabilities Section
        denied_lbl = QLabel("PROHIBITED CAPABILITIES (ALWAYS DENIED)")
        denied_lbl.setFont(QFont("Consolas", 7, QFont.Weight.Bold))
        denied_lbl.setStyleSheet(f"color: {pal.red};")
        root.addWidget(denied_lbl)

        for d_title, d_desc in PROHIBITED_CAPABILITIES:
            row = QHBoxLayout()
            lbl = QLabel(f"✕  {d_title}")
            lbl.setFont(QFont("Consolas", 7))
            lbl.setStyleSheet(f"color: {pal.text_dim};")
            row.addWidget(lbl)
            root.addLayout(row)

        root.addStretch()

        # Footer Buttons
        foot = QHBoxLayout()
        reset_btn = QPushButton("RESET DEFAULTS")
        reset_btn.setFont(QFont("Consolas", 7))
        reset_btn.setFixedSize(110, 28)
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.setStyleSheet(f"""
            QPushButton {{
                background: {pal.panel2};
                color: {pal.text_med};
                border: 1px solid {pal.border_a};
            }}
            QPushButton:hover {{ color: #ffffff; border-color: #ffaa00; }}
        """)
        reset_btn.clicked.connect(self._reset_defaults)
        foot.addWidget(reset_btn)

        foot.addStretch()

        save_btn = QPushButton("SAVE PERMISSIONS ❯")
        save_btn.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        save_btn.setFixedSize(140, 28)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(142, 155, 255, 0.2);
                color: {pal.pri};
                border: 1px solid {pal.pri};
            }}
            QPushButton:hover {{ background: {pal.pri}; color: {pal.dark}; }}
        """)
        save_btn.clicked.connect(self._save_and_close)
        foot.addWidget(save_btn)

        root.addLayout(foot)

    def _load_values(self) -> None:
        """Load stored permission values."""
        for cap_id, cb in self._checkboxes.items():
            stored = self.store.get(f"alexa.perm.{cap_id}")
            if stored is not None:
                cb.setChecked(stored.strip().lower() == "true")
            else:
                cb.setChecked(self.policy.is_capability_enabled(cap_id))

    def _reset_defaults(self) -> None:
        """Reset checkboxes to safe defaults."""
        for cap_id, cap_title, cap_desc, default_val in CAPABILITY_DEFINITIONS:
            if cap_id in self._checkboxes:
                self._checkboxes[cap_id].setChecked(default_val)

    def _save_and_close(self) -> None:
        """Persist permissions and apply to policy."""
        for cap_id, cb in self._checkboxes.items():
            enabled = cb.isChecked()
            self.policy.set_capability_enabled(cap_id, enabled)
            self.store.set(f"alexa.perm.{cap_id}", str(enabled).lower())
        self.accept()

    def paintEvent(self, event) -> None:
        """Fill the background with the dark panel colour and draw the styled widget primitive."""
        from PyQt6.QtGui import QColor, QPainter
        from PyQt6.QtWidgets import QStyle, QStyleOption
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#040c16"))
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)
