"""
actions/clipboard_manager.py — Persistent, Semantically Indexed Clipboard History for ALFRED.

Features:
1. Background listener monitoring system clipboard changes (via pyperclip / win32).
2. Rolling history stack (max 50 items) stored in memory/clipboard_history.json.
3. Fast sentence embeddings using local fastembed with metadata tagging (type, timestamp, source app).
4. Password manager scrubbing: ignores items from 1Password, Bitwarden, KeePass, and high-entropy secret patterns.
5. Synthesis and retrieval tools:
   - get_recent_clipboards(count=3)
   - search_clipboard(query)
   - paste_clipboard_item(index_or_id)
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import logging
import math
import os
import platform
import re
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import pyperclip
    _PYPERCLIP_OK = True
except ImportError:
    pyperclip = None
    _PYPERCLIP_OK = False

# Lazy-load fastembed inside _get_embedding_model to avoid startup delay
TextEmbedding = None
_FASTEMBED_OK = None

_RED = "\033[91m"
_RESET = "\033[0m"
_OS = platform.system()

BASE_DIR = Path(__file__).resolve().parent.parent
HISTORY_FILE = BASE_DIR / "memory" / "clipboard_history.json"
MAX_HISTORY_ITEMS = 50

# Sensitive process and title markers to scrub
_PASSWORD_APP_PATTERNS = {
    "1password", "bitwarden", "keepass", "lastpass", "dashlane",
    "nordpass", "authenticator", "keychain", "roboform", "enpass"
}

# Known secret token prefixes
_SECRET_PATTERNS = [
    re.compile(r"^ghp_[A-Za-z0-9_]{36}"),                # GitHub PAT
    re.compile(r"^gho_[A-Za-z0-9_]{36}"),                # GitHub OAuth
    re.compile(r"^sk-[A-Za-z0-9_]{32,}"),                # OpenAI/Anthropic API Key
    re.compile(r"^AIzaSy[A-Za-z0-9_\-]{33}"),            # Google API Key
    re.compile(r"^xox[baprs]-[A-Za-z0-9_\-]{10,}"),      # Slack Token
    re.compile(r"-----BEGIN (RSA|EC|OPENSSH|DSA|PGP)? PRIVATE KEY-----"), # Private keys
]


def _get_active_window_info() -> Tuple[str, str]:
    """Return (process_name, window_title) of the foreground window."""
    if _OS != "Windows":
        return "desktop", ""
    try:
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return "unknown", ""

        # Window title
        length = user32.GetWindowTextLengthW(hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buff, length + 1)
        title = buff.value

        # Process name
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        import psutil
        proc = psutil.Process(pid.value)
        return proc.name().lower(), title
    except Exception:
        return "unknown", ""


def is_sensitive_content(text: str, source_proc: str = "", source_title: str = "") -> bool:
    """Detect if content originates from a password manager or contains high-entropy secrets."""
    if not text:
        return True

    # 1. Check window process or title
    proc_low = source_proc.lower()
    title_low = source_title.lower()
    for app in _PASSWORD_APP_PATTERNS:
        if app in proc_low or app in title_low:
            return True

    # 2. Check secret token regexes
    for pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            return True

    # 3. High-entropy single-word password heuristic
    stripped = text.strip()
    if 10 <= len(stripped) <= 64 and " " not in stripped and "\n" not in stripped:
        has_upper = any(c.isupper() for c in stripped)
        has_lower = any(c.islower() for c in stripped)
        has_digit = any(c.isdigit() for c in stripped)
        has_punct = any(not c.isalnum() for c in stripped)
        categories = sum([has_upper, has_lower, has_digit, has_punct])
        unique_ratio = len(set(stripped)) / len(stripped)
        if categories >= 3 and unique_ratio > 0.65:
            return True

    return False


def classify_content_type(text: str) -> str:
    """Determine category: url, email, json, code, or text."""
    s = text.strip()
    if re.match(r"^https?://[^\s]+$", s):
        return "url"
    if re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", s):
        return "email"
    if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
        try:
            json.loads(s)
            return "json"
        except Exception:
            pass
    code_indicators = ["def ", "class ", "import ", "function ", "const ", "let ", "var ", "SELECT ", "CREATE TABLE"]
    if any(ind in s for ind in code_indicators) or (s.count(";") > 2 and "{" in s):
        return "code"
    return "text"


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


class ClipboardManager:
    """Thread-safe persistent clipboard manager with semantic indexing."""

    _instance: Optional[ClipboardManager] = None
    _lock = threading.Lock()

    def __init__(self):
        self._history: List[Dict[str, Any]] = []
        self._listener_thread: Optional[threading.Thread] = None
        self._running = False
        self._last_raw: str = ""
        self._embedding_model: Any = None
        self._load_history()

    @classmethod
    def get_instance(cls) -> ClipboardManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _get_embedding_model(self) -> Any:
        """Lazily initialize local fastembed model."""
        global _FASTEMBED_OK, TextEmbedding
        if self._embedding_model is None and _FASTEMBED_OK is not False:
            try:
                if TextEmbedding is None:
                    from fastembed import TextEmbedding as _TE
                    TextEmbedding = _TE
                self._embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
                _FASTEMBED_OK = True
            except Exception as e:
                print(f"{_RED}[clipboard]{_RESET} FastEmbed init notice: {e}")
                self._embedding_model = False
                _FASTEMBED_OK = False
        return self._embedding_model if self._embedding_model is not False else None

    def _compute_embedding(self, text: str) -> Optional[List[float]]:
        """Compute 384-dimensional vector embedding for text."""
        model = self._get_embedding_model()
        if not model or not text:
            return None
        try:
            # First 500 characters provide clean semantic representation
            snippet = text[:500]
            emb = list(model.embed([snippet]))[0]
            return [round(float(x), 5) for x in emb]
        except Exception:
            return None

    def _load_history(self) -> None:
        """Load history from disk."""
        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self._history = data[:MAX_HISTORY_ITEMS]
            except Exception:
                self._history = []

    def _save_history(self) -> None:
        """Save history to disk atomically."""
        try:
            HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            temp_file = HISTORY_FILE.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self._history, f, indent=2, ensure_ascii=False)
            temp_file.replace(HISTORY_FILE)
        except Exception as e:
            print(f"{_RED}[clipboard]{_RESET} Error saving clipboard history: {e}")

    def add_clipboard_item(self, text: str, source_app: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Append item to history stack with deduplication and sensitive data filtering."""
        clean_text = text.strip() if text else ""
        if not clean_text:
            return None

        proc_name, win_title = _get_active_window_info()
        source = source_app or proc_name or "desktop"

        if is_sensitive_content(clean_text, proc_name, win_title):
            print(f"{_RED}[clipboard]{_RESET} Sensitive password/token scrubbed and ignored.")
            return None

        with self._lock:
            # Deduplicate against top item
            if self._history and self._history[0].get("text") == clean_text:
                return self._history[0]

            # Generate item metadata
            now = datetime.now()
            h_suffix = hashlib.md5(clean_text.encode("utf-8")).hexdigest()[:6]
            item_id = f"clip_{now.strftime('%Y%m%d_%H%M%S')}_{h_suffix}"

            item: Dict[str, Any] = {
                "id": item_id,
                "text": clean_text,
                "preview": clean_text[:80] + ("..." if len(clean_text) > 80 else ""),
                "type": classify_content_type(clean_text),
                "timestamp": now.isoformat(),
                "char_count": len(clean_text),
                "word_count": len(clean_text.split()),
                "source_app": source,
                "embedding": self._compute_embedding(clean_text),
            }

            # Insert at head (most recent first)
            self._history.insert(0, item)
            if len(self._history) > MAX_HISTORY_ITEMS:
                self._history = self._history[:MAX_HISTORY_ITEMS]

            self._save_history()
            return item

    def get_recent_clipboards(self, count: int = 3) -> List[Dict[str, Any]]:
        """Return the most recent count items in chronological order (oldest to newest among the recent set)."""
        with self._lock:
            n = max(1, min(count, len(self._history)))
            recent_items = self._history[:n]
            # Return in chronological order (earliest to most recent)
            return list(reversed(recent_items))

    def search_clipboard(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Perform semantic and keyword search across clipboard history."""
        clean_q = query.lower().strip()
        if not clean_q:
            return []

        q_emb = self._compute_embedding(query)
        scored: List[Tuple[float, Dict[str, Any]]] = []

        with self._lock:
            for item in self._history:
                text = item.get("text", "")
                text_low = text.lower()

                # Lexical scoring
                lexical_score = 0.0
                if clean_q == text_low:
                    lexical_score = 1.0
                elif clean_q in text_low:
                    lexical_score = max(0.6, len(clean_q) / max(len(text_low), 1))
                else:
                    q_words = set(re.findall(r"\w+", clean_q))
                    t_words = set(re.findall(r"\w+", text_low))
                    if q_words and t_words:
                        overlap = len(q_words & t_words) / len(q_words)
                        lexical_score = overlap * 0.5

                # Semantic scoring
                semantic_score = 0.0
                if q_emb and item.get("embedding"):
                    semantic_score = max(0.0, cosine_similarity(q_emb, item["embedding"]))

                # Combined hybrid score
                if q_emb and item.get("embedding"):
                    final_score = (semantic_score * 0.6) + (lexical_score * 0.4)
                else:
                    final_score = lexical_score

                if final_score > 0.15:
                    item_copy = dict(item)
                    item_copy.pop("embedding", None)
                    item_copy["search_score"] = round(final_score, 3)
                    scored.append((final_score, item_copy))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:limit]]

    def paste_clipboard_item(self, index_or_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        """Push historical item to system clipboard active paste slot."""
        with self._lock:
            if not self._history:
                return None

            selected: Optional[Dict[str, Any]] = None

            # 1. Match by integer index (1-based relative index, where 1 is newest)
            try:
                idx = int(index_or_id)
                if 1 <= idx <= len(self._history):
                    selected = self._history[idx - 1]
            except (ValueError, TypeError):
                pass

            # 2. Match by ID or text search if not matched by integer
            if selected is None:
                target_str = str(index_or_id).strip()
                for item in self._history:
                    if item.get("id") == target_str or target_str in item.get("text", ""):
                        selected = item
                        break

            if selected is not None:
                text = selected.get("text", "")
                if _PYPERCLIP_OK:
                    pyperclip.copy(text)
                return selected

        return None

    def start_listener(self) -> None:
        """Start background daemon thread monitoring OS clipboard."""
        if self._listener_thread and self._listener_thread.is_alive():
            return
        self._running = True
        self._listener_thread = threading.Thread(target=self._listener_loop, daemon=True, name="ClipboardListener")
        self._listener_thread.start()

    def stop_listener(self) -> None:
        """Stop background clipboard listener."""
        self._running = False

    def _listener_loop(self) -> None:
        """Polling loop inspecting OS clipboard."""
        while self._running:
            try:
                if _PYPERCLIP_OK:
                    current_clip = pyperclip.paste()
                    if current_clip and current_clip != self._last_raw:
                        self._last_raw = current_clip
                        self.add_clipboard_item(current_clip)
            except Exception:
                pass
            time.sleep(0.5)


# Global module functions for direct access
def get_recent_clipboards(count: int = 3) -> List[Dict[str, Any]]:
    return ClipboardManager.get_instance().get_recent_clipboards(count)


def search_clipboard(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    return ClipboardManager.get_instance().search_clipboard(query, limit)


def paste_clipboard_item(index_or_id: Union[int, str]) -> Optional[Dict[str, Any]]:
    return ClipboardManager.get_instance().paste_clipboard_item(index_or_id)


def add_clipboard_item(text: str, source_app: Optional[str] = None) -> Optional[Dict[str, Any]]:
    return ClipboardManager.get_instance().add_clipboard_item(text, source_app)


def start_clipboard_listener() -> None:
    ClipboardManager.get_instance().start_listener()


def stop_clipboard_listener() -> None:
    ClipboardManager.get_instance().stop_listener()


# ── Action Handler for ALFRED ────────────────────────────────────────────────
def clipboard_manager_action(parameters: dict, player=None, speak=None, **kwargs) -> str:
    """Action handler called by ALFRED action dispatcher."""
    action = str(parameters.get("action", "recent")).lower().strip()
    mgr = ClipboardManager.get_instance()

    if action in ("recent", "get_recent", "list"):
        count = int(parameters.get("count", 3))
        items = mgr.get_recent_clipboards(count)
        if not items:
            return "Clipboard history is currently empty."
        lines = [f"Recent Clipboard Items ({len(items)}):"]
        for idx, item in enumerate(items, 1):
            ts = item.get("timestamp", "").split("T")[-1][:5]
            lines.append(f"{idx}. [{item.get('type', 'text')}] ({ts}) {item.get('preview', '')}")
        return "\n".join(lines)

    elif action in ("search", "find"):
        query = parameters.get("query") or parameters.get("text") or ""
        if not query:
            return "Please provide a 'query' to search clipboard history."
        results = mgr.search_clipboard(query, limit=int(parameters.get("count", 5)))
        if not results:
            return f"No clipboard entries matched '{query}'."
        lines = [f"Found {len(results)} clipboard matches for '{query}':"]
        for idx, item in enumerate(results, 1):
            score = item.get("search_score", 0.0)
            lines.append(f"{idx}. [Score: {score:.2f}] {item.get('preview', '')}")
        return "\n".join(lines)

    elif action in ("paste", "select", "restore"):
        target = parameters.get("index") or parameters.get("id") or parameters.get("target") or 1
        item = mgr.paste_clipboard_item(target)
        if not item:
            return f"Could not find clipboard item '{target}'."
        if parameters.get("auto_paste"):
            try:
                import pyautogui
                pyautogui.hotkey("ctrl", "v")
            except Exception:
                pass
        return f"Active clipboard restored to: '{item.get('preview', '')}'"

    elif action in ("copy", "add"):
        text = parameters.get("text", "")
        if not text:
            return "Please provide 'text' to copy."
        if _PYPERCLIP_OK:
            pyperclip.copy(text)
        item = mgr.add_clipboard_item(text)
        if item:
            return f"Copied and indexed: '{item.get('preview', '')}'"
        return "Content was scrubbed or empty."

    return f"Unknown clipboard_manager action: '{action}'"


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "clipboard_manager",
    "description": (
        "Persistent, semantically indexed clipboard history with voice search and restoration. "
        "Allows viewing recent clips, searching historical copied text by keywords/meaning, "
        "and restoring prior clipboard entries to the active paste slot."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "recent | search | paste | copy"
            },
            "count": {
                "type": "INTEGER",
                "description": "Number of recent items to return (default: 3)"
            },
            "query": {
                "type": "STRING",
                "description": "Keyword or concept to search for in clipboard history"
            },
            "index": {
                "type": "STRING",
                "description": "1-based relative index (1=most recent) or item ID to push to active clipboard"
            },
            "text": {
                "type": "STRING",
                "description": "Text content for copy action"
            },
            "auto_paste": {
                "type": "BOOLEAN",
                "description": "Whether to automatically trigger Ctrl+V paste after restoring item (default: false)"
            }
        },
        "required": ["action"]
    },
    "handler": clipboard_manager_action,
}
