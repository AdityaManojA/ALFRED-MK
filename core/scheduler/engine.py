"""One local scheduler loop shared by reminders and user-authored macros."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable

from .automation import run_macro
from .ledger import Ledger

NEAR_TICK_S = 1
IDLE_TICK_S = 10
WARNING_S = 10


class SchedulerEngine:
    def __init__(self, speak: Callable[[str], None] | None = None, notify: Callable[[dict], None] | None = None, ledger: Ledger | None = None) -> None:
        self.ledger = ledger or Ledger()
        self.speak = speak or (lambda _text: None)
        self.notify = notify or (lambda _task: None)
        self._stop_event, self._lock = threading.Event(), threading.RLock()
        self._paused = False
        self._thread: threading.Thread | None = None

    @property
    def paused(self) -> bool:
        with self._lock:
            return self._paused

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True, name="alfred-scheduler")
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def set_paused(self, paused: bool) -> None:
        with self._lock:
            self._paused = bool(paused)

    def list_tasks(self) -> list[dict[str, Any]]:
        return self.ledger.load()

    def add(self, name: str, action_type: str, payload: dict[str, Any], trigger_time: str, recurrence: str = "once") -> dict[str, Any]:
        task = {"id": uuid.uuid4().hex, "name": str(name), "trigger_time": str(trigger_time), "recurrence": recurrence if recurrence == "daily" else "once", "action_type": action_type, "payload": dict(payload), "status": "pending", "warned": False, "acknowledged": False}
        with self._lock:
            tasks = self.ledger.load(); tasks.append(task); self.ledger.save(tasks)
        self.notify(task)
        return task

    def _change(self, task_id: str, mutate: Callable[[dict[str, Any]], None]) -> bool:
        with self._lock:
            tasks = self.ledger.load(); task = next((item for item in tasks if item.get("id") == task_id), None)
            if task is None:
                return False
            mutate(task); self.ledger.save(tasks)
        self.notify(task)
        return True

    def cancel(self, task_id: str) -> bool:
        return self._change(task_id, lambda task: task.update(status="cancelled"))

    def delete(self, task_id: str) -> bool:
        with self._lock:
            tasks = self.ledger.load(); kept = [task for task in tasks if task.get("id") != task_id]
            if len(kept) == len(tasks):
                return False
            self.ledger.save(kept)
        self.notify({"event": "deleted", "id": task_id})
        return True

    def acknowledge(self, task_id: str) -> bool:
        return self._change(task_id, lambda task: task.update(acknowledged=True))

    def trigger_now(self, task_id: str) -> bool:
        return self._change(task_id, lambda task: task.update(trigger_time=datetime.now().isoformat(), status="pending", warned=True))

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            self.tick(); self._stop_event.wait(self._delay())

    def _delay(self) -> int:
        now = datetime.now()
        for task in self.ledger.load():
            if task.get("status") != "pending":
                continue
            try:
                if 0 <= (datetime.fromisoformat(task["trigger_time"]) - now).total_seconds() <= 60:
                    return NEAR_TICK_S
            except (KeyError, TypeError, ValueError):
                continue
        return IDLE_TICK_S

    def _execute(self, task: dict[str, Any]) -> str:
        if task.get("action_type") in {"speak", "reminder"}:
            self.speak(f"Reminder, sir: {task.get('payload', {}).get('message', '')}")
            return "done"
        if task.get("action_type") == "macro":
            result = run_macro(task.get("payload", {}))
            if not result.ok:
                self.speak(f"Scheduled automation aborted: {result.detail}")
                task["error"] = result.detail
                return "failed"
            return "done"
        task["error"] = "Unknown task action."
        return "failed"

    def tick(self, now: datetime | None = None) -> None:
        if self.paused:
            return
        now = now or datetime.now()
        with self._lock:
            tasks, changed, notifications = self.ledger.load(), False, []
            for task in tasks:
                if task.get("status") != "pending":
                    continue
                try:
                    due = datetime.fromisoformat(task["trigger_time"])
                except (KeyError, TypeError, ValueError):
                    task.update(status="failed", error="Invalid trigger time."); changed = True; notifications.append(dict(task)); continue
                delta = (due - now).total_seconds()
                if task.get("action_type") == "macro" and 0 < delta <= WARNING_S and not task.get("warned"):
                    task["warned"] = True; self.speak("Executing scheduled automation in 10 seconds, sir. Please release keyboard."); changed = True; notifications.append(dict(task))
                if delta > 0:
                    continue
                outcome = self._execute(task)
                if task.get("recurrence") == "daily" and outcome == "done":
                    task.update(trigger_time=(due + timedelta(days=1)).isoformat(), status="pending", warned=False, acknowledged=False)
                else:
                    task["status"] = outcome
                changed = True; notifications.append(dict(task))
            if changed:
                self.ledger.save(tasks)
        for task in notifications:
            self.notify(task)
