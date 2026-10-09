"""
core/integrations/alexa/state.py — Connection status and state management for Alexa integration.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum
from typing import Callable, List, Optional


class AlexaConnectionStatus(Enum):
    NOT_CONFIGURED = "not_configured"
    READY_TO_LINK = "ready_to_link"
    LINK_PENDING = "link_pending"
    CONNECTED = "connected"
    OFFLINE = "offline"
    ERROR = "error"


@dataclass(frozen=True)
class AlexaSnapshot:
    """
    Client-visible state snapshot.
    GUARANTEE: Contains NO tokens, endpoint query parameters, user IDs, Echo names,
    utterances, or account names.
    """
    status: AlexaConnectionStatus
    configured: bool
    linked: bool
    relay_connected: bool
    last_request_ok: bool
    allowed_intent_count: int


class AlexaStateManager:
    """Thread-safe state manager for Alexa connection lifecycle."""

    def __init__(
        self,
        initial_status: AlexaConnectionStatus = AlexaConnectionStatus.NOT_CONFIGURED,
        configured: bool = False,
        linked: bool = False,
        relay_connected: bool = False,
        allowed_intent_count: int = 0,
    ) -> None:
        self._lock = threading.RLock()
        self._status = initial_status
        self._configured = configured
        self._linked = linked
        self._relay_connected = relay_connected
        self._last_request_ok = True
        self._allowed_intent_count = allowed_intent_count
        self._listeners: List[Callable[[AlexaSnapshot], None]] = []

    def get_snapshot(self) -> AlexaSnapshot:
        with self._lock:
            return AlexaSnapshot(
                status=self._status,
                configured=self._configured,
                linked=self._linked,
                relay_connected=self._relay_connected,
                last_request_ok=self._last_request_ok,
                allowed_intent_count=self._allowed_intent_count,
            )

    def add_listener(self, callback: Callable[[AlexaSnapshot], None]) -> None:
        with self._lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[AlexaSnapshot], None]) -> None:
        with self._lock:
            if callback in self._listeners:
                self._listeners.remove(callback)

    def _notify(self) -> None:
        snap = self.get_snapshot()
        for listener in list(self._listeners):
            try:
                listener(snap)
            except Exception:
                pass

    def set_configured(self, configured: bool) -> None:
        with self._lock:
            self._configured = configured
            if not configured:
                self._status = AlexaConnectionStatus.NOT_CONFIGURED
                self._linked = False
                self._relay_connected = False
            elif self._status == AlexaConnectionStatus.NOT_CONFIGURED:
                self._status = AlexaConnectionStatus.READY_TO_LINK
        self._notify()

    def set_linking_pending(self) -> None:
        with self._lock:
            if self._configured:
                self._status = AlexaConnectionStatus.LINK_PENDING
        self._notify()

    def set_linked(self, linked: bool) -> None:
        with self._lock:
            self._linked = linked
            if linked:
                if self._relay_connected:
                    self._status = AlexaConnectionStatus.CONNECTED
                else:
                    self._status = AlexaConnectionStatus.OFFLINE
            else:
                self._status = AlexaConnectionStatus.READY_TO_LINK if self._configured else AlexaConnectionStatus.NOT_CONFIGURED
        self._notify()

    def set_relay_connected(self, connected: bool) -> None:
        with self._lock:
            self._relay_connected = connected
            if connected and self._linked:
                self._status = AlexaConnectionStatus.CONNECTED
            elif not connected and self._linked:
                self._status = AlexaConnectionStatus.OFFLINE
            elif not self._configured:
                self._status = AlexaConnectionStatus.NOT_CONFIGURED
            else:
                self._status = AlexaConnectionStatus.READY_TO_LINK
        self._notify()

    def set_error(self) -> None:
        with self._lock:
            self._status = AlexaConnectionStatus.ERROR
            self._last_request_ok = False
        self._notify()

    def record_request_result(self, success: bool) -> None:
        with self._lock:
            self._last_request_ok = success
        self._notify()

    def set_allowed_intent_count(self, count: int) -> None:
        with self._lock:
            self._allowed_intent_count = max(0, count)
        self._notify()

    def reset(self) -> None:
        with self._lock:
            self._status = AlexaConnectionStatus.NOT_CONFIGURED
            self._configured = False
            self._linked = False
            self._relay_connected = False
            self._last_request_ok = True
        self._notify()
