"""Answer Window: Opens a temporary mic window for one-shot answers without wake word."""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Callable, Coroutine

# ── Named Constants ──────────────────────────────────────────────────────────
ANSWER_WINDOW_S: float = 8.0
ANSWER_POLL_INTERVAL_S: float = 0.1
DEFAULT_PROMPT: str = "What shall I keep an eye on, sir?"

_LOGGER = logging.getLogger(__name__)


class AnswerWindow:
    """Coordinates one-shot spoken user responses without wake-word requirements."""

    def __init__(
        self,
        speak_fn: Callable[[str], None] | None = None,
        un_gate_fn: Callable[[bool], None] | None = None,
    ) -> None:
        self._speak_fn = speak_fn
        self._un_gate_fn = un_gate_fn
        self._lock = threading.Lock()
        self._active = False
        self._pending_future: asyncio.Future[str] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def is_active(self) -> bool:
        with self._lock:
            return self._active

    def set_callbacks(
        self,
        speak_fn: Callable[[str], None],
        un_gate_fn: Callable[[bool], None],
    ) -> None:
        """Register host application callbacks."""
        with self._lock:
            self._speak_fn = speak_fn
            self._un_gate_fn = un_gate_fn

    async def request_answer(
        self,
        prompt_speech: str = DEFAULT_PROMPT,
        timeout_s: float = ANSWER_WINDOW_S,
    ) -> str:
        """Speak prompt and await one user reply without requiring a wake word."""
        self._loop = asyncio.get_running_loop()
        future: asyncio.Future[str] = self._loop.create_future()

        with self._lock:
            if self._active and self._pending_future and not self._pending_future.done():
                self._pending_future.cancel()
            self._active = True
            self._pending_future = future
            un_gate = self._un_gate_fn
            speak = self._speak_fn

        # 1. Open gate in audio stream
        if un_gate is not None:
            try:
                un_gate(True)
            except Exception as exc:
                _LOGGER.warning("Could not un-gate mic for answer window: %s", exc)

        # 2. Speak the prompt
        if speak is not None and prompt_speech:
            try:
                speak(prompt_speech)
            except Exception as exc:
                _LOGGER.warning("Could not speak answer window prompt: %s", exc)

        # 3. Wait for user response or timeout
        answer = ""
        try:
            answer = await asyncio.wait_for(future, timeout=max(1.0, timeout_s))
        except asyncio.TimeoutError:
            _LOGGER.debug("Answer window timed out after %.1fs", timeout_s)
            answer = ""
        except asyncio.CancelledError:
            _LOGGER.debug("Answer window cancelled")
            answer = ""
        finally:
            self._close_window()

        return (answer or "").strip()

    def submit_answer(self, text: str) -> bool:
        """Submit captured speech/text into the waiting window.

        Thread-safe; can be called from STT callbacks or UI chat input.
        """
        cleaned = (text or "").strip()
        if not cleaned:
            return False

        with self._lock:
            if not self._active or self._pending_future is None:
                return False
            fut = self._pending_future
            loop = self._loop

        if fut is not None and not fut.done() and loop is not None:
            loop.call_soon_threadsafe(lambda: not fut.done() and fut.set_result(cleaned))
            return True
        return False

    def cancel(self) -> None:
        """Cancel an active answer window immediately."""
        self._close_window()

    def _close_window(self) -> None:
        with self._lock:
            if not self._active:
                return
            self._active = False
            un_gate = self._un_gate_fn
            fut = self._pending_future
            self._pending_future = None

        if un_gate is not None:
            try:
                un_gate(False)
            except Exception as exc:
                _LOGGER.debug("Error restoring mic gate: %s", exc)

        if fut is not None and not fut.done():
            fut.cancel()
