"""
ui/overlays/setup_overlay.py — Initial setup and intelligence backend configuration overlay.
"""
from __future__ import annotations

import json
import os
import platform
import threading
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui import (
    C,
    tech_font,
    mono_font,
    attach_hover_help,
    _read_full_config,
)


class SetupOverlay(QWidget):
    done = pyqtSignal(object)  # emits config dict
    setup_api_requested = pyqtSignal()
    _probe_done = pyqtSignal(str, bool, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._probe_done.connect(self._on_probe_done)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            SetupOverlay {{
                background: {C.PANEL_BG};
                border: 1px solid {C.BORDER_B};
                border-radius: 4px;
            }}
        """)

        os_sys = platform.system().lower()
        detected = {"darwin": "mac", "windows": "windows"}.get(os_sys, "linux")
        self._sel_os = detected

        cur_cfg = _read_full_config()
        self._provider = cur_cfg.get("llm_provider", "gemini").lower()
        if self._provider not in ("gemini", "ollama", "openai", "openrouter"):
            self._provider = "gemini"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(7)

        def _lbl(txt, font_size=9, bold=False, color=C.PRI,
                 align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt)
            w.setAlignment(align)
            w.setFont(tech_font(font_size,
                                QFont.Weight.Bold if bold else QFont.Weight.Medium,
                                50 if bold else 20))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        # Common input field styling
        _inp_style = f"""
            QLineEdit {{
                background: {C.PANEL2}; color: {C.TEXT_BRIGHT};
                border: 1px solid {C.BORDER_A}; border-radius: 2px; padding: 4px 8px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
        """

        # Header with Title, External APIs Button, and Close Button
        hdr_row = QHBoxLayout()
        hdr_box = QVBoxLayout(); hdr_box.setSpacing(2)
        hdr_box.addWidget(_lbl("◈  SYSTEM INITIALISATION // OPERATOR & NEURAL CONFIG", 11, True, align=Qt.AlignmentFlag.AlignLeft))
        hdr_box.addWidget(_lbl("Configure operator designation, neural interface backend, and credentials.", 8, color=C.PRI_DIM, align=Qt.AlignmentFlag.AlignLeft))
        hdr_row.addLayout(hdr_box)
        hdr_row.addStretch()

        api_btn = QPushButton("◈  SETUP SPOTIFY, GMAIL & WORKSPACE")
        api_btn.setFixedHeight(26)
        api_btn.setFont(mono_font(7, QFont.Weight.Bold, letter_spacing=0.5))
        api_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        api_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL2}; color: {C.PRI};
                border: 1px solid {C.PRI}; border-radius: 2px; padding: 0 10px;
            }}
            QPushButton:hover {{ background: {C.PRI}; color: {C.DARK}; }}
        """)
        api_btn.clicked.connect(lambda: self.setup_api_requested.emit())
        attach_hover_help(api_btn, "Configure encrypted credentials and OAuth tokens for Spotify, Gmail, and Google Workspace.")
        hdr_row.addWidget(api_btn)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(26, 26)
        close_btn.setFont(tech_font(9, QFont.Weight.Bold))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255, 255, 255, 0.05);
                color: {C.TEXT_MED};
                border: 1px solid {C.BORDER_A};
                border-radius: 13px;
            }}
            QPushButton:hover {{
                background: rgba(255, 42, 85, 0.25);
                color: #ffffff;
                border-color: {C.RED};
            }}
        """)
        close_btn.clicked.connect(self.hide)
        hdr_row.addWidget(close_btn)
        layout.addLayout(hdr_row)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER_A}; margin: 2px 0;"); layout.addWidget(sep)
        layout.addSpacing(2)

        # ── Operator Designation & Identity ─────────────────────────────
        ident_row = QHBoxLayout(); ident_row.setSpacing(8)
        user_box = QVBoxLayout(); user_box.setSpacing(2)
        user_box.addWidget(_lbl("OPERATOR CALLSIGN / USER DESIGNATION", 7, bold=True, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        self._user_input = QLineEdit(cur_cfg.get("user_name", ""))
        self._user_input.setPlaceholderText("e.g. Master Wayne, Sir, or your name")
        self._user_input.setFont(mono_font(8))
        self._user_input.setFixedHeight(26)
        self._user_input.setStyleSheet(_inp_style)
        user_box.addWidget(self._user_input)
        ident_row.addLayout(user_box, stretch=3)

        asst_box = QVBoxLayout(); asst_box.setSpacing(2)
        asst_box.addWidget(_lbl("ASSISTANT CALLSIGN", 7, bold=True, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        self._asst_input = QLineEdit(cur_cfg.get("assistant_name", "Alfred") or "Alfred")
        self._asst_input.setFont(mono_font(8))
        self._asst_input.setFixedHeight(26)
        self._asst_input.setStyleSheet(_inp_style)
        asst_box.addWidget(self._asst_input)
        ident_row.addLayout(asst_box, stretch=2)
        layout.addLayout(ident_row)
        layout.addSpacing(2)

        # ── Backend Mode Selector ───────────────────────────────────────
        layout.addWidget(_lbl("INTELLIGENCE BACKEND // MULTI-ROUTE ARCHITECTURE", 8, bold=True, color=C.TEXT_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))
        mode_row = QHBoxLayout(); mode_row.setSpacing(6)
        self._mode_btns: dict[str, QPushButton] = {}
        for m_key, m_label in [
            ("gemini", "◈  GEMINI LIVE"),
            ("ollama", "🦙  LOCAL OLLAMA"),
            ("openai", "⚡  LM STUDIO"),
            ("openrouter", "🌐  OPENROUTER API"),
        ]:
            b = QPushButton(m_label)
            b.setFont(tech_font(8, QFont.Weight.Bold, 30))
            b.setFixedHeight(28)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _, k=m_key: self._set_backend(k))
            self._mode_btns[m_key] = b
            mode_row.addWidget(b)
        layout.addLayout(mode_row)
        layout.addSpacing(2)

        # ── Provider Stack ──────────────────────────────────────────────
        self._provider_stack = QStackedWidget()

        # 1. Gemini Stack Page
        gemini_w = QWidget(); gemini_lay = QVBoxLayout(gemini_w)
        gemini_lay.setContentsMargins(0, 0, 0, 0); gemini_lay.setSpacing(4)
        gemini_lay.addWidget(_lbl("GEMINI API DIRECTIVE KEY", 8, bold=True, color=C.TEXT_DIM,
                                  align=Qt.AlignmentFlag.AlignLeft))
        existing_key = (cur_cfg.get("gemini_api_key") or cur_cfg.get("GEMINI_API_KEY")
                        or cur_cfg.get("api_key") or os.environ.get("GEMINI_API_KEY", ""))
        self._key_input = QLineEdit(existing_key)
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText("AIzaSy... (key from Google AI Studio)")
        self._key_input.setFont(mono_font(9))
        self._key_input.setFixedHeight(30)
        self._key_input.setStyleSheet(_inp_style)
        gemini_lay.addWidget(self._key_input)
        gemini_hint = QLabel("⚡ Cloud Multimodal WebSocket — Zero local compute/Ollama required. Recommended for macOS & all platforms.")
        gemini_hint.setFont(tech_font(7))
        gemini_hint.setStyleSheet(f"color: {C.TEXT_MUTED}; background: transparent;")
        gemini_lay.addWidget(gemini_hint)
        gemini_lay.addStretch()
        self._provider_stack.addWidget(gemini_w)

        # 2. Ollama Stack Page
        ollama_w = QWidget(); ollama_lay = QVBoxLayout(ollama_w)
        ollama_lay.setContentsMargins(0, 0, 0, 0); ollama_lay.setSpacing(4)
        
        ollama_url_row = QHBoxLayout(); ollama_url_row.setSpacing(6)
        ollama_url_box = QVBoxLayout(); ollama_url_box.setSpacing(2)
        ollama_url_box.addWidget(_lbl("OLLAMA HOST URL", 7, bold=True, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        self._ollama_url = QLineEdit(cur_cfg.get("llm_url", "http://localhost:11434"))
        self._ollama_url.setFont(mono_font(9))
        self._ollama_url.setFixedHeight(28)
        self._ollama_url.setStyleSheet(_inp_style)
        ollama_url_box.addWidget(self._ollama_url)
        ollama_url_row.addLayout(ollama_url_box, stretch=2)

        ollama_model_box = QVBoxLayout(); ollama_model_box.setSpacing(2)
        ollama_model_box.addWidget(_lbl("MODEL TAG", 7, bold=True, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        self._ollama_model = QLineEdit(cur_cfg.get("llm_model", "llama3.2"))
        self._ollama_model.setFont(mono_font(9))
        self._ollama_model.setFixedHeight(28)
        self._ollama_model.setStyleSheet(_inp_style)
        ollama_model_box.addWidget(self._ollama_model)
        ollama_url_row.addLayout(ollama_model_box, stretch=2)
        ollama_lay.addLayout(ollama_url_row)

        chip_row = QHBoxLayout(); chip_row.setSpacing(4)
        for chip_name in ["llama3.2", "qwen2.5:7b", "deepseek-coder-v2"]:
            cb = QPushButton(chip_name)
            cb.setFixedHeight(20)
            cb.setFont(mono_font(7, letter_spacing=0.2))
            cb.setCursor(Qt.CursorShape.PointingHandCursor)
            cb.setStyleSheet(f"""
                QPushButton {{
                    background: {C.PANEL2}; color: {C.TEXT_MED};
                    border: 1px solid {C.BORDER_A}; border-radius: 2px; padding: 0 6px;
                }}
                QPushButton:hover {{ border-color: {C.PRI}; color: #ffffff; background: rgba(142, 155, 255, 0.10); }}
            """)
            cb.clicked.connect(lambda _, m=chip_name: self._ollama_model.setText(m))
            chip_row.addWidget(cb)
        chip_row.addStretch()
        ollama_lay.addLayout(chip_row)

        probe_row = QHBoxLayout(); probe_row.setSpacing(8)
        self._probe_btn = QPushButton("◈  PROBE STATUS")
        self._probe_btn.setFixedHeight(24)
        self._probe_btn.setFont(tech_font(7, QFont.Weight.Bold))
        self._probe_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._probe_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL2}; color: {C.PRI};
                border: 1px solid {C.PRI}; border-radius: 2px; padding: 0 8px;
            }}
            QPushButton:hover {{ background: {C.PRI}; color: {C.DARK}; }}
        """)
        self._probe_btn.clicked.connect(self._probe_ollama)
        probe_row.addWidget(self._probe_btn)

        self._probe_status = QLabel("100% offline, zero network egress")
        self._probe_status.setFont(tech_font(7))
        self._probe_status.setStyleSheet(f"color: {C.GREEN}; background: transparent;")
        probe_row.addWidget(self._probe_status, stretch=1)
        ollama_lay.addLayout(probe_row)
        ollama_lay.addStretch()
        self._provider_stack.addWidget(ollama_w)

        # 3. LM Studio Stack Page
        lm_w = QWidget(); lm_lay = QVBoxLayout(lm_w)
        lm_lay.setContentsMargins(0, 0, 0, 0); lm_lay.setSpacing(4)
        lm_url_row = QHBoxLayout(); lm_url_row.setSpacing(6)
        lm_url_box = QVBoxLayout(); lm_url_box.setSpacing(2)
        lm_url_box.addWidget(_lbl("SERVER ENDPOINT", 7, bold=True, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        self._lm_url = QLineEdit(cur_cfg.get("llm_url", "http://localhost:1234/v1"))
        self._lm_url.setFont(mono_font(9))
        self._lm_url.setFixedHeight(28)
        self._lm_url.setStyleSheet(_inp_style)
        lm_url_box.addWidget(self._lm_url)
        lm_url_row.addLayout(lm_url_box, stretch=2)

        lm_model_box = QVBoxLayout(); lm_model_box.setSpacing(2)
        lm_model_box.addWidget(_lbl("MODEL IDENTIFIER", 7, bold=True, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        self._lm_model = QLineEdit(cur_cfg.get("llm_model", "local-model"))
        self._lm_model.setFont(mono_font(9))
        self._lm_model.setFixedHeight(28)
        self._lm_model.setStyleSheet(_inp_style)
        lm_model_box.addWidget(self._lm_model)
        lm_url_row.addLayout(lm_model_box, stretch=2)
        lm_lay.addLayout(lm_url_row)
        lm_hint = QLabel("Compatible with LM Studio, Jan, LocalAI, vLLM, and llama.cpp server.")
        lm_hint.setFont(tech_font(7))
        lm_hint.setStyleSheet(f"color: {C.TEXT_MUTED}; background: transparent;")
        lm_lay.addWidget(lm_hint)
        lm_lay.addStretch()
        self._provider_stack.addWidget(lm_w)

        # 4. OpenRouter Stack Page
        or_w = QWidget(); or_lay = QVBoxLayout(or_w)
        or_lay.setContentsMargins(0, 0, 0, 0); or_lay.setSpacing(4)

        or_key_box = QVBoxLayout(); or_key_box.setSpacing(2)
        or_key_box.addWidget(_lbl("OPENROUTER DIRECTIVE API KEY", 7, bold=True, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        existing_or_key = (cur_cfg.get("openrouter_api_key") or cur_cfg.get("OPENROUTER_API_KEY")
                           or os.environ.get("OPENROUTER_API_KEY", ""))
        self._or_key_input = QLineEdit(existing_or_key)
        self._or_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._or_key_input.setPlaceholderText("sk-or-v1-... (from openrouter.ai/keys)")
        self._or_key_input.setFont(mono_font(9))
        self._or_key_input.setFixedHeight(28)
        self._or_key_input.setStyleSheet(_inp_style)
        or_key_box.addWidget(self._or_key_input)
        or_lay.addLayout(or_key_box)

        or_model_box = QVBoxLayout(); or_model_box.setSpacing(2)
        or_model_box.addWidget(_lbl("TARGET NEURAL MODEL IDENTIFIER", 7, bold=True, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        default_or_model = cur_cfg.get("openrouter_model") or cur_cfg.get("llm_model") or "anthropic/claude-3.5-sonnet"
        self._or_model = QLineEdit(default_or_model)
        self._or_model.setFont(mono_font(9))
        self._or_model.setFixedHeight(28)
        self._or_model.setStyleSheet(_inp_style)
        or_model_box.addWidget(self._or_model)
        or_lay.addLayout(or_model_box)

        # Quick-pick model chips
        or_chip_row = QHBoxLayout(); or_chip_row.setSpacing(4)
        for chip_label, model_id in [
            ("claude-3.5-sonnet", "anthropic/claude-3.5-sonnet"),
            ("gemini-2.0-flash", "google/gemini-2.0-flash-001"),
            ("llama-3.3-70b", "meta-llama/llama-3.3-70b-instruct"),
            ("deepseek-r1", "deepseek/deepseek-r1"),
            ("gpt-4o", "openai/gpt-4o"),
            ("auto", "openrouter/auto"),
        ]:
            cb = QPushButton(chip_label)
            cb.setFixedHeight(20)
            cb.setFont(mono_font(7, letter_spacing=0.2))
            cb.setCursor(Qt.CursorShape.PointingHandCursor)
            cb.setStyleSheet(f"""
                QPushButton {{
                    background: {C.PANEL2}; color: {C.TEXT_MED};
                    border: 1px solid {C.BORDER_A}; border-radius: 2px; padding: 0 5px;
                }}
                QPushButton:hover {{ border-color: {C.PRI}; color: #ffffff; background: rgba(142, 155, 255, 0.10); }}
            """)
            cb.clicked.connect(lambda _, m=model_id: self._or_model.setText(m))
            or_chip_row.addWidget(cb)
        or_chip_row.addStretch()
        or_lay.addLayout(or_chip_row)

        or_probe_row = QHBoxLayout(); or_probe_row.setSpacing(8)
        self._or_probe_btn = QPushButton("◈  PROBE ROUTE")
        self._or_probe_btn.setFixedHeight(24)
        self._or_probe_btn.setFont(tech_font(7, QFont.Weight.Bold))
        self._or_probe_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._or_probe_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL2}; color: {C.PRI};
                border: 1px solid {C.PRI}; border-radius: 2px; padding: 0 8px;
            }}
            QPushButton:hover {{ background: {C.PRI}; color: {C.DARK}; }}
        """)
        self._or_probe_btn.clicked.connect(self._probe_openrouter)
        or_probe_row.addWidget(self._or_probe_btn)

        self._or_probe_status = QLabel("Unified gateway to 200+ frontier models")
        self._or_probe_status.setFont(tech_font(7))
        self._or_probe_status.setStyleSheet(f"color: {C.TEXT_MUTED}; background: transparent;")
        or_probe_row.addWidget(self._or_probe_status, stretch=1)
        or_lay.addLayout(or_probe_row)
        or_lay.addStretch()
        self._provider_stack.addWidget(or_w)

        layout.addWidget(self._provider_stack)
        layout.addSpacing(2)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C.BORDER_A}; margin: 2px 0;"); layout.addWidget(sep2)
        layout.addSpacing(2)

        layout.addWidget(_lbl("TARGET OPERATING SYSTEM", 8, bold=True, color=C.TEXT_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))
        det_name = {"windows": "Windows", "mac": "macOS", "linux": "Linux"}[detected]
        layout.addWidget(_lbl(f"Auto-detected Environment: {det_name}", 7, color=C.ACC2,
                               align=Qt.AlignmentFlag.AlignLeft))

        os_row = QHBoxLayout(); os_row.setSpacing(6)
        self._os_btns: dict[str, QPushButton] = {}
        for key, label in [("windows","⊞  Windows"),("mac","◈  macOS"),("linux","🐧  Linux")]:
            btn = QPushButton(label)
            btn.setFont(tech_font(8, QFont.Weight.Bold, 30))
            btn.setFixedHeight(28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._sel_os_btn(k))
            os_row.addWidget(btn)
            self._os_btns[key] = btn
        layout.addLayout(os_row)
        self._sel_os_btn(detected)
        self._set_backend(self._provider)
        layout.addSpacing(4)

        # Validation error banner
        self._err_lbl = QLabel("")
        self._err_lbl.setFont(tech_font(7, QFont.Weight.Bold))
        self._err_lbl.setStyleSheet(f"color: {C.RED}; background: transparent;")
        self._err_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._err_lbl.hide()
        layout.addWidget(self._err_lbl)

        # Bottom action bar (Initialise Systems + Discard)
        btn_row = QHBoxLayout(); btn_row.setSpacing(10)

        init_btn = QPushButton("▸  INITIALISE SYSTEMS")
        init_btn.setFont(mono_font(8, QFont.Weight.Bold, letter_spacing=1.2))
        init_btn.setFixedHeight(36)
        init_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        init_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PRI};
                color: {C.DARK};
                border: 1px solid {C.PRI};
                border-radius: 2px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {C.TEXT_BRIGHT};
                color: #000000;
                border-color: #ffffff;
            }}
            QPushButton:pressed {{
                background: {C.PRI_DIM};
                color: {C.DARK};
            }}
        """)
        init_btn.clicked.connect(self._submit)
        btn_row.addWidget(init_btn, stretch=2)

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
            QPushButton:hover {{
                color: #ffffff;
                border-color: {C.PRI};
                background: rgba(142, 155, 255, 0.10);
            }}
            QPushButton:pressed {{
                background: rgba(142, 155, 255, 0.20);
            }}
        """)
        cancel_btn.clicked.connect(self.hide)
        btn_row.addWidget(cancel_btn, stretch=1)

        layout.addLayout(btn_row)

    def _set_backend(self, key: str):
        self._provider = key
        idx_map = {"gemini": 0, "ollama": 1, "openai": 2, "openrouter": 3}
        self._provider_stack.setCurrentIndex(idx_map.get(key, 0))
        for k, btn in self._mode_btns.items():
            if k == key:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {C.PRI}; color: {C.DARK};
                        border: 1px solid {C.PRI}; border-radius: 2px; font-weight: bold;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {C.PANEL2}; color: {C.TEXT_MED};
                        border: 1px solid {C.BORDER_A}; border-radius: 2px;
                    }}
                    QPushButton:hover {{ color: {C.TEXT_BRIGHT}; border-color: {C.PRI}; background: rgba(142, 155, 255, 0.10); }}
                """)

    def _sel_os_btn(self, key: str):
        self._sel_os = key
        for k, btn in self._os_btns.items():
            if k == key:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {C.PRI}; color: {C.DARK};
                        border: 1px solid {C.PRI}; border-radius: 2px; font-weight: bold;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {C.PANEL2}; color: {C.TEXT_MED};
                        border: 1px solid {C.BORDER_A}; border-radius: 2px;
                    }}
                    QPushButton:hover {{ color: {C.TEXT_BRIGHT}; border-color: {C.PRI}; background: rgba(142, 155, 255, 0.10); }}
                """)

    def _probe_ollama(self):
        self._probe_status.setText("Probing Ollama...")
        self._probe_status.setStyleSheet(f"color: {C.ACC2}; background: transparent;")
        url = self._ollama_url.text().strip() or "http://localhost:11434"

        def _check():
            import urllib.request
            try:
                req = urllib.request.Request(f"{url.rstrip('/')}/api/tags", headers={"User-Agent": "ALFRED"})
                with urllib.request.urlopen(req, timeout=2.0) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        models = [m.get("name", "") for m in data.get("models", [])]
                        return True, models
            except Exception:
                pass
            return False, []

        def _worker():
            ok, models = _check()
            self._probe_done.emit("ollama", ok, models)

        threading.Thread(target=_worker, daemon=True).start()

    def _probe_openrouter(self):
        key = self._or_key_input.text().strip()
        if not key:
            self._or_probe_status.setText("▲ ENTER API KEY FIRST")
            self._or_probe_status.setStyleSheet(f"color: {C.RED}; background: transparent;")
            return
        self._or_probe_status.setText("Probing OpenRouter gateway...")
        self._or_probe_status.setStyleSheet(f"color: {C.ACC2}; background: transparent;")

        def _check():
            import urllib.request
            try:
                req = urllib.request.Request(
                    "https://openrouter.ai/api/v1/auth/key",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "User-Agent": "ALFRED-Mark-IX",
                    }
                )
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8")).get("data", {})
                        usage = data.get("usage")
                        if usage is not None:
                            return True, f"● ONLINE // Key Valid (Usage: ${usage:.2f})"
                        return True, "● ONLINE // Gateway Verified"
            except Exception as e:
                err_msg = str(e)
                if "401" in err_msg or "403" in err_msg:
                    return False, "▲ INVALID API KEY (401 Unauthorized)"
                return False, f"▲ CONNECTION FAILED ({type(e).__name__})"
            return False, "▲ PROBE FAILED"

        def _worker():
            ok, message = _check()
            self._probe_done.emit("openrouter", ok, message)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_probe_done(self, backend: str, ok: bool, payload) -> None:
        """Update probe widgets on the Qt thread via a queued signal."""
        if backend == "ollama":
            models = list(payload or [])
            if ok:
                found = ", ".join(models[:3]) if models else "server reachable"
                self._probe_status.setText(f"● ONLINE // Models: {found}")
                self._probe_status.setStyleSheet(f"color: {C.GREEN}; background: transparent;")
            else:
                hint = "Run 'ollama serve' in terminal"
                if self._sel_os == "mac":
                    hint = "Run 'brew install ollama && ollama serve' (CLI works on macOS 11+)"
                self._probe_status.setText(f"▲ OFFLINE — {hint}")
                self._probe_status.setStyleSheet(f"color: {C.RED}; background: transparent;")
            return

        self._or_probe_status.setText(str(payload))
        self._or_probe_status.setStyleSheet(
            f"color: {C.GREEN if ok else C.RED}; background: transparent;"
        )

    def _submit(self):
        self._err_lbl.hide()
        prov = self._provider
        os_name = self._sel_os
        u_name = self._user_input.text().strip()
        a_name = self._asst_input.text().strip() or "Alfred"

        if prov == "gemini":
            key = self._key_input.text().strip()
            if not key:
                self._key_input.setStyleSheet(
                    self._key_input.styleSheet() +
                    f" QLineEdit {{ border: 1px solid {C.RED}; }}"
                )
                self._err_lbl.setText("GEMINI KEY REQUIRED FOR CLOUD. OR SELECT OPENROUTER / LOCAL.")
                self._err_lbl.show()
                return
            config_dict = {
                "llm_provider": "gemini",
                "gemini_api_key": key,
                "os_system": os_name,
                "user_name": u_name,
                "assistant_name": a_name,
            }
        elif prov == "ollama":
            url = self._ollama_url.text().strip() or "http://localhost:11434"
            model = self._ollama_model.text().strip() or "llama3.2"
            key = self._key_input.text().strip()
            config_dict = {
                "llm_provider": "ollama",
                "llm_url": url,
                "llm_model": model,
                "gemini_api_key": key,
                "os_system": os_name,
                "user_name": u_name,
                "assistant_name": a_name,
            }
        elif prov == "openrouter":
            or_key = self._or_key_input.text().strip()
            or_model = self._or_model.text().strip() or "anthropic/claude-3.5-sonnet"
            if not or_key:
                self._or_key_input.setStyleSheet(
                    self._or_key_input.styleSheet() +
                    f" QLineEdit {{ border: 1px solid {C.RED}; }}"
                )
                self._err_lbl.setText("OPENROUTER API KEY REQUIRED FOR ROUTING.")
                self._err_lbl.show()
                return
            config_dict = {
                "llm_provider": "openrouter",
                "openrouter_api_key": or_key,
                "openrouter_model": or_model,
                "llm_model": or_model,
                "os_system": os_name,
                "user_name": u_name,
                "assistant_name": a_name,
            }
        else:  # openai / lmstudio
            url = self._lm_url.text().strip() or "http://localhost:1234/v1"
            model = self._lm_model.text().strip() or "local-model"
            key = self._key_input.text().strip()
            config_dict = {
                "llm_provider": "openai",
                "llm_url": url,
                "llm_model": model,
                "gemini_api_key": key,
                "os_system": os_name,
                "user_name": u_name,
                "assistant_name": a_name,
            }

        self.done.emit(config_dict)

    def refresh_values(self):
        """Reload configuration from disk into input fields."""
        cur_cfg = _read_full_config()
        self._provider = cur_cfg.get("llm_provider", "gemini").lower()
        if self._provider not in ("gemini", "ollama", "openai", "openrouter"):
            self._provider = "gemini"
        self._set_backend(self._provider)

        self._user_input.setText(cur_cfg.get("user_name", ""))
        self._asst_input.setText(cur_cfg.get("assistant_name", "Alfred") or "Alfred")

        existing_key = (cur_cfg.get("gemini_api_key") or cur_cfg.get("GEMINI_API_KEY")
                        or cur_cfg.get("api_key") or os.environ.get("GEMINI_API_KEY", ""))
        self._key_input.setText(existing_key)

        self._ollama_url.setText(cur_cfg.get("llm_url", "http://localhost:11434"))
        self._ollama_model.setText(cur_cfg.get("llm_model", "llama3.2"))

        self._lm_url.setText(cur_cfg.get("llm_url", "http://localhost:1234/v1"))
        self._lm_model.setText(cur_cfg.get("llm_model", "local-model"))

        self._or_key_input.setText(cur_cfg.get("openrouter_api_key", ""))
        self._or_model.setText(cur_cfg.get("openrouter_model", "anthropic/claude-3.5-sonnet"))

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_values()

