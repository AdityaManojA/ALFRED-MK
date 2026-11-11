"""Behavioural tests for core.ui.task_board.TaskBoard (offscreen Qt, fake scheduler)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QWidget

from core.ui.task_board import TaskBoard

_app = QApplication.instance() or QApplication(["test", "-platform", "offscreen"])


class FakeScheduler:
    def __init__(self, tasks=None):
        self.tasks = list(tasks or [])
        self.paused = False
        self.calls = []

    def list_tasks(self):
        return list(self.tasks)

    def set_paused(self, value):
        self.calls.append(("set_paused", value))
        self.paused = value

    def cancel(self, tid):
        self.calls.append(("cancel", tid))

    def acknowledge(self, tid):
        self.calls.append(("acknowledge", tid))

    def trigger_now(self, tid):
        self.calls.append(("trigger_now", tid))

    def delete(self, tid):
        self.calls.append(("delete", tid))
        self.tasks = [t for t in self.tasks if t.get("id") != tid]


@pytest.fixture
def parent():
    w = QWidget()
    yield w
    w.deleteLater()


def _rows(board):
    """Return (label_text, [button_texts]) for each task row frame."""
    out = []
    for i in range(board._rows.count()):
        w = board._rows.itemAt(i).widget()
        if type(w) is QFrame:
            label = w.findChild(QLabel).text()
            buttons = [b.text() for b in w.findChildren(QPushButton)]
            out.append((label, buttons))
    return out


def _button(board, row_idx, text):
    frames = [board._rows.itemAt(i).widget() for i in range(board._rows.count())
              if type(board._rows.itemAt(i).widget()) is QFrame]
    return next(b for b in frames[row_idx].findChildren(QPushButton) if b.text() == text)


def test_empty_board_shows_placeholder(parent):
    board = TaskBoard(FakeScheduler(), parent)
    first = board._rows.itemAt(0).widget()
    assert isinstance(first, QLabel) and first.text() == "No scheduled local tasks."
    assert board._pause.text() == "PAUSE"
    board._timer.stop()


def test_rows_sorted_formatted_and_buttons(parent):
    tasks = [
        {"id": "b", "trigger_time": "2026-01-01T15:30:00", "name": "Later", "status": "pending",
         "action_type": "macro", "warned": True},
        {"id": "a", "trigger_time": "2026-01-01T09:05:00", "payload": {"message": "x" * 60},
         "status": "done", "action_type": "reminder"},
        {"id": "c", "trigger_time": "garbage", "status": "done", "acknowledged": True},
    ]
    board = TaskBoard(FakeScheduler(tasks), parent)
    board._timer.stop()
    rows = _rows(board)
    # sorted by raw trigger_time string ("garbage" sorts after ISO dates);
    # unparseable time shown as --:--, message truncated to 42 chars
    assert rows[0] == ("09:05  " + "x" * 42 + "  [DONE]", ["ACK", "DEL"])
    assert rows[1] == ("15:30  Later  [PENDING]", ["ABORT", "NOW", "DEL"])
    assert rows[2] == ("--:--  Task  [DONE]", ["DEL"])


@pytest.mark.parametrize("button, call", [
    ("ABORT", "cancel"), ("NOW", "trigger_now"), ("DEL", "delete"),
])
def test_row_buttons_call_scheduler(parent, button, call):
    sched = FakeScheduler([{"id": "t1", "trigger_time": "2026-01-01T10:00:00", "status": "pending",
                            "action_type": "macro", "warned": True}])
    board = TaskBoard(sched, parent)
    board._timer.stop()
    _button(board, 0, button).click()
    assert (call, "t1") in sched.calls


def test_ack_button_calls_acknowledge(parent):
    sched = FakeScheduler([{"id": "r1", "trigger_time": "2026-01-01T10:00:00", "status": "done"}])
    board = TaskBoard(sched, parent)
    board._timer.stop()
    _button(board, 0, "ACK").click()
    assert sched.calls == [("acknowledge", "r1")]


def test_delete_refreshes_to_empty(parent):
    sched = FakeScheduler([{"id": "d", "trigger_time": "2026-01-01T10:00:00", "status": "pending"}])
    board = TaskBoard(sched, parent)
    board._timer.stop()
    _button(board, 0, "DEL").click()
    _app.processEvents()
    assert _rows(board) == []


def test_toggle_pause_flips_scheduler_and_label(parent):
    sched = FakeScheduler()
    board = TaskBoard(sched, parent)
    board._timer.stop()
    board._pause.click()
    assert sched.paused is True and board._pause.text() == "RESUME"
    board._pause.click()
    assert sched.paused is False and board._pause.text() == "PAUSE"


def test_present_event_armed_macro_shows_notice(parent):
    board = TaskBoard(FakeScheduler(), parent)
    board._timer.stop()
    board.present_event({"action_type": "macro", "warned": True, "status": "pending"})
    assert "AUTOMATION ARMED" in board._notice.text()
    assert not board._notice.isHidden()


def test_present_event_delivered_reminder(parent):
    board = TaskBoard(FakeScheduler(), parent)
    board._timer.stop()
    board.present_event({"action_type": "speak", "status": "done"})
    assert board._notice.text().startswith("REMINDER DELIVERED")


def test_present_event_other_task_keeps_notice_hidden(parent):
    board = TaskBoard(FakeScheduler(), parent)
    board._timer.stop()
    board.present_event({"action_type": "macro", "warned": False, "status": "pending"})
    assert board._notice.isHidden()
    assert board._notice.text() == ""
