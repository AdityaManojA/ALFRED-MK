"""
core/ui/setup_api_modal.py — Tabbed API Backend Setup Modal for Tactical Controls & Settings.

Features:
- Frameless, glassmorphic modal matching the active Batcomputer HUD palette.
- Tabbed navigation: [Google Workspace] [Spotify] [Gmail API] with animated palette accent highlight.
- Masked inputs (password echo mode) with no plaintext echo on focus/blur.
- Background asynchronous validation without blocking HUD paint.
- Direct integration with encrypted SecretStore.
"""
from __future__ import annotations

import json
import re
import threading
from typing import Optional

from PyQt6.QtCore import QPoint, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.apis.registry import (
    get_api_registry,
    get_backend,
    save_backend_credentials,
    validate_backend_fields,
)
from core.integrations.alexa.account_link import AccountLinkingManager
from core.integrations.alexa.config import (
    AlexaConfig,
    load_alexa_config_from_store,
    save_alexa_config_to_store,
)
from core.integrations.alexa.policy import AlexaActionPolicy
from core.integrations.alexa.state import AlexaConnectionStatus, AlexaStateManager
from core.secrets.store import SecretStore, get_secret_store
from core.ui.alexa_permissions_dialog import (
    CAPABILITY_DEFINITIONS,
    PROHIBITED_CAPABILITIES,
    AlexaPermissionsDialog,
)
from core.ui.themes import ThemeChrome

COLOR_CYAN = "#00f0ff"
COLOR_YELLOW = "#ffaa00"
COLOR_GREEN = "#00ff66"
COLOR_RED = "#ff2a55"


class _TabsProxy:
    """Compatibility proxy for tab inspection in automated test suites."""
    def __init__(self, tab_names: list[str]):
        """Store the tab display names."""
        self._names = tab_names

    def count(self) -> int:
        """Return the number of tab names."""
        return len(self._names)

    def tabText(self, idx: int) -> str:
        """Return the tab name at idx, or an empty string if out of range."""
        return self._names[idx] if 0 <= idx < len(self._names) else ""


class SetupApiModal(QDialog):
    """
    Tactical glassmorphic dialog for managing encrypted API keys.
    """
    config_saved = pyqtSignal(str)   # backend_id / name
    _async_validation_done = pyqtSignal(str, bool, str)  # (backend_id_or_name, is_valid, message)

    _MODAL_W = 640
    _MODAL_H = 620

    def __init__(self, parent=None, store: Optional[SecretStore] = None):
        """Create the frameless API setup modal, wire the secret store and Alexa managers, build the UI and load saved values.
        Also exposes input-field aliases used by UI tests.
        """
        super().__init__(parent)
        from core.hud_video.layering import make_frameless_overlay
        make_frameless_overlay(self, parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        import core.secrets.store
        self.store = store or core.secrets.store.get_secret_store()
        self._active_tab_idx = 0
        self._backend_ids = ["google_workspace", "spotify", "gmail", "alexa"]
        self._tab_buttons: list[QPushButton] = []
        self._tabs = _TabsProxy(["GOOGLE WORKSPACE", "SPOTIFY", "GMAIL API", "ALEXA"])

        self._alexa_policy = AlexaActionPolicy()
        self._alexa_linking_mgr = AccountLinkingManager()
        self._alexa_state_mgr = AlexaStateManager()

        self._async_validation_done.connect(self._on_validation_result)

        self._init_ui()
        self._load_current_values()

        # UI test aliases
        self._spotify_id_input = self._spot_cid
        self._spotify_secret_input = self._spot_secret
        self._gw_id_input = self._gw_cid
        self._gw_secret_input = self._gw_secret
        self._gmail_key_input = self._gmail_pw
        self._alexa_id_input = self._alexa_skill_id
        self._alexa_secret_input = self._alexa_oauth_csecret
        self._footer_status = self._status_lbl

    def _submit_spotify(self, sync: bool = True) -> None:
        """Alias for programmatic submission in tests."""
        self._switch_tab(1)
        self._on_submit_current_tab(sync=sync)

    def _submit_gw(self, sync: bool = True) -> None:
        """Alias for programmatic submission in tests."""
        self._switch_tab(0)
        self._on_submit_current_tab(sync=sync)

    def _submit_gmail(self, sync: bool = True) -> None:
        """Alias for programmatic submission in tests."""
        self._switch_tab(2)
        self._on_submit_current_tab(sync=sync)

    def _submit_alexa(self, sync: bool = True) -> None:
        """Alias for programmatic submission in tests."""
        self._switch_tab(3)
        self._on_submit_current_tab(sync=sync)

    def _init_ui(self) -> None:
        """Build the modal layout: header, backend tab buttons, stacked backend pages, and a footer with status, discard and save buttons."""
        pal = ThemeChrome.get_active().palette

        self.setFixedSize(self._MODAL_W, self._MODAL_H)
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

        # ── Header ───────────────────────────────────────────────────────────
        hdr_row = QHBoxLayout()
        hdr_box = QVBoxLayout()
        hdr_box.setSpacing(2)

        hdr_title = QLabel("◈  TACTICAL API BACKEND SETUP")
        hdr_title.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        hdr_title.setStyleSheet(f"color: {pal.pri}; background: transparent;")
        hdr_box.addWidget(hdr_title)

        hdr_sub = QLabel("ENCRYPTED LOCAL STORAGE // OAUTH & KEY DIRECTIVES")
        hdr_sub.setFont(QFont("Consolas", 7, QFont.Weight.Medium))
        hdr_sub.setStyleSheet(f"color: {pal.text_dim}; background: transparent;")
        hdr_box.addWidget(hdr_sub)
        hdr_row.addLayout(hdr_box)
        hdr_row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(26, 26)
        close_btn.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: {pal.panel2};
                color: {pal.text_med};
                border: 1px solid {pal.border_a};
                border-radius: 13px;
            }}
            QPushButton:hover {{
                background: rgba(255, 42, 85, 0.25);
                color: #ffffff;
                border-color: {pal.red};
            }}
        """)
        close_btn.clicked.connect(self.reject)
        hdr_row.addWidget(close_btn)
        root.addLayout(hdr_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {pal.border_a}; margin: 2px 0;")
        root.addWidget(sep)

        # ── Tabs Navigation ──────────────────────────────────────────────────
        tab_row = QHBoxLayout()
        tab_row.setSpacing(8)

        tab_defs = [
            ("google_workspace", "🌐  GOOGLE WORKSPACE"),
            ("spotify", "🎵  SPOTIFY API"),
            ("gmail", "✉  GMAIL API"),
            ("alexa", "🎙  ALEXA"),
        ]

        for idx, (bid, title) in enumerate(tab_defs):
            b = QPushButton(title)
            b.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
            b.setFixedHeight(30)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setCheckable(True)
            b.clicked.connect(lambda _, i=idx: self._switch_tab(i))
            self._tab_buttons.append(b)
            tab_row.addWidget(b)

        root.addLayout(tab_row)

        # ── Stacked Pages ────────────────────────────────────────────────────
        self._stack = QStackedWidget()

        # 1. Google Workspace Page
        self._stack.addWidget(self._build_google_page())

        # 2. Spotify Page
        self._stack.addWidget(self._build_spotify_page())

        # 3. Gmail Page
        self._stack.addWidget(self._build_gmail_page())

        # 4. Alexa Page
        self._stack.addWidget(self._build_alexa_page())

        root.addWidget(self._stack, stretch=1)

        # ── Footer Status & Buttons ──────────────────────────────────────────
        foot_sep = QFrame()
        foot_sep.setFrameShape(QFrame.Shape.HLine)
        foot_sep.setStyleSheet(f"color: {pal.border_a}; margin: 2px 0;")
        root.addWidget(foot_sep)

        foot_row = QHBoxLayout()
        foot_row.setSpacing(10)

        self._status_lbl = QLabel("")
        self._status_lbl.setFont(QFont("Consolas", 8, QFont.Weight.DemiBold))
        self._status_lbl.setStyleSheet(f"color: {pal.text_med}; background: transparent;")
        foot_row.addWidget(self._status_lbl, stretch=1)

        cancel_btn = QPushButton("DISCARD")
        cancel_btn.setFixedSize(90, 32)
        cancel_btn.setFont(QFont("Consolas", 8))
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {pal.panel2};
                color: {pal.text_med};
                border: 1px solid {pal.border_a};
                border-radius: 2px;
            }}
            QPushButton:hover {{
                color: #ffffff;
                border-color: {pal.pri};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        foot_row.addWidget(cancel_btn)

        self._save_btn = QPushButton("SAVE CONFIG ❯")
        self._save_btn.setFixedSize(130, 32)
        self._save_btn.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(142, 155, 255, 0.16);
                color: {pal.pri};
                border: 1px solid {pal.pri};
                border-radius: 2px;
            }}
            QPushButton:hover {{
                background: {pal.pri};
                color: {pal.dark};
            }}
        """)
        self._save_btn.clicked.connect(self._on_submit_current_tab)
        foot_row.addWidget(self._save_btn)

        root.addLayout(foot_row)
        self._switch_tab(0)

    def paintEvent(self, event):
        """Paint the dark rounded-rect background with the active palette border."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = ThemeChrome.get_active().palette
        bg_col = QColor("#040c16")
        border_col = QColor(pal.border_b)
        painter.setBrush(bg_col)
        painter.setPen(QPen(border_col, 1))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 8, 8)

    def showEvent(self, event):
        """Reload stored credentials into the fields and clear the status line on show."""
        super().showEvent(event)
        self._load_current_values()
        self._status_lbl.setText("")

    def _field_style(self) -> str:
        """Return the themed stylesheet shared by line-edit and text-edit fields."""
        pal = ThemeChrome.get_active().palette
        return f"""
            QLineEdit, QTextEdit {{
                background: {pal.panel2};
                color: {pal.text_bright};
                border: 1px solid {pal.border_a};
                border-radius: 2px;
                padding: 4px 8px;
                font-family: 'Consolas', monospace;
                font-size: 11px;
                min-height: 20px;
            }}
            QLineEdit:focus, QTextEdit:focus {{
                border: 1px solid {pal.pri};
                background: rgba(142, 155, 255, 0.08);
            }}
        """

    def _lbl(self, text: str, fs: int = 7) -> QLabel:
        """Return a bold, dim-coloured Consolas field label with the given text and font size."""
        pal = ThemeChrome.get_active().palette
        lbl = QLabel(text)
        lbl.setFont(QFont("Consolas", fs, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {pal.text_dim}; background: transparent;")
        return lbl

    # ── Google Workspace Page ────────────────────────────────────────────────
    def _build_google_page(self) -> QWidget:
        """Build the Google Workspace page with client ID/secret fields and a browser OAuth button."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 8, 4, 8)
        lay.setSpacing(8)

        desc = QLabel("Authenticate Google Workspace (Calendar, Drive) via Google Cloud credentials.")
        desc.setFont(QFont("Consolas", 7))
        desc.setStyleSheet(f"color: {ThemeChrome.get_active().palette.text_med};")
        lay.addWidget(desc)

        lay.addWidget(self._lbl("CLIENT ID"))
        self._gw_cid = QLineEdit()
        self._gw_cid.setEchoMode(QLineEdit.EchoMode.Password)
        self._gw_cid.setPlaceholderText("...apps.googleusercontent.com")
        self._gw_cid.setStyleSheet(self._field_style())
        lay.addWidget(self._gw_cid)

        lay.addWidget(self._lbl("CLIENT SECRET"))
        self._gw_secret = QLineEdit()
        self._gw_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self._gw_secret.setPlaceholderText("GOCSPX-...")
        self._gw_secret.setStyleSheet(self._field_style())
        lay.addWidget(self._gw_secret)

        # OAuth one-click helper
        oauth_row = QHBoxLayout()
        self._gw_auth_btn = QPushButton("⚡  AUTHORIZE WITH GOOGLE BROWSER")
        self._gw_auth_btn.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        self._gw_auth_btn.setFixedHeight(30)
        self._gw_auth_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        pal = ThemeChrome.get_active().palette
        self._gw_auth_btn.setStyleSheet(f"""
            QPushButton {{
                background: {pal.panel2};
                color: {pal.green};
                border: 1px solid {pal.green};
                border-radius: 2px;
            }}
            QPushButton:hover {{
                background: {pal.green};
                color: {pal.dark};
            }}
        """)
        self._gw_auth_btn.clicked.connect(self._start_google_oauth)
        oauth_row.addWidget(self._gw_auth_btn)
        lay.addLayout(oauth_row)

        lay.addStretch()
        return w

    # ── Spotify Page ─────────────────────────────────────────────────────────
    def _build_spotify_page(self) -> QWidget:
        """Build the Spotify page with client ID/secret fields and a browser authorization button."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 8, 4, 8)
        lay.setSpacing(8)

        desc = QLabel("Obtain Client ID & Secret from https://developer.spotify.com/dashboard")
        desc.setFont(QFont("Consolas", 7))
        desc.setStyleSheet(f"color: {ThemeChrome.get_active().palette.text_med};")
        lay.addWidget(desc)

        lay.addWidget(self._lbl("SPOTIFY CLIENT ID (32 CHARACTERS)"))
        self._spot_cid = QLineEdit()
        self._spot_cid.setEchoMode(QLineEdit.EchoMode.Password)
        self._spot_cid.setPlaceholderText("32-character hexadecimal Client ID")
        self._spot_cid.setStyleSheet(self._field_style())
        lay.addWidget(self._spot_cid)

        lay.addWidget(self._lbl("SPOTIFY CLIENT SECRET (32 CHARACTERS)"))
        self._spot_secret = QLineEdit()
        self._spot_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self._spot_secret.setPlaceholderText("32-character hexadecimal Client Secret")
        self._spot_secret.setStyleSheet(self._field_style())
        lay.addWidget(self._spot_secret)

        oauth_row = QHBoxLayout()
        self._spot_auth_btn = QPushButton("◈  AUTHORIZE SPOTIFY (CONNECT VIA BROWSER)")
        self._spot_auth_btn.setFixedHeight(26)
        self._spot_auth_btn.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        self._spot_auth_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        pal = ThemeChrome.get_active().palette
        self._spot_auth_btn.setStyleSheet(f"""
            QPushButton {{
                background: {pal.panel2};
                color: {pal.green};
                border: 1px solid {pal.green};
                border-radius: 2px;
            }}
            QPushButton:hover {{
                background: {pal.green};
                color: {pal.dark};
            }}
        """)
        self._spot_auth_btn.clicked.connect(self._start_spotify_oauth)
        oauth_row.addWidget(self._spot_auth_btn)
        lay.addLayout(oauth_row)

        lay.addStretch()
        return w

    # ── Gmail Page ───────────────────────────────────────────────────────────
    def _build_gmail_page(self) -> QWidget:
        """Build the Gmail page with a mode toggle between app-password fields and an OAuth credentials JSON editor."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 8, 4, 8)
        lay.setSpacing(8)

        mode_row = QHBoxLayout()
        self._gmail_mode_pw = QPushButton("APP PASSWORD")
        self._gmail_mode_pw.setCheckable(True)
        self._gmail_mode_pw.setChecked(True)
        self._gmail_mode_pw.setFont(QFont("Consolas", 7, QFont.Weight.Bold))
        self._gmail_mode_pw.setFixedHeight(24)

        self._gmail_mode_oauth = QPushButton("OAUTH JSON")
        self._gmail_mode_oauth.setCheckable(True)
        self._gmail_mode_oauth.setFont(QFont("Consolas", 7, QFont.Weight.Bold))
        self._gmail_mode_oauth.setFixedHeight(24)

        self._gmail_mode_pw.clicked.connect(lambda: self._set_gmail_mode("api_key"))
        self._gmail_mode_oauth.clicked.connect(lambda: self._set_gmail_mode("oauth_json"))

        mode_row.addWidget(self._gmail_mode_pw)
        mode_row.addWidget(self._gmail_mode_oauth)
        mode_row.addStretch()
        lay.addLayout(mode_row)

        self._gmail_stack = QStackedWidget()

        # Page 1: App password
        pw_w = QWidget()
        pw_lay = QVBoxLayout(pw_w)
        pw_lay.setContentsMargins(0, 0, 0, 0)
        pw_lay.setSpacing(6)

        pw_lay.addWidget(self._lbl("GMAIL USER EMAIL"))
        self._gmail_email = QLineEdit()
        self._gmail_email.setPlaceholderText("operator@gmail.com")
        self._gmail_email.setStyleSheet(self._field_style())
        pw_lay.addWidget(self._gmail_email)

        pw_lay.addWidget(self._lbl("GOOGLE APP PASSWORD (16 CHARS)"))
        self._gmail_pw = QLineEdit()
        self._gmail_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._gmail_pw.setPlaceholderText("abcd efgh ijkl mnop")
        self._gmail_pw.setStyleSheet(self._field_style())
        pw_lay.addWidget(self._gmail_pw)

        self._gmail_stack.addWidget(pw_w)

        # Page 2: OAuth credentials JSON
        oauth_w = QWidget()
        oauth_lay = QVBoxLayout(oauth_w)
        oauth_lay.setContentsMargins(0, 0, 0, 0)
        oauth_lay.setSpacing(6)

        oauth_lay.addWidget(self._lbl("PASTE CREDENTIALS.JSON CONTENT"))
        self._gmail_json = QTextEdit()
        self._gmail_json.setPlaceholderText('{\n  "installed": {\n    "client_id": "...",\n    "client_secret": "..."\n  }\n}')
        self._gmail_json.setStyleSheet(self._field_style())
        oauth_lay.addWidget(self._gmail_json)

        self._gmail_stack.addWidget(oauth_w)
        lay.addWidget(self._gmail_stack)

        self._set_gmail_mode("api_key")
        return w

    def _set_gmail_mode(self, mode: str) -> None:
        """Switch the Gmail page between app-password and OAuth JSON modes, updating button states and the stacked page."""
        pal = ThemeChrome.get_active().palette
        active_ss = f"background: {pal.pri}; color: {pal.dark}; border: 1px solid {pal.pri}; font-weight: bold;"
        idle_ss = f"background: {pal.panel2}; color: {pal.text_med}; border: 1px solid {pal.border_a};"

        if mode == "api_key":
            self._gmail_mode_pw.setChecked(True)
            self._gmail_mode_pw.setStyleSheet(active_ss)
            self._gmail_mode_oauth.setChecked(False)
            self._gmail_mode_oauth.setStyleSheet(idle_ss)
            self._gmail_stack.setCurrentIndex(0)
        else:
            self._gmail_mode_pw.setChecked(False)
            self._gmail_mode_pw.setStyleSheet(idle_ss)
            self._gmail_mode_oauth.setChecked(True)
            self._gmail_mode_oauth.setStyleSheet(active_ss)
            self._gmail_stack.setCurrentIndex(1)

    # ── Alexa Page ───────────────────────────────────────────────────────────
    def _build_alexa_page(self) -> QWidget:
        """Build the Alexa page as a stack holding the overview widget and the permissions widget."""
        self._alexa_stack = QStackedWidget()
        self._alexa_overview_widget = self._build_alexa_overview()
        self._alexa_perms_widget = self._build_alexa_permissions_widget()
        self._alexa_stack.addWidget(self._alexa_overview_widget)
        self._alexa_stack.addWidget(self._alexa_perms_widget)
        return self._alexa_stack

    def _build_alexa_overview(self) -> QWidget:
        """Build the scrollable Alexa overview: connection status, connect/disconnect and permissions buttons,
        linking instructions, and a collapsible developer configuration section.
        """
        pal = ThemeChrome.get_active().palette

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                width: 6px;
                background: transparent;
            }
            QScrollBar::handle:vertical {
                background: rgba(142, 155, 255, 0.25);
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #8e9bff;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 4, 10, 8)
        lay.setSpacing(10)

        desc = QLabel("Connect your Amazon Echo or Alexa app to ALFRED via the Alexa Custom Skill.")
        desc.setFont(QFont("Consolas", 7))
        desc.setStyleSheet(f"color: {pal.text_med};")
        lay.addWidget(desc)

        # ── User Mode Panel ──────────────────────────────────────────────────
        user_card = QFrame()
        user_card.setStyleSheet(f"""
            QFrame {{
                background-color: {pal.panel2};
                border: 1px solid {pal.border_a};
                border-radius: 4px;
            }}
        """)
        user_lay = QVBoxLayout(user_card)
        user_lay.setContentsMargins(12, 12, 12, 12)
        user_lay.setSpacing(10)

        # Status row
        status_row = QHBoxLayout()
        st_title = QLabel("CONNECTION STATUS:")
        st_title.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        st_title.setStyleSheet(f"color: {pal.text_bright}; border: none; background: transparent;")
        status_row.addWidget(st_title)

        self._alexa_status_badge = QLabel("NOT CONFIGURED")
        self._alexa_status_badge.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        self._alexa_status_badge.setStyleSheet(f"color: {COLOR_YELLOW}; border: none; background: transparent;")
        status_row.addWidget(self._alexa_status_badge)
        status_row.addStretch()
        user_lay.addLayout(status_row)

        # Connect / Disconnect Buttons row
        action_row = QHBoxLayout()
        self._alexa_connect_btn = QPushButton("◈  CONNECT ALEXA")
        self._alexa_connect_btn.setFixedHeight(30)
        self._alexa_connect_btn.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        self._alexa_connect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._alexa_connect_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0, 240, 255, 0.15);
                color: {COLOR_CYAN};
                border: 1px solid {COLOR_CYAN};
                border-radius: 2px;
                padding: 0 14px;
            }}
            QPushButton:hover {{
                background: {COLOR_CYAN};
                color: {pal.dark};
            }}
        """)
        self._alexa_connect_btn.clicked.connect(self._start_alexa_linking)
        action_row.addWidget(self._alexa_connect_btn)

        self._alexa_disconnect_btn = QPushButton("DISCONNECT")
        self._alexa_disconnect_btn.setFixedHeight(30)
        self._alexa_disconnect_btn.setFont(QFont("Consolas", 8))
        self._alexa_disconnect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._alexa_disconnect_btn.setStyleSheet(f"""
            QPushButton {{
                background: {pal.panel};
                color: {pal.text_med};
                border: 1px solid {pal.border_a};
                border-radius: 2px;
                padding: 0 10px;
            }}
            QPushButton:hover {{
                border-color: {pal.red};
                color: {pal.red};
            }}
        """)
        self._alexa_disconnect_btn.clicked.connect(self._on_alexa_disconnect)
        action_row.addWidget(self._alexa_disconnect_btn)
        action_row.addStretch()
        user_lay.addLayout(action_row)

        # Permissions row
        perms_row = QHBoxLayout()
        self._alexa_allowed_count_lbl = QLabel(f"ALLOWED COMMANDS: {self._alexa_policy.count_allowed_intents()}")
        self._alexa_allowed_count_lbl.setFont(QFont("Consolas", 8))
        self._alexa_allowed_count_lbl.setStyleSheet(f"color: {pal.text_med}; border: none; background: transparent;")
        perms_row.addWidget(self._alexa_allowed_count_lbl)

        self._alexa_perms_btn = QPushButton("⚙  MANAGE PERMISSIONS")
        self._alexa_perms_btn.setFixedHeight(24)
        self._alexa_perms_btn.setFont(QFont("Consolas", 7, QFont.Weight.Bold))
        self._alexa_perms_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._alexa_perms_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {pal.pri};
                border: 1px solid {pal.pri};
                border-radius: 2px;
                padding: 0 8px;
            }}
            QPushButton:hover {{
                background: {pal.pri};
                color: {pal.dark};
            }}
        """)
        self._alexa_perms_btn.clicked.connect(self._open_alexa_permissions)
        perms_row.addWidget(self._alexa_perms_btn)
        perms_row.addStretch()
        user_lay.addLayout(perms_row)

        # Dynamic Linking Container (hidden by default)
        self._alexa_link_container = QWidget()
        link_lay = QVBoxLayout(self._alexa_link_container)
        link_lay.setContentsMargins(0, 4, 0, 0)
        link_lay.setSpacing(6)

        self._alexa_link_instruct = QLabel("“Enable the ALFRED skill in the Alexa app, then link your account, sir.”")
        self._alexa_link_instruct.setFont(QFont("Consolas", 7, QFont.Weight.Medium))
        self._alexa_link_instruct.setStyleSheet(f"color: {COLOR_CYAN}; border: none; background: transparent;")
        link_lay.addWidget(self._alexa_link_instruct)

        qr_box = QHBoxLayout()
        self._alexa_qr_label = QLabel()
        self._alexa_qr_label.setFixedSize(96, 96)
        self._alexa_qr_label.setStyleSheet(f"border: 1px solid {pal.border_a}; background: #02060b;")
        self._alexa_qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qr_box.addWidget(self._alexa_qr_label)

        self._alexa_link_url_input = QLineEdit()
        self._alexa_link_url_input.setReadOnly(True)
        self._alexa_link_url_input.setFixedHeight(28)
        self._alexa_link_url_input.setStyleSheet(self._field_style())
        qr_box.addWidget(self._alexa_link_url_input, stretch=1)
        link_lay.addLayout(qr_box)

        self._alexa_link_container.setVisible(False)
        user_lay.addWidget(self._alexa_link_container)

        lay.addWidget(user_card)

        # ── Developer Configuration Section ──────────────────────────────────
        dev_toggle_row = QHBoxLayout()
        self._alexa_dev_toggle_btn = QPushButton("▸  DEVELOPER CONFIGURATION")
        self._alexa_dev_toggle_btn.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        self._alexa_dev_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._alexa_dev_toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {pal.text_dim};
                border: none;
                text-align: left;
                padding: 4px 0;
            }}
            QPushButton:hover {{
                color: {pal.pri};
            }}
        """)
        self._alexa_dev_toggle_btn.clicked.connect(self._toggle_alexa_dev_panel)
        dev_toggle_row.addWidget(self._alexa_dev_toggle_btn)
        dev_toggle_row.addStretch()
        lay.addLayout(dev_toggle_row)

        self._alexa_dev_widget = QFrame()
        self._alexa_dev_widget.setObjectName("alexa_dev_card")
        self._alexa_dev_widget.setStyleSheet(f"""
            QFrame#alexa_dev_card {{
                background-color: {pal.panel2};
                border: 1px solid {pal.border_a};
                border-radius: 4px;
            }}
        """)
        dev_lay = QVBoxLayout(self._alexa_dev_widget)
        dev_lay.setContentsMargins(12, 12, 12, 12)
        dev_lay.setSpacing(6)

        dev_lay.addWidget(self._lbl("SKILL ID"))
        self._alexa_skill_id = QLineEdit()
        self._alexa_skill_id.setFixedHeight(28)
        self._alexa_skill_id.setPlaceholderText("amzn1.ask.skill.xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
        self._alexa_skill_id.setStyleSheet(self._field_style())
        dev_lay.addWidget(self._alexa_skill_id)

        dev_lay.addWidget(self._lbl("RELAY HTTPS URL"))
        self._alexa_relay_https = QLineEdit()
        self._alexa_relay_https.setFixedHeight(28)
        self._alexa_relay_https.setPlaceholderText("https://relay.yourdomain.com")
        self._alexa_relay_https.setStyleSheet(self._field_style())
        dev_lay.addWidget(self._alexa_relay_https)

        dev_lay.addWidget(self._lbl("RELAY WEBSOCKET URL"))
        self._alexa_relay_ws = QLineEdit()
        self._alexa_relay_ws.setFixedHeight(28)
        self._alexa_relay_ws.setPlaceholderText("wss://relay.yourdomain.com/ws/desktop")
        self._alexa_relay_ws.setStyleSheet(self._field_style())
        dev_lay.addWidget(self._alexa_relay_ws)

        dev_lay.addWidget(self._lbl("SKILL STORE / ACCOUNT LINKING URL"))
        self._alexa_store_url = QLineEdit()
        self._alexa_store_url.setFixedHeight(28)
        self._alexa_store_url.setPlaceholderText("https://alexa-skills.amazon.com/...")
        self._alexa_store_url.setStyleSheet(self._field_style())
        dev_lay.addWidget(self._alexa_store_url)

        dev_lay.addWidget(self._lbl("OAUTH CLIENT ID"))
        self._alexa_oauth_cid = QLineEdit()
        self._alexa_oauth_cid.setFixedHeight(28)
        self._alexa_oauth_cid.setPlaceholderText("alfred_alexa_client")
        self._alexa_oauth_cid.setStyleSheet(self._field_style())
        dev_lay.addWidget(self._alexa_oauth_cid)

        dev_lay.addWidget(self._lbl("OAUTH CLIENT SECRET"))
        self._alexa_oauth_csecret = QLineEdit()
        self._alexa_oauth_csecret.setFixedHeight(28)
        self._alexa_oauth_csecret.setEchoMode(QLineEdit.EchoMode.Password)
        self._alexa_oauth_csecret.setPlaceholderText("Client secret (masked)")
        self._alexa_oauth_csecret.setStyleSheet(self._field_style())
        dev_lay.addWidget(self._alexa_oauth_csecret)

        dev_lay.addWidget(self._lbl("OAUTH REDIRECT URL"))
        self._alexa_redirect_url = QLineEdit()
        self._alexa_redirect_url.setFixedHeight(28)
        self._alexa_redirect_url.setPlaceholderText("https://pitangui.amazon.com/api/skill/link/...")
        self._alexa_redirect_url.setStyleSheet(self._field_style())
        dev_lay.addWidget(self._alexa_redirect_url)

        dev_btn_row = QHBoxLayout()
        self._alexa_validate_btn = QPushButton("VALIDATE CONFIGURATION")
        self._alexa_validate_btn.setFixedHeight(28)
        self._alexa_validate_btn.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        self._alexa_validate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._alexa_validate_btn.setStyleSheet(f"""
            QPushButton {{
                background: {pal.panel2};
                color: {COLOR_YELLOW};
                border: 1px solid {COLOR_YELLOW};
                border-radius: 2px;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background: {COLOR_YELLOW};
                color: {pal.dark};
            }}
        """)
        self._alexa_validate_btn.clicked.connect(self._validate_alexa_dev_config)
        dev_btn_row.addWidget(self._alexa_validate_btn)

        self._alexa_save_dev_btn = QPushButton("SAVE CONFIGURATION")
        self._alexa_save_dev_btn.setFixedHeight(28)
        self._alexa_save_dev_btn.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        self._alexa_save_dev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._alexa_save_dev_btn.setStyleSheet(f"""
            QPushButton {{
                background: {pal.panel2};
                color: {pal.green};
                border: 1px solid {pal.green};
                border-radius: 2px;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background: {pal.green};
                color: {pal.dark};
            }}
        """)
        self._alexa_save_dev_btn.clicked.connect(self._save_alexa_dev_config)
        dev_btn_row.addWidget(self._alexa_save_dev_btn)
        dev_btn_row.addStretch()
        dev_lay.addLayout(dev_btn_row)

        self._alexa_dev_widget.setVisible(False)
        lay.addWidget(self._alexa_dev_widget)

        lay.addStretch()
        scroll.setWidget(w)
        return scroll

    def _build_alexa_permissions_widget(self) -> QWidget:
        """Dedicated permissions manager embedded directly inside the Alexa tab."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(8)

        pal = ThemeChrome.get_active().palette

        # ── Top Navigation Bar ───────────────────────────────────────────────
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        back_btn = QPushButton("❮  BACK TO OVERVIEW")
        back_btn.setFixedHeight(26)
        back_btn.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0, 240, 255, 0.12);
                color: {COLOR_CYAN};
                border: 1px solid {COLOR_CYAN};
                border-radius: 2px;
                padding: 0 10px;
            }}
            QPushButton:hover {{
                background: {COLOR_CYAN};
                color: {pal.dark};
            }}
        """)
        back_btn.clicked.connect(self._close_alexa_permissions)
        top_row.addWidget(back_btn)

        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        title_lbl = QLabel("◈  ALEXA CAPABILITY PERMISSIONS")
        title_lbl.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color: {pal.pri}; border: none; background: transparent;")
        title_box.addWidget(title_lbl)

        sub_lbl = QLabel("CONFIGURE APPROVED VOICE DIRECTIVES // ZERO SHELL OR CODE EGRESS")
        sub_lbl.setFont(QFont("Consolas", 7))
        sub_lbl.setStyleSheet(f"color: {pal.text_dim}; border: none; background: transparent;")
        title_box.addWidget(sub_lbl)
        top_row.addLayout(title_box)
        top_row.addStretch()
        lay.addLayout(top_row)

        # ── Scroll Area for Directives ───────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                width: 6px;
                background: transparent;
            }
            QScrollBar::handle:vertical {
                background: #1f364d;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: #00f0ff;
            }
        """)

        content = QWidget()
        c_lay = QVBoxLayout(content)
        c_lay.setContentsMargins(0, 0, 4, 0)
        c_lay.setSpacing(8)

        # Approved Capabilities Card
        app_card = QFrame()
        app_card.setStyleSheet(f"""
            QFrame {{
                background-color: {pal.panel2};
                border: 1px solid {pal.border_a};
                border-radius: 4px;
            }}
        """)
        app_lay = QVBoxLayout(app_card)
        app_lay.setContentsMargins(12, 10, 12, 10)
        app_lay.setSpacing(8)

        app_title = QLabel("APPROVED VOICE DIRECTIVES")
        app_title.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        app_title.setStyleSheet(f"color: {COLOR_CYAN}; border: none; background: transparent;")
        app_lay.addWidget(app_title)

        self._alexa_perms_checkboxes = {}
        for cap_id, cap_title, cap_desc, default_val in CAPABILITY_DEFINITIONS:
            item_box = QVBoxLayout()
            item_box.setSpacing(2)

            cb = QCheckBox(f"✓  {cap_title}")
            cb.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
            cb.setStyleSheet(f"""
                QCheckBox {{
                    color: {pal.text_bright};
                    spacing: 8px;
                    background: transparent;
                    border: none;
                }}
                QCheckBox::indicator {{
                    width: 14px;
                    height: 14px;
                    border: 1px solid {pal.pri};
                    background: {pal.panel};
                    border-radius: 2px;
                }}
                QCheckBox::indicator:hover {{
                    border-color: #ffffff;
                }}
                QCheckBox::indicator:checked {{
                    background: {pal.pri};
                }}
            """)
            cb.setChecked(default_val)
            self._alexa_perms_checkboxes[cap_id] = cb
            item_box.addWidget(cb)

            desc_lbl = QLabel(cap_desc)
            desc_lbl.setFont(QFont("Consolas", 7))
            desc_lbl.setStyleSheet(f"color: {pal.text_med}; margin-left: 22px; border: none; background: transparent;")
            item_box.addWidget(desc_lbl)

            app_lay.addLayout(item_box)

        c_lay.addWidget(app_card)

        # Prohibited Capabilities Card
        den_card = QFrame()
        den_card.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(255, 42, 85, 0.05);
                border: 1px solid rgba(255, 42, 85, 0.35);
                border-radius: 4px;
            }}
        """)
        den_lay = QVBoxLayout(den_card)
        den_lay.setContentsMargins(12, 8, 12, 8)
        den_lay.setSpacing(4)

        den_title = QLabel("PROHIBITED CAPABILITIES (ALWAYS DENIED BY SECURITY POLICY)")
        den_title.setFont(QFont("Consolas", 7, QFont.Weight.Bold))
        den_title.setStyleSheet(f"color: {pal.red}; border: none; background: transparent;")
        den_lay.addWidget(den_title)

        for d_title, d_desc in PROHIBITED_CAPABILITIES:
            d_row = QHBoxLayout()
            d_lbl = QLabel(f"✕  {d_title}")
            d_lbl.setFont(QFont("Consolas", 7))
            d_lbl.setStyleSheet(f"color: {pal.text_dim}; border: none; background: transparent;")
            d_row.addWidget(d_lbl)
            d_row.addStretch()

            tag = QLabel("[RESTRICTED]")
            tag.setFont(QFont("Consolas", 7, QFont.Weight.Bold))
            tag.setStyleSheet(f"color: {pal.red}; border: none; background: transparent;")
            d_row.addWidget(tag)
            den_lay.addLayout(d_row)

        c_lay.addWidget(den_card)
        scroll.setWidget(content)
        lay.addWidget(scroll, stretch=1)

        # ── Footer Actions ───────────────────────────────────────────────────
        foot = QHBoxLayout()
        reset_btn = QPushButton("↺  RESET DEFAULTS")
        reset_btn.setFont(QFont("Consolas", 7, QFont.Weight.Bold))
        reset_btn.setFixedSize(130, 28)
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.setStyleSheet(f"""
            QPushButton {{
                background: {pal.panel2};
                color: {pal.text_med};
                border: 1px solid {pal.border_a};
                border-radius: 2px;
            }}
            QPushButton:hover {{ color: #ffffff; border-color: {COLOR_YELLOW}; }}
        """)
        reset_btn.clicked.connect(self._reset_alexa_perms_defaults)
        foot.addWidget(reset_btn)

        foot.addStretch()

        save_btn = QPushButton("✓  SAVE & APPLY PERMISSIONS")
        save_btn.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        save_btn.setFixedSize(190, 28)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0, 240, 255, 0.2);
                color: {COLOR_CYAN};
                border: 1px solid {COLOR_CYAN};
                border-radius: 2px;
            }}
            QPushButton:hover {{
                background: {COLOR_CYAN};
                color: {pal.dark};
            }}
        """)
        save_btn.clicked.connect(lambda: self._save_alexa_perms(and_return=True))
        foot.addWidget(save_btn)

        lay.addLayout(foot)
        return w

    def _refresh_alexa_ui_state(self) -> None:
        """Update Alexa status badge and allowed commands count."""
        pal = ThemeChrome.get_active().palette
        snap = self._alexa_state_mgr.get_snapshot()

        status_map = {
            AlexaConnectionStatus.NOT_CONFIGURED: ("NOT CONFIGURED", COLOR_YELLOW),
            AlexaConnectionStatus.READY_TO_LINK: ("READY TO LINK", COLOR_CYAN),
            AlexaConnectionStatus.LINK_PENDING: ("LINKING IN PROGRESS...", COLOR_CYAN),
            AlexaConnectionStatus.CONNECTED: ("CONNECTED", pal.green),
            AlexaConnectionStatus.OFFLINE: ("OFFLINE", pal.red),
            AlexaConnectionStatus.ERROR: ("ERROR", pal.red),
        }
        text, color = status_map.get(snap.status, ("UNKNOWN", pal.text_med))
        if hasattr(self, "_alexa_status_badge"):
            self._alexa_status_badge.setText(text)
            self._alexa_status_badge.setStyleSheet(f"color: {color}; border: none; background: transparent;")

        if hasattr(self, "_alexa_allowed_count_lbl"):
            cnt = self._alexa_policy.count_allowed_intents()
            self._alexa_allowed_count_lbl.setText(f"ALLOWED COMMANDS: {cnt}")

    def _start_alexa_linking(self) -> None:
        """Initiate short-lived account linking state and display instructions/QR code."""
        cfg = load_alexa_config_from_store(self.store)
        if not cfg.is_configured() and not self._alexa_skill_id.text().strip():
            self._status_lbl.setText("⚠ Please configure Alexa Skill ID and Relay URL first.")
            self._status_lbl.setStyleSheet("color: #ffaa00;")
            self._alexa_dev_widget.setVisible(True)
            self._alexa_dev_toggle_btn.setText("▾  DEVELOPER CONFIGURATION")
            return

        token = self._alexa_linking_mgr.create_linking_state("desktop_main")
        base_url = cfg.relay_https_url or "http://localhost:8000"
        link_url = f"{base_url.rstrip('/')}/api/alexa/link?state={token}"

        self._alexa_link_url_input.setText(link_url)
        self._render_qr_code(link_url)
        self._alexa_link_container.setVisible(True)
        self._alexa_state_mgr.set_linking_pending()
        self._refresh_alexa_ui_state()

        self._status_lbl.setText("Account linking initiated. Enable the skill and link your Echo account.")
        self._status_lbl.setStyleSheet(f"color: {COLOR_CYAN};")

        import webbrowser
        try:
            webbrowser.open(link_url)
        except Exception:
            pass

    def _render_qr_code(self, data: str) -> None:
        """Render QR code pixmap for linking URL."""
        try:
            import io
            import qrcode
            from PyQt6.QtGui import QImage, QPixmap
            qr = qrcode.QRCode(box_size=3, border=1)
            qr.add_data(data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="white", back_color="black")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            qimg = QImage.fromData(buf.getvalue())
            pix = QPixmap.fromImage(qimg)
            self._alexa_qr_label.setPixmap(pix.scaled(96, 96, Qt.AspectRatioMode.KeepAspectRatio))
        except Exception:
            self._alexa_qr_label.setText("[QR Code]")

    def _on_alexa_disconnect(self) -> None:
        """Revoke Alexa linking state and tokens without touching other integrations."""
        self.store.delete("alexa.oauth_access_token")
        self.store.delete("alexa.oauth_refresh_token")
        self._alexa_state_mgr.set_linked(False)
        self._alexa_link_container.setVisible(False)
        self._refresh_alexa_ui_state()
        self._status_lbl.setText("Alexa connection unlinked and local tokens revoked.")
        self._status_lbl.setStyleSheet(f"color: {COLOR_YELLOW};")

    def _toggle_alexa_dev_panel(self) -> None:
        """Toggle collapsed developer panel."""
        is_vis = not self._alexa_dev_widget.isVisible()
        self._alexa_dev_widget.setVisible(is_vis)
        self._alexa_dev_toggle_btn.setText("▾  DEVELOPER CONFIGURATION" if is_vis else "▸  DEVELOPER CONFIGURATION")

    def _open_alexa_permissions(self) -> None:
        """Switch to capability permissions view inside the Alexa tab."""
        self._load_alexa_perms_values()
        self._alexa_stack.setCurrentIndex(1)

    def _close_alexa_permissions(self) -> None:
        """Return from permissions view to Alexa overview view."""
        self._alexa_stack.setCurrentIndex(0)

    def _load_alexa_perms_values(self) -> None:
        """Load stored permission values into checkboxes."""
        for cap_id, cb in getattr(self, "_alexa_perms_checkboxes", {}).items():
            stored = self.store.get(f"alexa.perm.{cap_id}")
            if stored is not None:
                cb.setChecked(stored.strip().lower() == "true")
            else:
                cb.setChecked(self._alexa_policy.is_capability_enabled(cap_id))

    def _reset_alexa_perms_defaults(self) -> None:
        """Reset permissions checkboxes to safe defaults."""
        for cap_id, cap_title, cap_desc, default_val in CAPABILITY_DEFINITIONS:
            if cap_id in getattr(self, "_alexa_perms_checkboxes", {}):
                self._alexa_perms_checkboxes[cap_id].setChecked(default_val)

    def _save_alexa_perms(self, and_return: bool = True) -> None:
        """Save permissions to SecretStore and AlexaActionPolicy."""
        for cap_id, cb in getattr(self, "_alexa_perms_checkboxes", {}).items():
            enabled = cb.isChecked()
            self._alexa_policy.set_capability_enabled(cap_id, enabled)
            self.store.set(f"alexa.perm.{cap_id}", str(enabled).lower())
        self._alexa_allowed_count_lbl.setText(f"ALLOWED COMMANDS: {self._alexa_policy.count_allowed_intents()}")
        self._status_lbl.setText("✓ Alexa permissions saved and active.")
        self._status_lbl.setStyleSheet(f"color: {ThemeChrome.get_active().palette.green};")
        if and_return:
            self._alexa_stack.setCurrentIndex(0)

    def _validate_alexa_dev_config(self) -> None:
        """Validate developer parameters non-blockingly."""
        fields = {
            "skill_id": self._alexa_skill_id.text().strip(),
            "relay_https_url": self._alexa_relay_https.text().strip(),
            "relay_ws_url": self._alexa_relay_ws.text().strip(),
            "oauth_redirect_url": self._alexa_redirect_url.text().strip(),
        }
        ok, err = validate_backend_fields("alexa", fields)
        pal = ThemeChrome.get_active().palette
        if not ok:
            self._status_lbl.setText(f"✕ {err}")
            self._status_lbl.setStyleSheet(f"color: {pal.red};")
            return

        self._status_lbl.setText("✓ Alexa configuration format is valid.")
        self._status_lbl.setStyleSheet(f"color: {pal.green};")

    def _save_alexa_dev_config(self) -> None:
        """Explicit save for Alexa configuration."""
        self._switch_tab(3)
        self._on_submit_current_tab(sync=False)

    def _load_alexa_values(self) -> None:
        """Load stored Alexa parameters into fields."""
        cfg = load_alexa_config_from_store(self.store)
        if cfg.skill_id:
            self._alexa_skill_id.setText(cfg.skill_id)
        if cfg.relay_https_url:
            self._alexa_relay_https.setText(cfg.relay_https_url)
        if cfg.relay_ws_url:
            self._alexa_relay_ws.setText(cfg.relay_ws_url)
        if cfg.skill_store_url:
            self._alexa_store_url.setText(cfg.skill_store_url)
        if cfg.oauth_client_id:
            self._alexa_oauth_cid.setText(cfg.oauth_client_id)
        if cfg.oauth_client_secret:
            self._alexa_oauth_csecret.setText(cfg.oauth_client_secret)
        if cfg.oauth_redirect_url:
            self._alexa_redirect_url.setText(cfg.oauth_redirect_url)

        is_conf = bool(cfg.skill_id)
        self._alexa_state_mgr.set_configured(is_conf)
        self._refresh_alexa_ui_state()

    def _switch_tab(self, idx: int) -> None:
        """Select the backend tab at the clamped index, restyle the tab buttons and clear the status label."""
        self._active_tab_idx = max(0, min(len(self._backend_ids) - 1, idx))
        self._stack.setCurrentIndex(self._active_tab_idx)

        pal = ThemeChrome.get_active().palette
        for i, b in enumerate(self._tab_buttons):
            on = (i == self._active_tab_idx)
            b.setChecked(on)
            if on:
                b.setStyleSheet(f"""
                    QPushButton {{
                        background: {pal.pri};
                        color: {pal.dark};
                        border: 1px solid {pal.pri};
                        border-radius: 2px;
                    }}
                """)
            else:
                b.setStyleSheet(f"""
                    QPushButton {{
                        background: {pal.panel2};
                        color: {pal.text_med};
                        border: 1px solid {pal.border_a};
                        border-radius: 2px;
                    }}
                    QPushButton:hover {{
                        color: #ffffff;
                        border-color: {pal.pri};
                    }}
                """)
        self._status_lbl.setText("")

    def _load_current_values(self) -> None:
        """Load masked credentials from SecretStore with fallback to config/api_keys.json."""
        # Google Workspace
        gw_cid = (self.store.get("google_workspace.client_id") or "").strip()
        gw_secret = (self.store.get("google_workspace.client_secret") or "").strip()
        if not gw_cid or not gw_secret:
            try:
                from actions.spotify_control import API_CONFIG_PATH
                if API_CONFIG_PATH.exists():
                    cfg = json.loads(API_CONFIG_PATH.read_text(encoding="utf-8"))
                    if not gw_cid:
                        gw_cid = (cfg.get("google_workspace_client_id") or "").strip()
                    if not gw_secret:
                        gw_secret = (cfg.get("google_workspace_client_secret") or "").strip()
            except Exception:
                pass

        if gw_cid:
            self._gw_cid.setText(gw_cid)
        if gw_secret:
            self._gw_secret.setText(gw_secret)

        # Spotify
        from actions.spotify_control import _is_placeholder, API_CONFIG_PATH
        spot_cid = self.store.get("spotify.client_id") or ""
        spot_secret = self.store.get("spotify.client_secret") or ""

        if _is_placeholder(spot_cid) or _is_placeholder(spot_secret):
            try:
                if API_CONFIG_PATH.exists():
                    cfg = json.loads(API_CONFIG_PATH.read_text(encoding="utf-8"))
                    if _is_placeholder(spot_cid):
                        spot_cid = cfg.get("spotify_client_id", "")
                    if _is_placeholder(spot_secret):
                        spot_secret = cfg.get("spotify_client_secret", "")
            except Exception:
                pass

        if spot_cid and not _is_placeholder(spot_cid):
            self._spot_cid.setText(spot_cid)
        if spot_secret and not _is_placeholder(spot_secret):
            self._spot_secret.setText(spot_secret)

        # Gmail
        gmail_email = (self.store.get("gmail.email") or self.store.get("gmail.user") or "").strip()
        gmail_pw = (self.store.get("gmail.app_password") or self.store.get("gmail.api_key") or "").strip()
        if not gmail_email or not gmail_pw:
            try:
                from actions.gmail_manager import _CONFIG_PATH
                if _CONFIG_PATH.exists():
                    cfg = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
                    gmail_email = gmail_email or (cfg.get("gmail_user") or cfg.get("gmail_email") or cfg.get("email") or "").strip()
                    gmail_pw = gmail_pw or (cfg.get("gmail_app_password") or cfg.get("gmail_passkey") or cfg.get("gmail_password") or cfg.get("app_password") or "").strip()
            except Exception:
                pass

        if gmail_email:
            self._gmail_email.setText(gmail_email)
        if gmail_pw:
            self._gmail_pw.setText(gmail_pw)
        if self.store.has("gmail.credentials_json"):
            self._gmail_json.setPlainText(self.store.get("gmail.credentials_json") or "")
            self._set_gmail_mode("oauth_json")

        # Alexa
        self._load_alexa_values()

    def _start_google_oauth(self) -> None:
        """Validate the Google client ID and secret, then run the Google OAuth flow on a background thread."""
        cid = self._gw_cid.text().strip()
        csecret = self._gw_secret.text().strip()
        if not cid or not csecret:
            self._status_lbl.setText("⚠ Please enter Google Client ID and Secret first.")
            self._status_lbl.setStyleSheet("color: #ffaa00;")
            return

        self._status_lbl.setText("Opening browser for Google authorization...")
        self._status_lbl.setStyleSheet(f"color: {COLOR_CYAN};")

        def worker():
            """Persist the Google credentials to the store and API config, run the OAuth flow and emit the result."""
            if cid:
                self.store.set("google_workspace.client_id", cid)
            if csecret:
                self.store.set("google_workspace.client_secret", csecret)
            try:
                from actions.spotify_control import API_CONFIG_PATH
                if API_CONFIG_PATH.exists():
                    cfg = json.loads(API_CONFIG_PATH.read_text(encoding="utf-8"))
                    if cid:
                        cfg["google_workspace_client_id"] = cid
                    if csecret:
                        cfg["google_workspace_client_secret"] = csecret
                    API_CONFIG_PATH.write_text(json.dumps(cfg, indent=4), encoding="utf-8")
            except Exception:
                pass
            from core.apis.oauth import GoogleOAuthFlow
            flow = GoogleOAuthFlow(cid, csecret, store=self.store)
            ok, err_type, msg = flow.execute()
            self._async_validation_done.emit("Google Workspace", ok, msg)

        threading.Thread(target=worker, daemon=True, name="GoogleOAuthThread").start()

    def _start_spotify_oauth(self) -> None:
        """Validate the Spotify client ID and secret, then run Spotify browser authorization on a background thread."""
        cid = self._spot_cid.text().strip()
        csecret = self._spot_secret.text().strip()
        if not cid or not csecret:
            self._status_lbl.setText("⚠ Please enter Spotify Client ID and Secret first.")
            self._status_lbl.setStyleSheet("color: #ffaa00;")
            return

        self._status_lbl.setText("Opening browser for Spotify authorization...")
        self._status_lbl.setStyleSheet(f"color: {COLOR_CYAN};")

        def worker():
            """Apply the credentials to the Spotify client, run user authorization and emit the result."""
            from actions.spotify_control import authorize_user, get_spotify_client
            client = get_spotify_client()
            client._client_id = cid
            client._client_secret = csecret
            ok = authorize_user()
            msg = "Spotify authorized and connected successfully." if ok else "Spotify authorization cancelled or timed out."
            self._async_validation_done.emit("Spotify", ok, msg)

        threading.Thread(target=worker, daemon=True, name="SpotifyOAuthThread").start()

    def _on_submit_current_tab(self, sync: bool = False) -> None:
        """Collect the active tab's credential fields and save/validate them for that backend.
        Runs on a background thread unless sync is True; the result is emitted via the validation signal.
        """
        bid = self._backend_ids[self._active_tab_idx]
        self._status_lbl.setText(f"Validating {bid}...")
        self._status_lbl.setStyleSheet(f"color: {ThemeChrome.get_active().palette.pri};")

        fields = {}
        if bid == "google_workspace":
            fields = {
                "client_id": self._gw_cid.text().strip(),
                "client_secret": self._gw_secret.text().strip(),
            }
        elif bid == "spotify":
            fields = {
                "client_id": self._spot_cid.text().strip(),
                "client_secret": self._spot_secret.text().strip(),
            }
        elif bid == "gmail":
            is_oauth = self._gmail_stack.currentIndex() == 1
            if is_oauth:
                fields = {
                    "auth_mode": "oauth_json",
                    "credentials_json": self._gmail_json.toPlainText().strip(),
                }
            else:
                fields = {
                    "auth_mode": "api_key",
                    "email": self._gmail_email.text().strip(),
                    "app_password": self._gmail_pw.text().strip(),
                }
        elif bid == "alexa":
            fields = {
                "skill_id": self._alexa_skill_id.text().strip(),
                "relay_https_url": self._alexa_relay_https.text().strip(),
                "relay_ws_url": self._alexa_relay_ws.text().strip(),
                "skill_store_url": self._alexa_store_url.text().strip(),
                "oauth_client_id": self._alexa_oauth_cid.text().strip(),
                "oauth_client_secret": self._alexa_oauth_csecret.text().strip(),
                "oauth_redirect_url": self._alexa_redirect_url.text().strip(),
            }

        def worker():
            """Save the backend credentials, mirror them into the relevant legacy config files or state, and emit the result."""
            ok, msg = save_backend_credentials(bid, fields, store=self.store)
            if ok and bid == "google_workspace":
                try:
                    from actions.spotify_control import API_CONFIG_PATH
                    if API_CONFIG_PATH.exists():
                        cfg = json.loads(API_CONFIG_PATH.read_text(encoding="utf-8"))
                        if fields.get("client_id"):
                            cfg["google_workspace_client_id"] = fields["client_id"]
                        if fields.get("client_secret"):
                            cfg["google_workspace_client_secret"] = fields["client_secret"]
                        API_CONFIG_PATH.write_text(json.dumps(cfg, indent=4), encoding="utf-8")
                except Exception:
                    pass
            elif ok and bid == "spotify":
                try:
                    from actions.spotify_control import API_CONFIG_PATH
                    if API_CONFIG_PATH.exists():
                        cfg = json.loads(API_CONFIG_PATH.read_text(encoding="utf-8"))
                        if fields.get("client_id"):
                            cfg["spotify_client_id"] = fields["client_id"]
                        if fields.get("client_secret"):
                            cfg["spotify_client_secret"] = fields["client_secret"]
                        API_CONFIG_PATH.write_text(json.dumps(cfg, indent=4), encoding="utf-8")
                except Exception:
                    pass
            elif ok and bid == "gmail":
                try:
                    from actions.gmail_manager import _CONFIG_PATH
                    if _CONFIG_PATH.exists():
                        cfg = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
                        if fields.get("email"):
                            cfg["gmail_user"] = fields["email"]
                        if fields.get("app_password"):
                            cfg["gmail_app_password"] = fields["app_password"].replace(" ", "").strip()
                        _CONFIG_PATH.write_text(json.dumps(cfg, indent=4), encoding="utf-8")
                except Exception:
                    pass
                try:
                    if fields.get("email"):
                        self.store.set("gmail.user", fields["email"])
                except Exception:
                    pass
            elif ok and bid == "alexa":
                self._alexa_state_mgr.set_configured(bool(fields.get("skill_id")))
                self._refresh_alexa_ui_state()
            backend = get_backend(bid)
            name = "Spotify" if bid == "spotify" else (backend.name if backend else bid)
            self._async_validation_done.emit(name, ok, msg)

        if sync:
            worker()
        else:
            threading.Thread(target=worker, daemon=True, name="BackendValidateThread").start()

    def _on_validation_result(self, backend_name: str, is_valid: bool, message: str) -> None:
        """Show a success or failure message in the status label; on success emit config_saved for the backend."""
        pal = ThemeChrome.get_active().palette
        if is_valid:
            self._status_lbl.setText(f"✓ {message}")
            self._status_lbl.setStyleSheet(f"color: {pal.green};")
            self.config_saved.emit(backend_name)
        else:
            self._status_lbl.setText(f"✕ {message}")
            self._status_lbl.setStyleSheet(f"color: {pal.red};")
