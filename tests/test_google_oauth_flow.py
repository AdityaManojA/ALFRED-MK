"""
tests/test_google_oauth_flow.py — Unit tests for core/apis/oauth.py (loopback OAuth flow).

No sockets, browsers or HTTP are used: the loopback server, webbrowser.open and
requests.post are all replaced with fakes.
"""
from __future__ import annotations

import io
import json
import urllib.parse
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import core.apis.oauth as oauth
from core.apis.oauth import GoogleOAuthFlow, OAuthError, _OAuthRedirectHandler


class _FakeServer:
    """Stand-in for http.server.HTTPServer that simulates one redirect per handle_request."""

    instances: list = []

    def __init__(self, addr, handler, *, code=None, error=None):
        self.addr = addr
        self.handler = handler
        self.code = code
        self.error = error
        self.closed = False
        self.handled = 0
        _FakeServer.instances.append(self)

    def handle_request(self):
        self.handled += 1
        if self.code:
            self.handler.auth_code = self.code
        elif self.error:
            self.handler.error = self.error

    def server_close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def _reset_handler_state():
    _FakeServer.instances.clear()
    _OAuthRedirectHandler.auth_code = None
    _OAuthRedirectHandler.error = None
    yield
    _OAuthRedirectHandler.auth_code = None
    _OAuthRedirectHandler.error = None


@pytest.fixture
def isolated_file(tmp_path, monkeypatch):
    """Point the module's __file__ into tmp so config/api_keys.json is resolved there."""
    fake_file = tmp_path / "core" / "apis" / "oauth.py"
    fake_file.parent.mkdir(parents=True)
    monkeypatch.setattr(oauth, "__file__", str(fake_file))
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    return cfg_dir / "api_keys.json"


def _install_server(monkeypatch, **kwargs):
    monkeypatch.setattr(
        oauth.http.server, "HTTPServer",
        lambda addr, handler: _FakeServer(addr, handler, **kwargs),
    )


def _flow(store=None, **kw):
    return GoogleOAuthFlow("  cid  ", " secret ", store=store or MagicMock(), **kw)


def test_constructor_strips_credentials_and_defaults_scopes():
    flow = _flow()
    assert flow.client_id == "cid"
    assert flow.client_secret == "secret"
    assert flow.redirect_uri == f"http://localhost:{oauth.OAUTH_LOCAL_PORT}"
    assert flow.scopes == oauth.DEFAULT_SCOPES


def test_missing_credentials_returns_config_error(monkeypatch):
    server_factory = MagicMock()
    monkeypatch.setattr(oauth.http.server, "HTTPServer", server_factory)
    ok, err, msg = GoogleOAuthFlow("", "x", store=MagicMock()).execute()
    assert (ok, err) == (False, OAuthError.CONFIG)
    assert "Missing" in msg
    server_factory.assert_not_called()


def test_port_in_use_returns_port_error(monkeypatch):
    def boom(*_a, **_k):
        raise OSError("in use")
    monkeypatch.setattr(oauth.http.server, "HTTPServer", boom)
    ok, err, msg = _flow().execute()
    assert (ok, err) == (False, OAuthError.PORT_IN_USE)
    assert str(oauth.OAUTH_LOCAL_PORT) in msg


def test_consent_url_contains_expected_params(monkeypatch, isolated_file):
    _install_server(monkeypatch, error="access_denied")
    opened = []
    monkeypatch.setattr(oauth.webbrowser, "open", lambda url: opened.append(url))
    _flow(scopes=["scope.a", "scope.b"]).execute(timeout_s=5)

    assert len(opened) == 1
    parsed = urllib.parse.urlparse(opened[0])
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == oauth.GOOGLE_AUTH_URL
    q = urllib.parse.parse_qs(parsed.query)
    assert q["client_id"] == ["cid"]
    assert q["response_type"] == ["code"]
    assert q["scope"] == ["scope.a scope.b"]
    assert q["access_type"] == ["offline"]
    assert q["prompt"] == ["consent"]


def test_user_denied_closes_server(monkeypatch):
    _install_server(monkeypatch, error="access_denied")
    monkeypatch.setattr(oauth.webbrowser, "open", lambda url: True)
    ok, err, msg = _flow().execute(timeout_s=5)
    assert (ok, err) == (False, OAuthError.USER_DENIED)
    assert "access_denied" in msg
    assert _FakeServer.instances[0].closed


def test_browser_failure_returns_network_error(monkeypatch):
    _install_server(monkeypatch)

    def fail(_url):
        raise RuntimeError("no browser")
    monkeypatch.setattr(oauth.webbrowser, "open", fail)
    ok, err, msg = _flow().execute(timeout_s=5)
    assert (ok, err) == (False, OAuthError.NETWORK)
    assert "no browser" in msg
    assert _FakeServer.instances[0].closed


def test_timeout_when_no_redirect(monkeypatch):
    _install_server(monkeypatch)
    monkeypatch.setattr(oauth.webbrowser, "open", lambda url: True)
    clock = iter([0.0, 0.0, 1.0, 2.0, 999.0])
    monkeypatch.setattr(oauth, "time", SimpleNamespace(time=lambda: next(clock)))
    ok, err, _ = _flow().execute(timeout_s=10)
    assert (ok, err) == (False, OAuthError.TIMEOUT)
    assert _FakeServer.instances[0].handled == 3


def test_token_exchange_http_failure(monkeypatch):
    _install_server(monkeypatch, code="abc")
    monkeypatch.setattr(oauth.webbrowser, "open", lambda url: True)
    monkeypatch.setattr(oauth, "_REQUESTS_AVAILABLE", True)
    monkeypatch.setattr(oauth.requests, "post", lambda *a, **k: MagicMock(status_code=401))
    ok, err, msg = _flow().execute(timeout_s=5)
    assert (ok, err) == (False, OAuthError.NETWORK)
    assert "HTTP 401" in msg


def test_token_exchange_network_exception(monkeypatch):
    _install_server(monkeypatch, code="abc")
    monkeypatch.setattr(oauth.webbrowser, "open", lambda url: True)
    monkeypatch.setattr(oauth, "_REQUESTS_AVAILABLE", True)

    def raise_conn(*a, **k):
        raise ConnectionError("dns")
    monkeypatch.setattr(oauth.requests, "post", raise_conn)
    ok, err, msg = _flow().execute(timeout_s=5)
    assert (ok, err) == (False, OAuthError.NETWORK)
    assert "dns" in msg


def test_requests_unavailable(monkeypatch):
    _install_server(monkeypatch, code="abc")
    monkeypatch.setattr(oauth.webbrowser, "open", lambda url: True)
    monkeypatch.setattr(oauth, "_REQUESTS_AVAILABLE", False)
    ok, err, msg = _flow().execute(timeout_s=5)
    assert (ok, err) == (False, OAuthError.NETWORK)
    assert "requests" in msg


def test_successful_exchange_persists_tokens(monkeypatch, isolated_file):
    isolated_file.write_text(json.dumps({"existing": 1}), encoding="utf-8")
    _install_server(monkeypatch, code="auth-code-1")
    monkeypatch.setattr(oauth.webbrowser, "open", lambda url: True)
    monkeypatch.setattr(oauth, "_REQUESTS_AVAILABLE", True)
    posted = {}

    def fake_post(url, data=None, timeout=None):
        posted.update(url=url, data=data, timeout=timeout)
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"access_token": "AT", "refresh_token": "RT"}
        return resp
    monkeypatch.setattr(oauth.requests, "post", fake_post)
    store = MagicMock()

    ok, err, msg = _flow(store=store).execute(timeout_s=5)

    assert (ok, err) == (True, OAuthError.NONE)
    assert posted["url"] == oauth.GOOGLE_TOKEN_URL
    assert posted["data"]["code"] == "auth-code-1"
    assert posted["data"]["grant_type"] == "authorization_code"
    keys = {c.args[0]: c.args[1] for c in store.set.call_args_list}
    assert keys["google_workspace.refresh_token"] == "RT"
    assert keys["google_workspace.access_token"] == "AT"
    assert "google_workspace.token_saved_at" in keys
    cfg = json.loads(isolated_file.read_text(encoding="utf-8"))
    assert cfg["existing"] == 1
    assert cfg["google_workspace_refresh_token"] == "RT"
    assert cfg["google_workspace_access_token"] == "AT"
    assert cfg["google_workspace_client_id"] == "cid"
    assert cfg["google_workspace_client_secret"] == "secret"


def test_success_without_config_file_does_not_create_it(monkeypatch, isolated_file):
    _install_server(monkeypatch, code="c")
    monkeypatch.setattr(oauth.webbrowser, "open", lambda url: True)
    monkeypatch.setattr(oauth, "_REQUESTS_AVAILABLE", True)
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"access_token": "AT"}
    monkeypatch.setattr(oauth.requests, "post", lambda *a, **k: resp)
    store = MagicMock()
    ok, _, _ = _flow(store=store).execute(timeout_s=5)
    assert ok
    assert not isolated_file.exists()
    stored_keys = [c.args[0] for c in store.set.call_args_list]
    assert "google_workspace.refresh_token" not in stored_keys


def _make_handler(path):
    h = _OAuthRedirectHandler.__new__(_OAuthRedirectHandler)
    h.path = path
    h.wfile = io.BytesIO()
    h.request_version = "HTTP/1.1"
    h.requestline = f"GET {path} HTTP/1.1"
    h.command = "GET"
    h.client_address = ("127.0.0.1", 0)
    return h


@pytest.mark.parametrize(
    "path,status,attr,value,marker",
    [
        ("/?code=XYZ", b"200", "auth_code", "XYZ", b"AUTHENTICATION SUCCESSFUL"),
        ("/?error=access_denied", b"400", "error", "access_denied", b"CANCELLED"),
        ("/favicon.ico", b"404", None, None, None),
    ],
)
def test_redirect_handler_responses(path, status, attr, value, marker):
    h = _make_handler(path)
    h.do_GET()
    out = h.wfile.getvalue()
    assert out.split(b"\r\n", 1)[0].split()[1] == status
    if attr:
        assert getattr(_OAuthRedirectHandler, attr) == value
    else:
        assert _OAuthRedirectHandler.auth_code is None
        assert _OAuthRedirectHandler.error is None
    if marker:
        assert marker in out
