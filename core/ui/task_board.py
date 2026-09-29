"""Thread-safe-friendly visual control surface for the local task scheduler."""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget


class TaskBoard(QFrame):
    """Compact HUD board for pending work, reminder acknowledgement, and macro abort."""

    def __init__(self, scheduler, parent: QWidget) -> None:
        super().__init__(parent)
        self.scheduler = scheduler
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setFixedWidth(500)
        self.setStyleSheet(
            "QFrame { background:#07111c; border:1px solid #00d9ff; } "
            "QLabel { color:#d3e9ff; border:none; } "
            "QPushButton { color:#00d9ff; background:#0b2031; border:1px solid #17677b; padding:4px 7px; } "
            "QPushButton:hover { background:#12354c; }"
        )
        root = QVBoxLayout(self); root.setContentsMargins(10, 9, 10, 9); root.setSpacing(6)
        top = QHBoxLayout()
        title = QLabel("TASK BOARD // LOCAL SCHEDULE")
        title.setStyleSheet("font-weight:bold; color:#00d9ff;")
        top.addWidget(title); top.addStretch()
        self._pause = QPushButton("PAUSE")
        self._pause.clicked.connect(self._toggle_pause)
        close = QPushButton("×"); close.clicked.connect(self.hide)
        top.addWidget(self._pause); top.addWidget(close); root.addLayout(top)
        self._notice = QLabel("")
        self._notice.setWordWrap(True); self._notice.hide(); root.addWidget(self._notice)
        self._scroll = QScrollArea(); self._scroll.setWidgetResizable(True); self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._body = QWidget(); self._rows = QVBoxLayout(self._body); self._rows.setContentsMargins(0, 0, 0, 0); self._rows.setSpacing(5)
        self._scroll.setWidget(self._body); root.addWidget(self._scroll)
        self._timer = QTimer(self); self._timer.timeout.connect(self.refresh); self._timer.start(1000)
        self.refresh()

    def present_event(self, task: dict) -> None:
        if task.get("action_type") == "macro" and task.get("warned") and task.get("status") == "pending":
            self._notice.setText("AUTOMATION ARMED: executing in 10 seconds. Use ABORT to cancel.")
            self._notice.setStyleSheet("color:#ffbc5b; border:1px solid #9d6a1e; padding:5px;")
            self._notice.show(); self.show(); self.raise_()
        elif task.get("action_type") in {"reminder", "speak"} and task.get("status") == "done":
            self._notice.setText("REMINDER DELIVERED: acknowledge it on the task board.")
            self._notice.setStyleSheet("color:#7dffbc; border:1px solid #257b54; padding:5px;")
            self._notice.show(); self.show(); self.raise_()
        self.refresh()

    def _toggle_pause(self) -> None:
        self.scheduler.set_paused(not self.scheduler.paused)
        self.refresh()

    def _clear_rows(self) -> None:
        while self._rows.count():
            item = self._rows.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def refresh(self) -> None:
        self._pause.setText("RESUME" if self.scheduler.paused else "PAUSE")
        self._clear_rows()
        tasks = self.scheduler.list_tasks()
        if not tasks:
            self._rows.addWidget(QLabel("No scheduled local tasks.")); self._rows.addStretch(); return
        for task in sorted(tasks, key=lambda item: item.get("trigger_time", "")):
            row = QFrame(); row.setStyleSheet("QFrame { border:1px solid #173748; background:#091924; }")
            layout = QHBoxLayout(row); layout.setContentsMargins(7, 5, 7, 5); layout.setSpacing(5)
            try:
                when = datetime.fromisoformat(task.get("trigger_time", "")).strftime("%H:%M")
            except (TypeError, ValueError):
                when = "--:--"
            text = task.get("payload", {}).get("message") or task.get("name", "Task")
            layout.addWidget(QLabel(f"{when}  {str(text)[:42]}  [{task.get('status', 'pending').upper()}]"), 1)
            task_id = task.get("id", "")
            if task.get("action_type") == "macro" and task.get("status") == "pending" and task.get("warned"):
                abort = QPushButton("ABORT"); abort.clicked.connect(lambda _, ident=task_id: self._abort(ident)); layout.addWidget(abort)
            if task.get("status") == "done" and not task.get("acknowledged"):
                ack = QPushButton("ACK"); ack.clicked.connect(lambda _, ident=task_id: self._ack(ident)); layout.addWidget(ack)
            if task.get("status") == "pending":
                now = QPushButton("NOW"); now.clicked.connect(lambda _, ident=task_id: self._now(ident)); layout.addWidget(now)
            delete = QPushButton("DEL"); delete.clicked.connect(lambda _, ident=task_id: self._delete(ident)); layout.addWidget(delete)
            self._rows.addWidget(row)
        self._rows.addStretch()

    def _abort(self, task_id: str) -> None:
        self.scheduler.cancel(task_id); self.refresh()

    def _ack(self, task_id: str) -> None:
        self.scheduler.acknowledge(task_id); self.refresh()

    def _now(self, task_id: str) -> None:
        self.scheduler.trigger_now(task_id); self.refresh()

    def _delete(self, task_id: str) -> None:
        self.scheduler.delete(task_id); self.refresh()
