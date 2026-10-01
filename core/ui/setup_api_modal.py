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
from core.secrets.store import SecretStore, get_secret_store
from core.ui.themes import ThemeChrome


class _TabsProxy:
    """Compatibility proxy for tab inspection in automated test suites."""
    def __init__(self, tab_names: list[str]):
        self._names = tab_names

    def count(self) -> int:
        return len(self._names)

    def tabText(self, idx: int) -> str:
        return self._names[idx] if 0 <= idx < len(self._names) else ""


class SetupApiModal(QDialog):
    """
    Tactical glassmorphic dialog for managing encrypted API keys.
    """
    config_saved = pyqtSignal(str)   # backend_id / name
    _async_validation_done = pyqtSignal(str, bool, str)  # (backend_id_or_name, is_valid, message)

    _MODAL_W = 600
    _MODAL_H = 580

    def __init__(self, parent=None, store: Optional[SecretStore] = None):
        super().__init__(parent)
        from core.hud_video.layering import make_frameless_overlay
        make_frameless_overlay(self, parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        import core.secrets.store
        self.store = store or core.secrets.store.get_secret_store()
        self._active_tab_idx = 0
        self._backend_ids = ["google_workspace", "spotify", "gmail"]
        self._tab_buttons: list[QPushButton] = []
        self._tabs = _TabsProxy(["GOOGLE WORKSPACE", "SPOTIFY", "GMAIL API"])

        self._async_validation_done.connect(self._on_validation_result)

        self._init_ui()
        self._load_current_values()

        # UI test aliases
        self._spotify_id_input = self._spot_cid
        self._spotify_secret_input = self._spot_secret
        self._gw_id_input = self._gw_cid
        self._gw_secret_input = self._gw_secret
        self._gmail_key_input = self._gmail_pw
        self._footer_status = self._status_lbl

    def _submit_spotify(self, sync: bool = True) -> None:
        """Alias for programmatic submission in tests."""
        self._switch_tab(1)
        self._on_submit_current_tab(sync=sync)

    def _init_ui(self) -> None:
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
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = ThemeChrome.get_active().palette
        bg_col = QColor("#040c16")
        border_col = QColor(pal.border_b)
        painter.setBrush(bg_col)
        painter.setPen(QPen(border_col, 1))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 8, 8)

    def showEvent(self, event):
        super().showEvent(event)
        self._load_current_values()
        self._status_lbl.setText("")

    def _field_style(self) -> str:
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
            }}
            QLineEdit:focus, QTextEdit:focus {{
                border: 1px solid {pal.pri};
                background: rgba(142, 155, 255, 0.08);
            }}
        """

    def _lbl(self, text: str, fs: int = 7) -> QLabel:
        pal = ThemeChrome.get_active().palette
        lbl = QLabel(text)
        lbl.setFont(QFont("Consolas", fs, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {pal.text_dim}; background: transparent;")
        return lbl

    # ── Google Workspace Page ────────────────────────────────────────────────
    def _build_google_page(self) -> QWidget:
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

    def _switch_tab(self, idx: int) -> None:
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
        # Google
        if self.store.has("google_workspace.client_id"):
            self._gw_cid.setText(self.store.get("google_workspace.client_id") or "")
        if self.store.has("google_workspace.client_secret"):
            self._gw_secret.setText(self.store.get("google_workspace.client_secret") or "")

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
        if self.store.has("gmail.email"):
            self._gmail_email.setText(self.store.get("gmail.email") or "")
        if self.store.has("gmail.app_password"):
            self._gmail_pw.setText(self.store.get("gmail.app_password") or "")
        if self.store.has("gmail.credentials_json"):
            self._gmail_json.setPlainText(self.store.get("gmail.credentials_json") or "")
            self._set_gmail_mode("oauth_json")

    def _start_google_oauth(self) -> None:
        cid = self._gw_cid.text().strip()
        csecret = self._gw_secret.text().strip()
        if not cid or not csecret:
            self._status_lbl.setText("⚠ Please enter Google Client ID and Secret first.")
            self._status_lbl.setStyleSheet("color: #ffaa00;")
            return

        self._status_lbl.setText("Opening browser for Google authorization...")
        self._status_lbl.setStyleSheet(f"color: {ThemeChrome.get_active().palette.cyan};")

        def worker():
            from core.apis.oauth import GoogleOAuthFlow
            flow = GoogleOAuthFlow(cid, csecret, store=self.store)
            ok, err_type, msg = flow.execute()
            self._async_validation_done.emit("Google Workspace", ok, msg)

        threading.Thread(target=worker, daemon=True, name="GoogleOAuthThread").start()

    def _start_spotify_oauth(self) -> None:
        cid = self._spot_cid.text().strip()
        csecret = self._spot_secret.text().strip()
        if not cid or not csecret:
            self._status_lbl.setText("⚠ Please enter Spotify Client ID and Secret first.")
            self._status_lbl.setStyleSheet("color: #ffaa00;")
            return

        self._status_lbl.setText("Opening browser for Spotify authorization...")
        pal = ThemeChrome.get_active().palette
        self._status_lbl.setStyleSheet(f"color: {pal.cyan};")

        def worker():
            from actions.spotify_control import authorize_user, get_spotify_client
            client = get_spotify_client()
            client._client_id = cid
            client._client_secret = csecret
            ok = authorize_user()
            msg = "Spotify authorized and connected successfully." if ok else "Spotify authorization cancelled or timed out."
            self._async_validation_done.emit("Spotify", ok, msg)

        threading.Thread(target=worker, daemon=True, name="SpotifyOAuthThread").start()

    def _on_submit_current_tab(self, sync: bool = False) -> None:
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

        def worker():
            ok, msg = save_backend_credentials(bid, fields, store=self.store)
            if ok and bid == "spotify":
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
            backend = get_backend(bid)
            name = "Spotify" if bid == "spotify" else (backend.name if backend else bid)
            self._async_validation_done.emit(name, ok, msg)

        if sync:
            worker()
        else:
            threading.Thread(target=worker, daemon=True, name="BackendValidateThread").start()

    def _on_validation_result(self, backend_name: str, is_valid: bool, message: str) -> None:
        pal = ThemeChrome.get_active().palette
        if is_valid:
            self._status_lbl.setText(f"✓ {message}")
            self._status_lbl.setStyleSheet(f"color: {pal.green};")
            self.config_saved.emit(backend_name)
        else:
            self._status_lbl.setText(f"✕ {message}")
            self._status_lbl.setStyleSheet(f"color: {pal.red};")
