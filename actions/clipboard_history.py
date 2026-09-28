# clipboard_history.py
"""
Maintains a session-scoped ring buffer of clipboard entries.
Every time Alfred copies or reads the clipboard, the entry is logged here.
The user can ask "what did I copy earlier?" or "show clipboard history".
"""
from __future__ import annotations

import threading
from datetime import datetime
from typing import Optional

import pyperclip  # already a dependency via clipboard_manager

_MAX_ENTRIES = 20
_lock = threading.Lock()
_history: list[dict] = []  # [{text, ts}]


# ── Internal helpers ──────────────────────────────────────────────────────────

def _push(text: str) -> None:
    """Add an entry, deduplicating consecutive identical values."""
    if not text or not text.strip():
        return
    with _lock:
        if _history and _history[-1]["text"] == text:
            return
        _history.append({"text": text.strip(), "ts": datetime.now().strftime("%H:%M")})
        if len(_history) > _MAX_ENTRIES:
            _history.pop(0)


def _snapshot() -> list[dict]:
    with _lock:
        return list(_history)


# ── Action handler ────────────────────────────────────────────────────────────

def clipboard_history_action(parameters: dict, **kwargs) -> str:
    action = str(parameters.get("action", "show")).lower().strip()

    if action in ("show", "list", "history"):
        # Also pull current clipboard so the list is always fresh
        try:
            current = pyperclip.paste()
            _push(current)
        except Exception:
            pass

        entries = _snapshot()
        if not entries:
            return "The clipboard history is empty for this session."

        lines = ["Clipboard history (most recent last):"]
        for i, e in enumerate(entries, 1):
            preview = e["text"][:80].replace("\n", " ")
            ellipsis = "…" if len(e["text"]) > 80 else ""
            lines.append(f"  {i}. [{e['ts']}] {preview}{ellipsis}")
        return "\n".join(lines)

    if action in ("clear", "wipe", "reset"):
        with _lock:
            _history.clear()
        return "Clipboard history cleared."

    if action in ("latest", "last", "current"):
        try:
            current = pyperclip.paste()
            _push(current)
        except Exception:
            return "Could not read the clipboard."

        entries = _snapshot()
        if not entries:
            return "Nothing in the clipboard history yet."
        e = entries[-1]
        preview = e["text"][:120].replace("\n", " ")
        return f"Last copied [{e['ts']}]: {preview}"

    if action == "push":
        text = str(parameters.get("text", "")).strip()
        if not text:
            return "No text provided to push into clipboard history."
        _push(text)
        return f"Logged to clipboard history: {text[:60]}"

    return f"Unknown clipboard_history action: '{action}'. Use show | clear | latest | push."


# ── Tool declaration (auto-discovered by core/action_loader.py) ───────────────
TOOL = {
    "name": "clipboard_history",
    "description": (
        "Session clipboard history. Shows the last items copied during this session, "
        "clears history, or retrieves the most recent entry. "
        "Actions: show, clear, latest."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "show | clear | latest | push",
            },
            "text": {
                "type": "STRING",
                "description": "Text to push into history (only for action=push).",
            },
        },
        "required": ["action"],
    },
    "handler": clipboard_history_action,
}
