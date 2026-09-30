"""Shared plumbing for the mac_* actions."""
from __future__ import annotations

import functools
import json
import traceback

from core.mac.osa import OSAError


def result(obj) -> str:
    return obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, default=str)


def tool(fn):
    """Turn exceptions into a sentence the assistant can relay instead of a stack trace."""
    @functools.wraps(fn)
    def wrapper(parameters=None, **kwargs):
        try:
            return result(fn(parameters or {}, **kwargs))
        except OSAError as e:
            return f"Couldn't do that: {e}"
        except Exception as e:
            traceback.print_exc()
            return f"Couldn't do that: {type(e).__name__}: {e}"
    return wrapper


def needs_confirm(preview: str) -> str:
    return (f"CONFIRMATION NEEDED — nothing has been done yet. Read this back to the user: {preview} "
            "Only if they clearly agree, call this tool again with the same arguments plus confirm=true.")


def S(desc: str, enum: list[str] | None = None) -> dict:
    d = {"type": "STRING", "description": desc}
    if enum:
        d["enum"] = enum
    return d


def N(desc: str) -> dict:
    return {"type": "NUMBER", "description": desc}


def B(desc: str) -> dict:
    return {"type": "BOOLEAN", "description": desc}
