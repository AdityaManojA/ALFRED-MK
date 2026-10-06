"""
core/ui/voice_enroll_modal.py — Tactical Voice Biometric Profile Enrollment Modal.

Features:
- Batcomputer HUD glassmorphic modal styled to match Alfred's tactical design language.
- Interactive 3-step enrollment: "Say 'Hey Alfred' (Sample 1/3, 2/3, 3/3)".
- Real-time acoustic quality verification (RMS level, clipping, speech duration, consistency).
- Non-blocking background recording and embedding extraction via CampplusOnnxExtractor.
- Automatic profile centroid aggregation, threshold calibration, and atomic persistence.
- Complete ThemeChrome integration adapting dynamically to active Batcomputer CRT palettes.
"""
from __future__ import annotations

import logging
import threading
from typing import Optional, Callable
import numpy as np

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QFont
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QFrame,
)

from core.speaker.types import SpeakerProfile
from core.speaker.profile_store import LocalProfileStore, get_default_profile_store
from core.speaker.extractor import SpeakerEmbeddingExtractor, CampplusOnnxExtractor
from core.speaker.enrollment import SpeakerEnrollmentManager
from core.ui.themes import ThemeChrome

_LOGGER = logging.getLogger("core.ui.voice_enroll")

SAMPLE_RATE = 16000
RECORD_DURATION_S = 2.0

_TECH_FONT_FAMILIES = (
    "JetBrains Mono", "Fira Code", "Consolas", "Courier New",
    "Cascadia Code", "SF Mono", "monospace"
)


def _tech_font(
    size: int | float,
    weight: QFont.Weight = QFont.Weight.Normal,
    letter_spacing: float | None = None,
) -> QFont:
    """Create a monospaced terminal font matching ALFRED's HUD design system."""
    f = QFont()
    f.setFamilies(list(_TECH_FONT_FAMILIES))
    if isinstance(size, float):
        f.setPointSizeF(size)
    else:
        f.setPointSize(int(size))
    f.setWeight(weight)
    f.setStyleHint(QFont.StyleHint.Monospace)
    if letter_spacing is not None:
        spacing = letter_spacing / 50.0 if letter_spacing > 5.0 else letter_spacing
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return f


class VoiceEnrollModal(QDialog):
    profile_enrolled = pyqtSignal(str)   # user_name
    profile_deleted = pyqtSignal()
    recording_finished = pyqtSignal(object, int)  # audio_np, sample_rate

    def __init__(
        self,
        parent=None,
        profile_store: Optional[LocalProfileStore] = None,
        extractor: Optional[SpeakerEmbeddingExtractor] = None,
        default_user: str = "Operator",
    ):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._store = profile_store or get_default_profile_store()
        self._extractor = extractor or CampplusOnnxExtractor()
        self._enrollment_mgr = SpeakerEnrollmentManager(
            extractor=self._extractor,
            profile_store=self._store,
            target_samples=3,
        )

        self._user_name = default_user or "Operator"
        self._current_step = 1
        self._target_steps = 3
        self._is_recording = False
        self._last_status_type = "ready"

        self._setup_ui()
        ThemeChrome.add_listener(self._on_theme_changed)
        self.recording_finished.connect(self._on_recording_finished)
        self._check_existing_profile()

    def _setup_ui(self):
        self.setFixedSize(620, 510)
        pal = ThemeChrome.get_active().palette

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {pal.panel};
                border: 1px solid {pal.border_b};
                border-radius: 8px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # ── Header Row ────────────────────────────────────────────────────────
        hdr_row = QHBoxLayout()
        hdr_row.setSpacing(8)

        hdr_box = QVBoxLayout()
        hdr_box.setSpacing(2)

        self._hdr_title = QLabel("◈  TACTICAL VOICE BIOMETRICS // ENROLLMENT DIRECTIVE")
        self._hdr_title.setFont(_tech_font(10.5, QFont.Weight.Bold, letter_spacing=1.5))
        self._hdr_title.setStyleSheet(f"color: {pal.pri}; background: transparent;")
        hdr_box.addWidget(self._hdr_title)

        self._hdr_sub = QLabel("LOCAL SPEAKER VERIFICATION PROTOCOL // ZERO CLOUD EGRESS")
        self._hdr_sub.setFont(_tech_font(7.5, QFont.Weight.Medium, letter_spacing=1.0))
        self._hdr_sub.setStyleSheet(f"color: {pal.text_dim}; background: transparent;")
        hdr_box.addWidget(self._hdr_sub)
        hdr_row.addLayout(hdr_box)
        hdr_row.addStretch()

        self._top_close_btn = QPushButton("✕")
        self._top_close_btn.setFixedSize(26, 26)
        self._top_close_btn.setFont(_tech_font(9, QFont.Weight.Bold))
        self._top_close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._top_close_btn.setStyleSheet(f"""
            QPushButton {{
                background: {pal.panel2};
                color: {pal.text_med};
                border: 1px solid {pal.border_a};
                border-radius: 13px;
            }}
            QPushButton:hover {{
                background: rgba(255, 60, 60, 0.25);
                color: #ffffff;
                border-color: {pal.red};
            }}
        """)
        self._top_close_btn.clicked.connect(self.reject)
        hdr_row.addWidget(self._top_close_btn)
        layout.addLayout(hdr_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {pal.border_a}; margin: 1px 0;")
        layout.addWidget(sep)

        # ── Description ───────────────────────────────────────────────────────
        self._desc = QLabel(
            "Hands-free wake requires local speaker verification to ensure only enrolled "
            "operators can awaken ALFRED. Once verified and awake, any room participant "
            "may converse normally during the active session."
        )
        self._desc.setWordWrap(True)
        self._desc.setFont(_tech_font(8.5, QFont.Weight.Normal, letter_spacing=0.2))
        self._desc.setStyleSheet(f"color: {pal.text_med}; line-height: 1.4; background: transparent;")
        layout.addWidget(self._desc)

        # ── Operator Identity Row ─────────────────────────────────────────────
        name_row = QHBoxLayout()
        name_row.setSpacing(10)

        self._name_lbl = QLabel("OPERATOR IDENTITY //")
        self._name_lbl.setFont(_tech_font(8.5, QFont.Weight.Bold, letter_spacing=1.0))
        self._name_lbl.setStyleSheet(f"color: {pal.text_dim}; background: transparent;")
        name_row.addWidget(self._name_lbl)

        self._name_input = QLineEdit(self._user_name)
        self._name_input.setFixedHeight(32)
        self._name_input.setFont(_tech_font(9.5, QFont.Weight.Medium, letter_spacing=0.5))
        self._name_input.setStyleSheet(f"""
            QLineEdit {{
                background: {pal.panel2};
                color: {pal.text_bright};
                border: 1px solid {pal.border_a};
                border-radius: 3px;
                padding: 0 10px;
            }}
            QLineEdit:focus {{
                border: 1px solid {pal.pri};
                background: {pal.panel2};
            }}
        """)
        self._name_input.textChanged.connect(self._on_name_changed)
        name_row.addWidget(self._name_input)
        layout.addLayout(name_row)

        # ── Tactical Card Container ──────────────────────────────────────────
        self._card = QFrame()
        self._card.setObjectName("EnrollCard")
        self._card.setStyleSheet(f"""
            QFrame#EnrollCard {{
                background: {pal.panel2};
                border: 1px solid {pal.border_a};
                border-radius: 6px;
            }}
            QFrame#EnrollCard QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        card_lay = QVBoxLayout(self._card)
        card_lay.setContentsMargins(16, 14, 16, 14)
        card_lay.setSpacing(8)

        self._step_label = QLabel(f"Sample {self._current_step} of {self._target_steps}")
        self._step_label.setFont(_tech_font(9.5, QFont.Weight.Bold, letter_spacing=1.0))
        self._step_label.setStyleSheet(f"color: {pal.pri}; background: transparent; border: none;")
        card_lay.addWidget(self._step_label)

        self._instruction_label = QLabel("Say 'Hey Alfred' clearly in your normal speaking voice.")
        self._instruction_label.setFont(_tech_font(9.5, QFont.Weight.Normal, letter_spacing=0.4))
        self._instruction_label.setWordWrap(True)
        self._instruction_label.setStyleSheet(f"color: {pal.text_bright}; background: transparent; border: none;")
        card_lay.addWidget(self._instruction_label)

        self._status_label = QLabel("[ ◈ ]  Ready to record.")
        self._status_label.setFont(_tech_font(8.5, QFont.Weight.DemiBold, letter_spacing=0.5))
        self._status_label.setStyleSheet(f"color: {pal.green}; background: transparent; border: none;")
        card_lay.addWidget(self._status_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setRange(0, self._target_steps)
        self._progress_bar.setValue(0)
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {pal.bg};
                border-radius: 3px;
                border: none;
            }}
            QProgressBar::chunk {{
                background: {pal.pri};
                border-radius: 3px;
            }}
        """)
        card_lay.addWidget(self._progress_bar)

        layout.addWidget(self._card)

        # ── Action Buttons ───────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._record_btn = QPushButton("🔴  RECORD UTTERANCE (2.0s)")
        self._record_btn.setFixedHeight(36)
        self._record_btn.setFont(_tech_font(8.5, QFont.Weight.Bold, letter_spacing=0.8))
        self._record_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._record_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255, 60, 60, 0.12);
                color: {pal.red};
                border: 1px solid rgba(255, 60, 60, 0.45);
                border-radius: 3px;
                padding: 0 14px;
            }}
            QPushButton:hover {{
                background: rgba(255, 60, 60, 0.28);
                color: #ffffff;
                border-color: {pal.red};
            }}
            QPushButton:disabled {{
                background: {pal.panel};
                color: {pal.text_dim};
                border-color: {pal.border_a};
            }}
        """)
        self._record_btn.clicked.connect(self._start_recording)
        btn_row.addWidget(self._record_btn, stretch=4)

        self._delete_btn = QPushButton("🗑  DELETE PROFILE")
        self._delete_btn.setFixedHeight(36)
        self._delete_btn.setFont(_tech_font(8.5, QFont.Weight.Bold, letter_spacing=0.8))
        self._delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._delete_btn.setStyleSheet(f"""
            QPushButton {{
                background: {pal.panel2};
                color: {pal.red};
                border: 1px solid rgba(255, 60, 60, 0.35);
                border-radius: 3px;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background: rgba(255, 60, 60, 0.22);
                border-color: {pal.red};
                color: #ffffff;
            }}
        """)
        self._delete_btn.clicked.connect(self._delete_profile)
        self._delete_btn.hide()
        btn_row.addWidget(self._delete_btn, stretch=3)

        self._close_btn = QPushButton("DISMISS ✕")
        self._close_btn.setFixedHeight(36)
        self._close_btn.setFont(_tech_font(8.5, QFont.Weight.Bold, letter_spacing=0.8))
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setStyleSheet(f"""
            QPushButton {{
                background: {pal.panel2};
                color: {pal.text_med};
                border: 1px solid {pal.border_a};
                border-radius: 3px;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background: {pal.panel};
                color: {pal.text_bright};
                border-color: {pal.pri};
            }}
        """)
        self._close_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._close_btn, stretch=2)

        layout.addLayout(btn_row)

    def showEvent(self, event):
        super().showEvent(event)
        parent = self.parentWidget()
        if parent:
            p_geo = parent.geometry()
            self.move(
                max(20, p_geo.center().x() - self.width() // 2),
                max(20, p_geo.center().y() - self.height() // 2),
            )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = ThemeChrome.get_active().palette
        bg_col = QColor(pal.panel)
        border_col = QColor(pal.border_b)
        painter.setBrush(bg_col)
        painter.setPen(QPen(border_col, 1))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 8, 8)

    def _on_theme_changed(self, theme=None):
        self._apply_theme()

    def _apply_theme(self):
        pal = ThemeChrome.get_active().palette
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {pal.panel};
                border: 1px solid {pal.border_b};
                border-radius: 8px;
            }}
        """)
        self._hdr_title.setStyleSheet(f"color: {pal.pri}; background: transparent;")
        self._hdr_sub.setStyleSheet(f"color: {pal.text_dim}; background: transparent;")
        self._top_close_btn.setStyleSheet(f"""
            QPushButton {{
                background: {pal.panel2};
                color: {pal.text_med};
                border: 1px solid {pal.border_a};
                border-radius: 13px;
            }}
            QPushButton:hover {{
                background: rgba(255, 60, 60, 0.25);
                color: #ffffff;
                border-color: {pal.red};
            }}
        """)
        self._desc.setStyleSheet(f"color: {pal.text_med}; line-height: 1.4; background: transparent;")
        self._name_lbl.setStyleSheet(f"color: {pal.text_dim}; background: transparent;")
        self._name_input.setStyleSheet(f"""
            QLineEdit {{
                background: {pal.panel2};
                color: {pal.text_bright};
                border: 1px solid {pal.border_a};
                border-radius: 3px;
                padding: 0 10px;
            }}
            QLineEdit:focus {{
                border: 1px solid {pal.pri};
                background: {pal.panel2};
            }}
        """)
        self._card.setStyleSheet(f"""
            QFrame#EnrollCard {{
                background: {pal.panel2};
                border: 1px solid {pal.border_a};
                border-radius: 6px;
            }}
            QFrame#EnrollCard QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        self._step_label.setStyleSheet(f"color: {pal.pri}; background: transparent; border: none;")
        self._instruction_label.setStyleSheet(f"color: {pal.text_bright}; background: transparent; border: none;")
        self._set_status(self._status_label.text(), self._last_status_type)
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {pal.bg};
                border-radius: 3px;
                border: none;
            }}
            QProgressBar::chunk {{
                background: {pal.pri};
                border-radius: 3px;
            }}
        """)
        self._record_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255, 60, 60, 0.12);
                color: {pal.red};
                border: 1px solid rgba(255, 60, 60, 0.45);
                border-radius: 3px;
                padding: 0 14px;
            }}
            QPushButton:hover {{
                background: rgba(255, 60, 60, 0.28);
                color: #ffffff;
                border-color: {pal.red};
            }}
            QPushButton:disabled {{
                background: {pal.panel};
                color: {pal.text_dim};
                border-color: {pal.border_a};
            }}
        """)
        self._delete_btn.setStyleSheet(f"""
            QPushButton {{
                background: {pal.panel2};
                color: {pal.red};
                border: 1px solid rgba(255, 60, 60, 0.35);
                border-radius: 3px;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background: rgba(255, 60, 60, 0.22);
                border-color: {pal.red};
                color: #ffffff;
            }}
        """)
        self._close_btn.setStyleSheet(f"""
            QPushButton {{
                background: {pal.panel2};
                color: {pal.text_med};
                border: 1px solid {pal.border_a};
                border-radius: 3px;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background: {pal.panel};
                color: {pal.text_bright};
                border-color: {pal.pri};
            }}
        """)
        self.update()

    def _set_status(self, text: str, status_type: str = "ready"):
        self._last_status_type = status_type
        pal = ThemeChrome.get_active().palette
        color_map = {
            "ready": pal.pri,
            "success": pal.green,
            "warning": pal.acc2,
            "error": pal.red,
            "recording": pal.red,
        }
        col = color_map.get(status_type, pal.pri)
        self._status_label.setStyleSheet(
            f"color: {col}; background: transparent; border: none;"
        )
        self._status_label.setText(text)

    def closeEvent(self, event):
        ThemeChrome.remove_listener(self._on_theme_changed)
        super().closeEvent(event)

    def reject(self):
        ThemeChrome.remove_listener(self._on_theme_changed)
        super().reject()

    def accept(self):
        ThemeChrome.remove_listener(self._on_theme_changed)
        super().accept()

    def _on_name_changed(self, text: str):
        self._user_name = text.strip() or "Operator"
        self._check_existing_profile()

    def _check_existing_profile(self):
        existing = self._store.load_profile(self._user_name)
        if existing:
            self._delete_btn.show()
            self._set_status(
                f"[ 👤 ] Existing profile active ({existing.sample_count} samples, "
                f"threshold {existing.threshold:.2f}). Ready to re-enroll.",
                "ready",
            )
        else:
            self._delete_btn.hide()
            self._set_status("[ ◈ ] Ready to record.", "ready")

    def _start_recording(self):
        if self._is_recording:
            return
        self._is_recording = True
        self._record_btn.setEnabled(False)
        self._name_input.setEnabled(False)
        self._set_status("🔴 Listening... Speak 'Hey Alfred' now.", "recording")

        def _rec_worker():
            try:
                import sounddevice as sd
                samples_n = int(RECORD_DURATION_S * SAMPLE_RATE)
                rec = sd.rec(samples_n, samplerate=SAMPLE_RATE, channels=1, dtype="float32")
                sd.wait()
                audio = rec.flatten()
                self.recording_finished.emit(audio, SAMPLE_RATE)
            except Exception as exc:
                _LOGGER.warning("Microphone recording error: %s", exc)
                self.recording_finished.emit(None, 0)

        threading.Thread(target=_rec_worker, daemon=True).start()

    def _on_recording_finished(self, audio: Optional[np.ndarray], sr: int):
        self._is_recording = False
        self._record_btn.setEnabled(True)
        self._name_input.setEnabled(True)

        if audio is None or sr == 0:
            self._set_status("⚠️ Microphone access failed. Check audio device settings.", "error")
            return

        self.process_audio_sample(audio, sr)

    def process_audio_sample(self, audio: np.ndarray, sample_rate: int) -> tuple[bool, str]:
        """Process an audio sample for the current step."""
        self._set_status("Analyzing audio quality and speaker characteristics...", "ready")
        success, message = self._enrollment_mgr.add_sample(self._user_name, audio, sample_rate)

        if not success:
            self._set_status(f"⚠️ {message}", "warning")
            return False, message

        # Step succeeded
        self._progress_bar.setValue(self._current_step)
        if self._current_step < self._target_steps:
            self._current_step += 1
            self._step_label.setText(f"Sample {self._current_step} of {self._target_steps}")
            if self._current_step == 2:
                self._instruction_label.setText("Say 'Hey Alfred' again (slightly change your distance or tone).")
            elif self._current_step == 3:
                self._instruction_label.setText("Say 'Hey Alfred' one last time to complete calibration.")
            self._set_status(f"✓ Sample accepted. {message}", "ready")
            return True, message
        else:
            # All steps completed!
            try:
                profile = self._enrollment_mgr.build_profile(self._user_name)
                self._store.save_profile(profile)
                self._set_status(
                    f"🎉 Voice Profile Successfully Enrolled! (Threshold: {profile.threshold:.2f})",
                    "success",
                )
                self._record_btn.setEnabled(False)
                self._delete_btn.show()
                self.profile_enrolled.emit(self._user_name)
                QTimer.singleShot(1500, self.accept)
                return True, "Profile enrolled successfully"
            except Exception as exc:
                self._set_status(f"❌ Failed to build profile: {exc}", "error")
                return False, str(exc)

    def _delete_profile(self):
        self._store.delete_profile(self._user_name)
        self._enrollment_mgr.reset_session(self._user_name)
        self._current_step = 1
        self._progress_bar.setValue(0)
        self._step_label.setText(f"Sample {self._current_step} of {self._target_steps}")
        self._instruction_label.setText("Say 'Hey Alfred' clearly in your normal speaking voice.")
        self._set_status("Profile deleted. Ready to re-enroll.", "ready")
        self._record_btn.setEnabled(True)
        self._delete_btn.hide()
        self.profile_deleted.emit()
