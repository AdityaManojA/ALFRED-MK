"""
core/apis/oauth.py — Google Workspace & Gmail Local Loopback OAuth Helper.

Spawns a temporary local loopback redirect server (http://localhost:8888),
opens the browser for Google consent, receives authorization code,
exchanges for access & refresh tokens, and stores them in SecretStore.
"""
from __future__ import annotations

import http.server
import json
import logging
import socket
import threading
import time
import urllib.parse
import webbrowser
from enum import Enum
from typing import Callable, Optional, Tuple

try:
    import requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False

from core.secrets.store import SecretStore, get_secret_store

logger = logging.getLogger("core.apis.oauth")

# ── Named Constants ──────────────────────────────────────────────────────────
OAUTH_LOCAL_PORT: int = 8888
OAUTH_TIMEOUT_S: float = 120.0
GOOGLE_AUTH_URL: str = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL: str = "https://oauth2.googleapis.com/token"

DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


class OAuthError(Enum):
    NONE = "none"
    TIMEOUT = "timeout"
    USER_DENIED = "user_denied"
    NETWORK = "network"
    PORT_IN_USE = "port_in_use"
    CONFIG = "invalid_config"


class _OAuthRedirectHandler(http.server.BaseHTTPRequestHandler):
    """Temporary HTTP handler to capture redirect authorization code."""
    auth_code: Optional[str] = None
    error: Optional[str] = None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            _OAuthRedirectHandler.auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
                <html>
                <body style="font-family: monospace; background: #090a12; color: #4ef2bb; padding: 40px; text-align: center;">
                    <h2>&#x25C8; ALFRED-MK-IX // AUTHENTICATION SUCCESSFUL</h2>
                    <p style="color: #8e9bff;">Authorization code received. You may now close this browser tab.</p>
                </body>
                </html>
            """)
        elif "error" in params:
            _OAuthRedirectHandler.error = params["error"][0]
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
                <html>
                <body style="font-family: monospace; background: #090a12; color: #ff2a55; padding: 40px; text-align: center;">
                    <h2>&#x25C8; AUTHENTICATION CANCELLED // ERROR</h2>
                    <p>Authorization was denied or failed.</p>
                </body>
                </html>
            """)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Silence local server logs
        pass


class GoogleOAuthFlow:
    """
    Executes an interactive loopback OAuth authorization flow.
    """
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str = f"http://localhost:{OAUTH_LOCAL_PORT}",
        scopes: Optional[list[str]] = None,
        store: Optional[SecretStore] = None,
    ):
        self.client_id = client_id.strip()
        self.client_secret = client_secret.strip()
        self.redirect_uri = redirect_uri.strip()
        self.scopes = scopes or DEFAULT_SCOPES
        self.store = store or get_secret_store()

    def execute(self, timeout_s: float = OAUTH_TIMEOUT_S) -> tuple[bool, OAuthError, str]:
        """
        Runs the full browser-based loopback OAuth exchange.
        Returns (success: bool, error_type: OAuthError, message: str).
        """
        if not self.client_id or not self.client_secret:
            return False, OAuthError.CONFIG, "Missing Client ID or Client Secret"

        _OAuthRedirectHandler.auth_code = None
        _OAuthRedirectHandler.error = None

        # 1. Start local loopback HTTP server
        try:
            server = http.server.HTTPServer(("localhost", OAUTH_LOCAL_PORT), _OAuthRedirectHandler)
            server.timeout = 1.0
        except OSError:
            return False, OAuthError.PORT_IN_USE, f"Port {OAUTH_LOCAL_PORT} is in use"

        # 2. Build consent URL and open browser
        scope_str = " ".join(self.scopes)
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": scope_str,
            "access_type": "offline",
            "prompt": "consent",
        }
        auth_url = f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"

        try:
            webbrowser.open(auth_url)
        except Exception as exc:
            server.server_close()
            return False, OAuthError.NETWORK, f"Failed to open browser: {exc}"

        # 3. Wait for redirect
        start_t = time.time()
        auth_code = None

        while (time.time() - start_t) < timeout_s:
            server.handle_request()
            if _OAuthRedirectHandler.auth_code:
                auth_code = _OAuthRedirectHandler.auth_code
                break
            if _OAuthRedirectHandler.error:
                server.server_close()
                return False, OAuthError.USER_DENIED, f"User denied consent: {_OAuthRedirectHandler.error}"

        server.server_close()

        if not auth_code:
            return False, OAuthError.TIMEOUT, "OAuth authorization timed out (no response received)"

        # 4. Exchange authorization code for tokens
        if not _REQUESTS_AVAILABLE:
            return False, OAuthError.NETWORK, "requests library not available"

        try:
            token_payload = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": auth_code,
                "grant_type": "authorization_code",
                "redirect_uri": self.redirect_uri,
            }
            resp = requests.post(GOOGLE_TOKEN_URL, data=token_payload, timeout=15.0)
            if resp.status_code != 200:
                return False, OAuthError.NETWORK, f"Token exchange failed: HTTP {resp.status_code}"

            token_data = resp.json()
            access_token = token_data.get("access_token", "")
            refresh_token = token_data.get("refresh_token", "")

            # Persist in secret store
            if refresh_token:
                self.store.set("google_workspace.refresh_token", refresh_token)
            if access_token:
                self.store.set("google_workspace.access_token", access_token)
                self.store.set("google_workspace.token_saved_at", str(time.time()))

            return True, OAuthError.NONE, "Google Workspace successfully authenticated."

        except Exception as exc:
            return False, OAuthError.NETWORK, f"Token exchange network error: {exc}"
