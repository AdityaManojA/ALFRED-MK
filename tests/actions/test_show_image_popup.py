"""Behavioural tests for actions.show_image_popup.

Runs Qt with the offscreen platform plugin, so widgets are created and
"shown" without any window appearing on screen.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytest.importorskip("PyQt6.QtWidgets")
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

import actions.show_image_popup as sip
from actions.show_image_popup import ImagePopupOverlay, action

_APP = QApplication.instance() or QApplication([])


@pytest.fixture
def png(tmp_path):
    path = tmp_path / "img.png"
    img = QImage(800, 200, QImage.Format.Format_RGB32)
    img.fill(QColor("red"))
    assert img.save(str(path))
    return path


# ── action() validation ──────────────────────────────────────────────────────

def test_requires_image_path():
    assert action({}) == "Error: image_path parameter is required for show_image_popup action."


def test_relative_path_resolved_against_project_root():
    out = action({"image_path": "definitely/not/here.png"})
    project_root = Path(sip.__file__).resolve().parent.parent
    expected = str((project_root / "definitely/not/here.png").resolve())
    assert out == f"Error: Image file not found: {expected}"


def test_requires_player(png):
    assert action({"image_path": str(png)}) == "Error: Player context not available to show overlay."


def test_player_without_central_widget(png):
    assert action({"image_path": str(png)}, player=SimpleNamespace()) == "Error: Could not get central widget."
    player = SimpleNamespace(centralWidget=lambda: None)
    assert action({"image_path": str(png)}, player=player) == "Error: Could not get central widget."


def test_shows_overlay_and_keeps_reference(png):
    parent = QWidget()
    parent.resize(600, 400)
    player = SimpleNamespace(_win=SimpleNamespace(centralWidget=lambda: parent))
    out = action({"image_path": str(png)}, player=player)
    assert out == f"Showing image popup: {png}"
    overlay = player._image_popup_overlay
    assert isinstance(overlay, ImagePopupOverlay)
    assert overlay.parent() is parent
    overlay.close()
    parent.close()


def test_action_reports_unexpected_errors(png, monkeypatch):
    monkeypatch.setattr(sip, "ImagePopupOverlay", MagicMock(side_effect=RuntimeError("no display")))
    player = SimpleNamespace(centralWidget=lambda: object())
    assert action({"image_path": str(png)}, player=player) == "Error showing image popup: no display"


# ── overlay widget ───────────────────────────────────────────────────────────

def test_overlay_scales_image_to_fit_400(png):
    overlay = ImagePopupOverlay(str(png))
    pix = overlay._image_label.pixmap()
    assert not pix.isNull()
    assert (pix.width(), pix.height()) == (400, 100)  # aspect ratio kept
    overlay.close()


def test_overlay_missing_image_shows_text(tmp_path):
    missing = tmp_path / "gone.png"
    overlay = ImagePopupOverlay(str(missing))
    assert overlay._image_label.text() == f"[Image not found: {missing}]"
    overlay.close()


def test_dismiss_button_hides_and_emits(png):
    overlay = ImagePopupOverlay(str(png))
    overlay.show()
    received = []
    overlay.dismissed.connect(lambda: received.append(True))
    button = overlay.findChild(QPushButton)
    assert button.text() == "Dismiss"
    button.click()
    assert received == [True]
    assert not overlay.isVisible()
    overlay.close()
