"""
core/integrations/alexa/config.py — Configuration & Named Constants for Alexa Integration.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# ── Named Timing & Limit Constants ──────────────────────────────────────────
ALEXA_RELAY_CONNECT_TIMEOUT_S: float = 10.0
ALEXA_RECONNECT_BASE_S: float = 1.0
ALEXA_RECONNECT_MAX_S: float = 30.0
ALEXA_REQUEST_MAX_AGE_S: float = 150.0
ALEXA_COMMAND_TIMEOUT_S: float = 8.0
ALEXA_MAX_RESPONSE_CHARS: int = 700
ALEXA_CLOCK_SKEW_S: float = 30.0
ALEXA_STATE_TOKEN_TTL_S: float = 300.0  # 5 minutes for account-link token


@dataclass(frozen=True)
class AlexaConfig:
    """Developer and endpoint configuration for Alexa Skill relay."""
    skill_id: str = ""
    skill_store_url: str = ""
    relay_https_url: str = ""
    relay_ws_url: str = ""
    oauth_client_id: str = ""
    oauth_client_secret: str = ""
    oauth_redirect_url: str = ""
    vendor_id: str = ""

    def is_configured(self) -> bool:
        """Return True if minimum relay & skill parameters are set."""
        return bool(self.skill_id and (self.relay_https_url or self.relay_ws_url))


def load_alexa_config_from_store(store=None) -> AlexaConfig:
    """Load Alexa configuration from encrypted SecretStore."""
    if store is None:
        from core.secrets.store import get_secret_store
        store = get_secret_store()

    return AlexaConfig(
        skill_id=store.get("alexa.skill_id") or "",
        skill_store_url=store.get("alexa.skill_store_url") or "",
        relay_https_url=store.get("alexa.relay_https_url") or "",
        relay_ws_url=store.get("alexa.relay_ws_url") or "",
        oauth_client_id=store.get("alexa.oauth_client_id") or "",
        oauth_client_secret=store.get("alexa.oauth_client_secret") or "",
        oauth_redirect_url=store.get("alexa.oauth_redirect_url") or "",
        vendor_id=store.get("alexa.vendor_id") or "",
    )


def save_alexa_config_to_store(cfg: AlexaConfig, store=None) -> None:
    """Save Alexa configuration to encrypted SecretStore."""
    if store is None:
        from core.secrets.store import get_secret_store
        store = get_secret_store()

    entries = {
        "alexa.skill_id": cfg.skill_id,
        "alexa.skill_store_url": cfg.skill_store_url,
        "alexa.relay_https_url": cfg.relay_https_url,
        "alexa.relay_ws_url": cfg.relay_ws_url,
        "alexa.oauth_client_id": cfg.oauth_client_id,
        "alexa.oauth_client_secret": cfg.oauth_client_secret,
        "alexa.oauth_redirect_url": cfg.oauth_redirect_url,
        "alexa.vendor_id": cfg.vendor_id,
    }

    for key, val in entries.items():
        clean = (val or "").strip()
        if clean:
            store.set(key, clean)
        else:
            store.delete(key)
