"""Behavioural tests for core.ui.image_deck (offscreen Qt, temp images)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QPoint, QPointF, QSize, Qt
from PyQt6.QtGui import QColor, QImage, QMouseEvent
from PyQt6.QtWidgets import QApplication, QWidget

from core.ui import image_deck
from core.ui.image_deck import IMAGE_PANEL_MAX_H, IMAGE_PANEL_MAX_W, ImageDeckPanel, _ImageLoadTask

_app = QApplication.instance() or QApplication(["test", "-platform", "offscreen"])


def _write_png(path, w, h):
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(QColor("red"))
    assert img.save(str(path), "PNG")
    return path


def test_load_task_scales_keeping_aspect(tmp_path):
    path = _write_png(tmp_path / "wide.png", 200, 100)
    task = _ImageLoadTask(str(path), QSize(50, 50))
    got, failed = [], []
    task.signals.loaded.connect(got.append)
    task.signals.failed.connect(lambda: failed.append(True))
    task.run()
    assert not failed
    assert got[0].size() == QSize(50, 25)


def test_load_task_emits_failed_for_missing_file(tmp_path):
    task = _ImageLoadTask(str(tmp_path / "missing.png"), QSize(10, 10))
    got, failed = [], []
    task.signals.loaded.connect(got.append)
    task.signals.failed.connect(lambda: failed.append(True))
    task.run()
    assert failed == [True] and got == []


class _SyncPool:
    """Runs tasks inline instead of on QThreadPool."""

    def start(self, task):
        task.run()


@pytest.fixture
def panel():
    parent = QWidget()
    p = ImageDeckPanel(parent)
    p._pool = _SyncPool()
    yield p
    parent.deleteLater()


def test_panel_fixed_size(panel):
    assert panel.size() == QSize(IMAGE_PANEL_MAX_W, IMAGE_PANEL_MAX_H)
    assert panel.image.text() == "Awaiting image…"


def test_show_image_sets_pixmap_and_caption(panel, tmp_path):
    path = _write_png(tmp_path / "a.png", 40, 30)
    panel.show_image(str(path), "Gotham skyline")
    assert panel.caption.text() == "Gotham skyline"
    assert not panel.isHidden()
    pix = panel.image.pixmap()
    assert pix is not None and not pix.isNull()


def test_show_image_failure_sets_unavailable(panel, tmp_path):
    panel.show_image(str(tmp_path / "nope.png"))
    assert panel.image.text() == "Image unavailable"
    assert panel.caption.text() == ""


def test_hide_emits_closed(panel, tmp_path):
    fired = []
    panel.closed.connect(lambda: fired.append(1))
    panel.show()
    panel.hide()
    assert fired == [1]


def _mouse(etype, pos, button=Qt.MouseButton.LeftButton):
    p = QPointF(pos)
    return QMouseEvent(etype, p, p, button, button, Qt.KeyboardModifier.NoModifier)


def test_drag_moves_panel(panel):
    panel.move(100, 100)
    panel.mousePressEvent(_mouse(QMouseEvent.Type.MouseButtonPress, QPoint(10, 10)))
    assert panel._drag_offset == QPoint(10, 10)
    panel.mouseMoveEvent(_mouse(QMouseEvent.Type.MouseMove, QPoint(25, 40)))
    assert panel.pos() == QPoint(115, 130)
    panel.mouseReleaseEvent(_mouse(QMouseEvent.Type.MouseButtonRelease, QPoint(25, 40)))
    assert panel._drag_offset is None
    panel.mouseMoveEvent(_mouse(QMouseEvent.Type.MouseMove, QPoint(90, 90)))
    assert panel.pos() == QPoint(115, 130)


def test_right_click_does_not_start_drag(panel):
    panel.mousePressEvent(_mouse(QMouseEvent.Type.MouseButtonPress, QPoint(5, 5),
                                 Qt.MouseButton.RightButton))
    assert panel._drag_offset is None
