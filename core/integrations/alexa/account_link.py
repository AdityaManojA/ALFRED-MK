"""
core/integrations/alexa/account_link.py — Short-lived single-use account linking token manager.
"""
from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional

from core.integrations.alexa.config import ALEXA_STATE_TOKEN_TTL_S


@dataclass(frozen=True)
class LinkingState:
    state_token: str
    created_at: float
    expires_at: float
    device_id: str


class AccountLinkingManager:
    """Manages short-lived single-use linking state tokens for Echo account pairing."""

    def __init__(self, ttl_s: float = ALEXA_STATE_TOKEN_TTL_S) -> None:
        self.ttl_s = ttl_s
        self._lock = threading.RLock()
        self._states: dict[str, LinkingState] = {}

    def create_linking_state(self, device_id: str) -> str:
        """Generate a cryptographically secure, single-use state token."""
        now = time.time()
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._purge_expired(now)
            self._states[token] = LinkingState(
                state_token=token,
                created_at=now,
                expires_at=now + self.ttl_s,
                device_id=device_id,
            )
        return token

    def consume_linking_state(self, state_token: str) -> Optional[LinkingState]:
        """
        Validate and atomically consume a linking state token.
        Returns the LinkingState if valid, or None if expired/not found/already used.
        """
        now = time.time()
        with self._lock:
            self._purge_expired(now)
            state = self._states.pop(state_token, None)
            if state is None:
                return None
            if now > state.expires_at:
                return None
            return state

    def is_state_valid(self, state_token: str) -> bool:
        """Check if a state token exists and has not expired (without consuming)."""
        now = time.time()
        with self._lock:
            state = self._states.get(state_token)
            if state is None:
                return False
            return now <= state.expires_at

    def revoke_device_states(self, device_id: str) -> int:
        """Revoke all pending states for a given device ID."""
        revoked = 0
        with self._lock:
            for token, state in list(self._states.items()):
                if state.device_id == device_id:
                    del self._states[token]
                    revoked += 1
        return revoked

    def _purge_expired(self, now: float) -> None:
        """Purge expired states from memory."""
        for token, state in list(self._states.items()):
            if now > state.expires_at:
                del self._states[token]
