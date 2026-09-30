"""
ui/overlays/plugin_settings_overlay.py — Extension configuration matrix overlay.
"""
from __future__ import annotations

import threading
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
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
    tech_font,
    mono_font,
)


class PluginSettingsOverlay(QWidget):
    """Floating overlay — renders per-plugin settings forms.

    Fully generic: it iterates the settings schemas a plugin declared via its
    PLUGIN_SETTINGS constant (delivered by PluginRegistry.settings_schemas) and
    builds a form for each.
    """

    _test_done = pyqtSignal(str, bool, str)   # namespace, ok, message
    setup_api_requested = pyqtSignal()
    _OW = 460

    def __init__(self, sections: list[dict], parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            PluginSettingsOverlay {{
                background: {C.PANEL_BG};
                border: 1px solid {C.BORDER_A};
                border-radius: 10px;
            }}
        """)
        self._sections = sections or []
        self._widgets: dict[tuple, object] = {}    # (namespace, key) -> input widget
        self._types:   dict[tuple, str]    = {}     # (namespace, key) -> field type
        self._status_labels: dict[str, QLabel] = {} # namespace -> status QLabel
        self._test_done.connect(self._on_test_done)

        self._fs = (f"QLineEdit {{ background: rgba(3, 14, 25, 0.85); color: {C.TEXT}; "
                    f"border: 1px solid {C.BORDER_B}; border-radius: 4px; padding: 4px 8px; }}"
                    f"QLineEdit:focus {{ border: 1px solid {C.PRI}; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(8)

        root.addWidget(self._lbl("⚙  EXTENSION CONFIGURATION MATRIX", 12, True))
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        root.addWidget(sep)

        if not self._sections:
            root.addWidget(self._lbl(
                "No configurable plugins are installed.\nDrop a plugin that needs "
                "settings into the plugins folder and it will appear here.", 9, color=C.TEXT_DIM))
        else:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setStyleSheet("QScrollArea { background: transparent; }")
            inner = QWidget()
            inner.setStyleSheet("background: transparent;")
            form = QVBoxLayout(inner)
            form.setContentsMargins(0, 0, 6, 0)
            form.setSpacing(6)
            for sec in self._sections:
                self._build_section(form, sec)
            form.addStretch(1)
            scroll.setWidget(inner)
            root.addWidget(scroll, 1)

        # ── bottom buttons ───────────────────────────────────────────────────
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        if self._sections:
            save_btn = QPushButton("▸  SAVE CHANGES")
            save_btn.setFixedHeight(34)
            save_btn.setFont(tech_font(9, QFont.Weight.Bold, 50))
            save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            save_btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(0,240,255,0.15), stop:1 rgba(0,180,255,0.06));
                    color: {C.PRI};
                    border: 1px solid {C.PRI}; border-radius: 5px;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(0,240,255,0.28), stop:1 rgba(0,200,255,0.12));
                    color: {C.TEXT_BRIGHT}; border-color: {C.TEXT_BRIGHT};
                }}
            """)
            save_btn.clicked.connect(self._save_all)
            btn_row.addWidget(save_btn)

        api_btn = QPushButton("◈  SETUP API")
        api_btn.setFixedHeight(34)
        api_btn.setFont(mono_font(8, QFont.Weight.Bold, letter_spacing=0.5))
        api_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        api_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL2}; color: {C.PRI};
                border: 1px solid {C.PRI}; border-radius: 4px; padding: 0 10px;
            }}
            QPushButton:hover {{ background: {C.PRI}; color: {C.DARK}; }}
        """)
        api_btn.clicked.connect(lambda: self.setup_api_requested.emit())
        btn_row.addWidget(api_btn)

        close_btn = QPushButton("CLOSE")
        close_btn.setFixedHeight(34)
        close_btn.setFont(tech_font(9))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 5px; }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        close_btn.clicked.connect(self.hide)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

    # ── helpers ───────────────────────────────────────────────────────────────
    def _lbl(self, txt, fs=9, bold=False, color=C.PRI,
             align=Qt.AlignmentFlag.AlignLeft):
        w = QLabel(txt); w.setAlignment(align); w.setWordWrap(True)
        w.setFont(tech_font(fs,
                            QFont.Weight.Bold if bold else QFont.Weight.Normal,
                            50 if bold else 20))
        w.setStyleSheet(f"color: {color}; background: transparent;")
        return w

    def _build_section(self, form: QVBoxLayout, sec: dict):
        ns     = sec.get("namespace") or sec.get("plugin") or "plugin"
        title  = sec.get("title") or ns
        fields = sec.get("fields") or []
        values = sec.get("values") or {}

        form.addSpacing(4)
        form.addWidget(self._lbl(title, 10, True, C.PRI))

        for field in fields:
            if not isinstance(field, dict) or not field.get("key"):
                continue
            key   = field["key"]
            ftype = (field.get("type") or "text").lower()
            label = field.get("label") or key
            default = field.get("default")
            stored  = values.get(key, default)

            form.addWidget(self._lbl(label.upper(), 8, color=C.TEXT_DIM))

            if ftype == "choice":
                w = QComboBox()
                w.addItems([str(o) for o in field.get("options", [])])
                w.setFont(tech_font(9))
                w.setFixedHeight(30)
                w.setStyleSheet(
                    f"QComboBox {{ background: rgba(3, 14, 25, 0.85); color: {C.TEXT}; "
                    f"border: 1px solid {C.BORDER_B}; border-radius: 4px; padding: 2px 8px; }}"
                    f"QComboBox QAbstractItemView {{ background: #030e19; color: {C.TEXT}; "
                    f"selection-background-color: {C.PRI_GHO}; }}")
                if stored is not None:
                    w.setCurrentText(str(stored))
            elif ftype == "toggle":
                w = QPushButton()
                w.setCheckable(True)
                w.setChecked(bool(stored))
                w.setFixedHeight(28)
                w.setFont(tech_font(8, QFont.Weight.Bold, 30))
                w.setCursor(Qt.CursorShape.PointingHandCursor)
                self._style_toggle(w)
                w.toggled.connect(lambda _=False, b=w: self._style_toggle(b))
            else:  # text / password
                w = QLineEdit("" if stored is None else str(stored))
                w.setFont(mono_font(10))
                w.setFixedHeight(30)
                w.setStyleSheet(self._fs)
                if field.get("placeholder"):
                    w.setPlaceholderText(str(field["placeholder"]))
                if ftype == "password":
                    w.setEchoMode(QLineEdit.EchoMode.Password)

            self._widgets[(ns, key)] = w
            self._types[(ns, key)]   = ftype
            form.addWidget(w)

        # optional test/connect action button + status line
        action = sec.get("action")
        if isinstance(action, dict) and callable(action.get("run")):
            form.addSpacing(2)
            ab = QPushButton(str(action.get("label") or "TEST"))
            ab.setFixedHeight(30)
            ab.setFont(tech_font(8, QFont.Weight.Bold, 40))
            ab.setCursor(Qt.CursorShape.PointingHandCursor)
            ab.setStyleSheet(f"""
                QPushButton {{ background: rgba(0, 240, 255, 0.08); color: {C.PRI};
                    border: 1px solid {C.PRI_DIM}; border-radius: 4px; }}
                QPushButton:hover {{ background: {C.PRI_GHO}; border-color: {C.PRI}; }}
            """)
            ab.clicked.connect(lambda _=False, n=ns: self._run_action(n))
            form.addWidget(ab)

        status = self._lbl("", 8, color=C.TEXT_DIM)
        self._status_labels[ns] = status
        form.addWidget(status)

        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color: {C.BORDER}; margin: 4px 0;")
        form.addWidget(line)

    def _style_toggle(self, btn: QPushButton):
        on = btn.isChecked()
        btn.setText("ACTIVE" if on else "OFF")
        if on:
            btn.setStyleSheet(f"QPushButton {{ background: {C.PRI_GHO}; color: {C.PRI}; "
                              f"border: 1px solid {C.PRI}; border-radius: 3px; }}")
        else:
            btn.setStyleSheet(f"QPushButton {{ background: transparent; color: {C.TEXT_MED}; "
                              f"border: 1px solid {C.BORDER}; border-radius: 3px; }}")

    # ── data ──────────────────────────────────────────────────────────────────
    def _gather(self, ns: str) -> dict:
        out = {}
        for (n, key), w in self._widgets.items():
            if n != ns:
                continue
            t = self._types.get((n, key), "text")
            if t == "choice":
                out[key] = w.currentText()
            elif t == "toggle":
                out[key] = w.isChecked()
            else:
                out[key] = w.text().strip()
        return out

    def _save_ns(self, ns: str):
        from memory.config_manager import save_plugin_config
        save_plugin_config(ns, self._gather(ns))

    def _save_all(self):
        for sec in self._sections:
            ns = sec.get("namespace") or sec.get("plugin")
            if ns:
                self._save_ns(ns)
                lbl = self._status_labels.get(ns)
                if lbl:
                    lbl.setText("Saved ✓")
                    lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")

    def _run_action(self, ns: str):
        sec = next((s for s in self._sections
                    if (s.get("namespace") or s.get("plugin")) == ns), None)
        if not sec:
            return
        run_fn = (sec.get("action") or {}).get("run")
        if not callable(run_fn):
            return
        self._save_ns(ns)                 # persist what the user typed before testing
        values = self._gather(ns)
        lbl = self._status_labels.get(ns)
        if lbl:
            lbl.setText("Testing…")
            lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")

        def worker():
            try:
                res = run_fn(values)
                if isinstance(res, tuple) and len(res) == 2:
                    ok, msg = bool(res[0]), str(res[1])
                else:
                    ok, msg = bool(res), str(res)
            except Exception as e:
                ok, msg = False, str(e)
            self._test_done.emit(ns, ok, msg)

        threading.Thread(target=worker, daemon=True).start()

    def _on_test_done(self, ns: str, ok: bool, msg: str):
        lbl = self._status_labels.get(ns)
        if not lbl:
            return
        lbl.setText(msg)
        color = C.PRI if ok else "#ff6b6b"
        lbl.setStyleSheet(f"color: {color}; background: transparent;")
