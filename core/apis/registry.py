"""
core/apis/registry.py — API Backend Registry & Format Validators.

Registers and validates credentials for:
1. Google Workspace (Client ID, Client Secret, Redirect URI)
2. Spotify (Client ID, Client Secret)
3. Gmail API (Simple API Key or OAuth credentials JSON)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from core.secrets.store import SecretStore, get_secret_store


@dataclass(frozen=True)
class APIBackend:
    """Definition and schema for a supported API backend."""
    id: str
    name: str
    icon: str
    description: str
    required_fields: tuple[str, ...]
    optional_fields: tuple[str, ...] = ()
    validator_fn: Optional[Callable[[dict[str, str]], tuple[bool, str]]] = None


# ── Validators ───────────────────────────────────────────────────────────────

def _validate_google_workspace(fields: dict[str, str]) -> tuple[bool, str]:
    """Validate Google Workspace Client ID and Secret format."""
    cid = fields.get("client_id", "").strip()
    csecret = fields.get("client_secret", "").strip()

    if not cid:
        return False, "Google Client ID is required."
    # Google OAuth client IDs typically end with '.apps.googleusercontent.com'
    if not (cid.endswith(".apps.googleusercontent.com") or len(cid) >= 20):
        return False, "Invalid Google Client ID format (must end with .apps.googleusercontent.com or be >=20 chars)."

    if not csecret:
        return False, "Google Client Secret is required."
    if len(csecret) < 12:
        return False, "Google Client Secret must be at least 12 characters."

    return True, ""


def _validate_spotify(fields: dict[str, str]) -> tuple[bool, str]:
    """Validate Spotify 32-character hexadecimal / alphanumeric Client ID and Secret."""
    cid = fields.get("client_id", "").strip()
    csecret = fields.get("client_secret", "").strip()

    if not cid:
        return False, "Spotify Client ID is required."
    if not re.match(r"^[a-zA-Z0-9]{32}$", cid):
        return False, "Spotify Client ID must be exactly 32 alphanumeric characters."

    if not csecret:
        return False, "Spotify Client Secret is required."
    if not re.match(r"^[a-zA-Z0-9]{32}$", csecret):
        return False, "Spotify Client Secret must be exactly 32 alphanumeric characters."

    return True, ""


def _validate_gmail(fields: dict[str, str]) -> tuple[bool, str]:
    """Validate Gmail API Key or credentials.json payload."""
    mode = fields.get("auth_mode", "api_key").lower()
    if mode == "oauth_json":
        raw_json = fields.get("credentials_json", "").strip()
        if not raw_json:
            return False, "credentials.json content is required for OAuth mode."
        try:
            parsed = json.loads(raw_json)
            # Must have 'installed' or 'web' client config
            if "installed" not in parsed and "web" not in parsed:
                return False, "Invalid credentials.json: missing 'installed' or 'web' client root key."
            client_block = parsed.get("installed") or parsed.get("web", {})
            if "client_id" not in client_block or "client_secret" not in client_block:
                return False, "Invalid credentials.json: missing client_id or client_secret inside client block."
        except json.JSONDecodeError as exc:
            return False, f"Invalid credentials.json syntax: {exc}"
        return True, ""
    else:
        # Simple API Key / App Password mode
        user_email = fields.get("email", "").strip()
        app_pw = fields.get("app_password", "").strip()
        if not user_email:
            return False, "Gmail address is required."
        if not re.match(r"^[^@]+@[^@]+\.[^@]+$", user_email):
            return False, "Invalid Gmail address format."
        if not app_pw:
            return False, "Gmail 16-character App Password is required."
        clean_pw = app_pw.replace(" ", "").strip()
        if len(clean_pw) < 8:
            return False, "Gmail App Password must be at least 8 characters (standard Google App Passwords are 16 chars)."
        return True, ""


# ── Registry Definition ───────────────────────────────────────────────────────

_BACKENDS: dict[str, APIBackend] = {
    "google_workspace": APIBackend(
        id="google_workspace",
        name="Google Workspace",
        icon="🌐",
        description="Connect Google Calendar, Drive, and Workspace Docs via OAuth2 credentials.",
        required_fields=("client_id", "client_secret"),
        optional_fields=("redirect_uri",),
        validator_fn=_validate_google_workspace,
    ),
    "spotify": APIBackend(
        id="spotify",
        name="Spotify API",
        icon="🎵",
        description="Spotify Web API for playback control, track search, playlists, and device streaming.",
        required_fields=("client_id", "client_secret"),
        optional_fields=("redirect_uri",),
        validator_fn=_validate_spotify,
    ),
    "gmail": APIBackend(
        id="gmail",
        name="Gmail API",
        icon="✉",
        description="Read inbox summaries, search threads, and compose tactical emails securely.",
        required_fields=("email", "app_password"),
        optional_fields=("credentials_json", "auth_mode"),
        validator_fn=_validate_gmail,
    ),
}


def get_api_registry() -> dict[str, APIBackend]:
    """Return dict of all registered APIBackends."""
    return dict(_BACKENDS)


def get_backend(backend_id: str) -> Optional[APIBackend]:
    """Retrieve an APIBackend by id."""
    return _BACKENDS.get(str(backend_id or "").strip().lower())


def validate_backend_fields(backend_id: str, fields: dict[str, str]) -> tuple[bool, str]:
    """Run format validation against given backend fields."""
    backend = get_backend(backend_id)
    if not backend:
        return False, f"Unknown API backend: '{backend_id}'"
    if backend.validator_fn is None:
        return True, ""
    return backend.validator_fn(fields)


def save_backend_credentials(backend_id: str, fields: dict[str, str], store: Optional[SecretStore] = None) -> tuple[bool, str]:
    """Validate and store backend credentials in the encrypted secret store."""
    valid, err = validate_backend_fields(backend_id, fields)
    if not valid:
        return False, err

    import core.secrets.store
    st = store or core.secrets.store.get_secret_store()
    prefix = str(backend_id).strip().lower()

    for k, v in fields.items():
        clean_val = str(v or "").strip()
        if clean_val:
            st.set(f"{prefix}.{k}", clean_val)
        else:
            st.delete(f"{prefix}.{k}")

    return True, "Credentials validated and saved successfully."


def get_configured_backends_count(store: Optional[SecretStore] = None) -> tuple[int, int]:
    """Return (configured_count, total_backends_count)."""
    import core.secrets.store
    st = store or core.secrets.store.get_secret_store()
    configured = 0
    total = len(_BACKENDS)

    for backend_id, b in _BACKENDS.items():
        # Check if all required fields exist
        all_present = True
        if backend_id == "gmail":
            # Either email+app_password or credentials_json
            has_pw = st.has("gmail.email") and st.has("gmail.app_password")
            has_oauth = st.has("gmail.credentials_json")
            if has_pw or has_oauth:
                configured += 1
            continue

        for req in b.required_fields:
            if not st.has(f"{backend_id}.{req}"):
                all_present = False
                break
        if all_present:
            configured += 1

    return configured, total
