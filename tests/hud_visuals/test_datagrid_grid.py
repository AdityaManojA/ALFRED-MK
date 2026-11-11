"""Tests for core.hud.datagrid.grid — DeveloperDataGridWidget (2x2 telemetry grid)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPen, QResizeEvent

from tests.hud_visuals._helpers import make_palette, rect_tuple

from core.hud.datagrid import grid
from core.hud.datagrid.providers import GridDataSnapshot

PAL = make_palette(panel="#202020", border_a="#FFFF00", text_dim="#808080",
                   acc2="#0000FF", text_bright="#FFFFFF")


@pytest.fixture
def theme(monkeypatch):
    holder = {"theme": SimpleNamespace(name="t1", palette=PAL)}
    monkeypatch.setattr(grid.ThemeChrome, "get_active", lambda: holder["theme"])
    return holder


@pytest.fixture
def worker(monkeypatch):
    fake = MagicMock()
    fake_cls = MagicMock()
    fake_cls.instance.return_value = fake
    monkeypatch.setattr(grid, "DataGridWorker", fake_cls)
    return fake_cls


@pytest.fixture
def widget(theme, worker):
    w = grid.DeveloperDataGridWidget()
    yield w
    w.deleteLater()


def _resize(w, width, height=92):
    w.resize(width, height)
    w.resizeEvent(QResizeEvent(QSize(width, height), QSize()))


def test_init_wires_worker_without_starting_real_thread(widget, worker):
    assert widget.height() == 92
    worker.instance.assert_called_once_with(widget._on_worker_update)
    worker.instance.return_value.start.assert_called_once()
    assert widget._cached_cells == ("", "", "", "")


def test_theme_cache_reads_palette_tokens(widget):
    assert widget._c_bg.name() == "#202020"
    assert widget._c_border.name() == "#ffff00"
    assert widget._c_pri.name() == "#ff0000"
    assert widget._c_dim.name() == "#808080"
    assert widget._c_warn.name() == "#0000ff"
    assert widget._c_white.name() == "#ffffff"
    assert widget._pen_warn.color().name() == "#0000ff"


def test_theme_cache_only_refreshes_when_theme_name_changes(widget, theme):
    theme["theme"] = SimpleNamespace(name="t1", palette=make_palette(pri="#123456"))
    widget._update_theme_cache()
    assert widget._c_pri.name() == "#ff0000"  # same name -> cached
    theme["theme"] = SimpleNamespace(name="t2", palette=make_palette(pri="#123456", acc2="", text_bright="", white="#EEEEEE"))
    widget._update_theme_cache()
    assert widget._c_pri.name() == "#123456"
    assert widget._c_warn.name() == "#00ff00"   # acc2 empty -> falls back to acc
    assert widget._c_white.name() == "#eeeeee"  # text_bright empty -> falls back to white


def test_resize_lays_out_four_quadrants(widget):
    _resize(widget, 300)
    assert (widget._mid_x, widget._mid_y, widget._w_int, widget._h_int) == (150, 46, 300, 92)
    assert rect_tuple(widget._rect_backplate) == (1.0, 1.0, 298.0, 90.0)
    assert rect_tuple(widget._rect_git_val) == (6.0, 18.0, 140.0, 16.0)
    assert rect_tuple(widget._rect_ports_lbl) == (156.0, 4.0, 140.0, 12.0)
    assert rect_tuple(widget._rect_proc_val) == (6.0, 64.0, 140.0, 16.0)
    assert rect_tuple(widget._rect_sess_val) == (156.0, 64.0, 140.0, 16.0)


def test_apply_snapshot_only_replaces_on_text_change(widget, monkeypatch):
    upd = MagicMock()
    monkeypatch.setattr(widget, "update", upd)
    snap = GridDataSnapshot(git_text="main • clean", ports_text="8000", proc_text="py • 1 MB", session_text="00:00:01 • 0 tok")
    widget._apply_snapshot(snap)
    assert widget.snapshot is snap
    assert widget._cached_cells == ("main • clean", "8000", "py • 1 MB", "00:00:01 • 0 tok")
    upd.assert_not_called()  # hidden widget -> no repaint request

    same_text = GridDataSnapshot(git_text="main • clean", git_state="warn", ports_text="8000",
                                 proc_text="py • 1 MB", session_text="00:00:01 • 0 tok")
    widget._apply_snapshot(same_text)
    assert widget.snapshot is snap  # state-only change is ignored


def test_apply_snapshot_requests_repaint_when_visible(widget, monkeypatch):
    upd = MagicMock()
    monkeypatch.setattr(widget, "update", upd)
    monkeypatch.setattr(widget, "isVisible", lambda: True)
    widget._apply_snapshot(GridDataSnapshot(git_text="dev"))
    upd.assert_called_once()


def test_worker_callback_routes_through_signal(widget):
    snap = GridDataSnapshot(session_text="00:01:00 • 2.0k tok")
    widget._on_worker_update(snap)  # same thread -> direct connection
    assert widget.snapshot is snap


def test_dispose_is_safe(widget, worker):
    widget.dispose()
    worker.instance.return_value.stop.assert_not_called()


def test_paint_uses_state_colours_and_draws_frame(widget, monkeypatch):
    pens: list[str] = []

    class RecordingPainter(QPainter):
        def setPen(self, pen):  # noqa: N802 - Qt naming
            pens.append(QPen(pen).color().name() if not isinstance(pen, QColor) else pen.name())
            super().setPen(pen)

    monkeypatch.setattr(grid, "QPainter", RecordingPainter)
    _resize(widget, 300)
    widget.snapshot = GridDataSnapshot(git_text="a", git_state="accent", ports_text="b", ports_state="warn",
                                       proc_text="c", proc_state="dim", session_text="d", session_state="other")
    img = QImage(300, 92, QImage.Format.Format_RGBA8888)
    img.fill(Qt.GlobalColor.black)
    widget.render(img)

    # Order: border, then (label dim, value pen) for git, ports, proc, session
    assert pens == ["#ffff00",
                    "#808080", "#ff0000",   # accent -> pri
                    "#808080", "#0000ff",   # warn -> acc2
                    "#808080", "#808080",   # dim -> dim
                    "#808080", "#808080"]   # unknown -> dim
    assert img.pixelColor(3, 40).name() == "#202020"  # backplate fill
    divider = [img.pixelColor(x, 40) for x in (149, 150)]
    assert any(c.red() > 100 and c.green() > 100 and c.blue() < 60 for c in divider)
