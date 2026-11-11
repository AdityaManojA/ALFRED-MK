"""Small, local and atomic persistence layer for scheduled work."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

LEDGER_PATH = Path("data/schedule.json")


class Ledger:
    """Owns the schedule file and keeps malformed or partial writes harmless."""

    def __init__(self, path: Path | str = LEDGER_PATH) -> None:
        """Store the ledger path, create its parent directory and set up a lock."""
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def load(self) -> list[dict[str, Any]]:
        """Return the task list from the JSON ledger, or [] if missing or invalid."""
        with self._lock:
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                return []
        return payload if isinstance(payload, list) else []

    def save(self, tasks: list[dict[str, Any]]) -> None:
        """Atomically write the task list to the ledger via a temporary file and os.replace."""
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        with self._lock:
            temporary.write_text(json.dumps(tasks, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
            os.replace(temporary, self.path)
