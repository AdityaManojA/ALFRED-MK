"""
actions/intel_notes.py — Dedicated Intel & Notes Terminal Action.

Provides a structured outlet for Alfred to write links, research notes,
code snippets, and reference data directly into the user's dedicated
Notes Terminal rather than cluttering the conversational chat stream.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

def _config_dir() -> Path:
    base = Path(__file__).resolve().parent.parent
    d = base / "config"
    d.mkdir(parents=True, exist_ok=True)
    return d

_NOTES_FILE = _config_dir() / "intel_notes.json"


def _load_notes() -> list[dict]:
    if not _NOTES_FILE.exists():
        return []
    try:
        return json.loads(_NOTES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_notes(notes: list[dict]) -> None:
    try:
        _NOTES_FILE.write_text(json.dumps(notes, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[intel_notes] Error saving notes: {e}")


def _auto_detect_type(content: str, explicit_type: str = "") -> str:
    if explicit_type and explicit_type.lower() in ("note", "link", "data", "code"):
        return explicit_type.lower()
    
    c = content.strip()
    # Check for URL
    if re.search(r"https?://[^\s]+", c):
        return "link"
    # Check for code blocks or JSON / key-value data
    if c.startswith("```") or "\n    " in c or c.startswith("{") or c.startswith("["):
        return "code" if "```" in c else "data"
    if ":" in c and "\n" in c and len(c.splitlines()) > 2:
        return "data"
    return "note"


def intel_notes(parameters: dict, player=None, **_) -> str:
    """Action handler called by Gemini / action_loader."""
    action = str(parameters.get("action", "add")).lower().strip()
    title = str(parameters.get("title", "")).strip()
    content = str(parameters.get("content", "")).strip()
    raw_type = str(parameters.get("note_type", "")).strip()

    if action == "clear":
        _save_notes([])
        if player and hasattr(player, "clear_intel_notes"):
            player.clear_intel_notes()
        return "Dedicated Intel & Notes Terminal cleared."

    if action == "list":
        notes = _load_notes()
        if not notes:
            return "Intel & Notes Terminal is currently empty."
        items = [f"• [{n.get('type', 'note').upper()}] {n.get('title', 'Untitled')} ({n.get('time', '')})" for n in notes[-10:]]
        return f"Recent Intel entries ({len(notes)} total):\n" + "\n".join(items)

    # Default action: "add"
    if not content and not title:
        return "Please provide content or a link to post into the Intel Terminal."

    if not title:
        # Generate short title from content
        title = content.splitlines()[0][:40] + ("..." if len(content.splitlines()[0]) > 40 else "")

    note_type = _auto_detect_type(content, raw_type)
    timestamp = datetime.now().strftime("%H:%M:%S")
    date_str = datetime.now().strftime("%Y-%m-%d")

    entry = {
        "title": title,
        "content": content,
        "type": note_type,
        "time": timestamp,
        "date": date_str,
    }

    # Persist
    notes = _load_notes()
    notes.append(entry)
    # Keep up to 200 notes
    if len(notes) > 200:
        notes = notes[-200:]
    _save_notes(notes)

    # Forward to UI if live
    if player and hasattr(player, "add_intel_note"):
        try:
            player.add_intel_note(title, content, note_type)
        except Exception as e:
            print(f"[intel_notes] Forward to player failed: {e}")

    type_labels = {
        "link": "Link recorded",
        "data": "Data logged",
        "code": "Code snippet saved",
        "note": "Note pinned",
    }
    label = type_labels.get(note_type, "Intel recorded")
    return f"{label} to dedicated Notes Terminal: '{title}'."


TOOL = {
    "name": "intel_notes",
    "description": (
        "Records special notes, research links, URLs, structured data, code snippets, or reference material "
        "directly into the user's dedicated Intel & Notes Terminal. ALWAYS call this tool whenever providing "
        "links/URLs, detailed reference data, checklists, or saved notes instead of dumping them into the main chat, "
        "keeping the user's activity stream completely clean."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "add | list | clear. Defaults to 'add'."
            },
            "title": {
                "type": "STRING",
                "description": "Short descriptive title for the note, link, or data entry."
            },
            "content": {
                "type": "STRING",
                "description": "The note text, URL link (https://...), code snippet, or formatted data."
            },
            "note_type": {
                "type": "STRING",
                "description": "note | link | data | code. If omitted, auto-detected from content."
            }
        },
        "required": [
            "content"
        ]
    },
    "handler": intel_notes,
}
