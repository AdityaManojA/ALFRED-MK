"""
tests/ui/test_setup_api_modal.py — Behavioural tests for the tabbed API backend
setup dialog (core/ui/setup_api_modal.py).

Uses an in-memory fake secret store (no keyring / disk), redirects the legacy
config/api_keys.json paths into tmp_path, and stubs browser / OAuth / threads.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
import sys
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

import core.ui.setup_api_modal as modal_mod
from core.ui.setup_api_modal import SetupApiModal, _TabsProxy, COLOR_YELLOW, COLOR_CYAN
from core.integrations.alexa.state import AlexaConnectionStatus
from core.ui.alexa_permissions_dialog import CAPABILITY_DEFINITIONS


class FakeStore:
    """Minimal in-memory stand-in for core.secrets.store.SecretStore."""

    def __init__(self, data=None):
        self.data = dict(data or {})

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value

    def delete(self, key):
        return self.data.pop(key, None) is not None

    def has(self, key):
        v = self.data.get(key)
        return bool(v and str(v).strip())


class _SyncThread:
    def __init__(self, target=None, daemon=None, name=None, **_):
        self._t = target

    def start(self):
        self._t()


VALID_SPOTIFY_ID = "0123456789abcdef0123456789abcdef"
VALID_SPOTIFY_SECRET = "fedcba9876543210fedcba9876543210"
VALID_GW_ID = "12345678901234567890.apps.googleusercontent.com"
VALID_GW_SECRET = "GOCSPX-abcdefghijkl"
VALID_SKILL = "amzn1.ask.skill.12345678-1234-1234-1234-123456789012"


@pytest.fixture
def cfg_paths(tmp_path):
    spot = tmp_path / "api_keys.json"
    gmail = tmp_path / "gmail_keys.json"
    with patch("actions.spotify_control.API_CONFIG_PATH", spot), \
         patch("actions.gmail_manager._CONFIG_PATH", gmail), \
         patch("webbrowser.open") as wb:
        yield {"spotify": spot, "gmail": gmail, "browser": wb}


def _modal(store=None):
    return SetupApiModal(store=store if store is not None else FakeStore())


def _emitted(modal):
    got = []
    modal.config_saved.connect(got.append)
    return got


# ── _TabsProxy ───────────────────────────────────────────────────────────────

def test_tabs_proxy_count_and_bounds():
    p = _TabsProxy(["A", "B"])
    assert p.count() == 2
    assert p.tabText(0) == "A"
    assert p.tabText(1) == "B"
    assert p.tabText(2) == ""
    assert p.tabText(-1) == ""


# ── construction / loading ───────────────────────────────────────────────────

def test_construction_defaults(cfg_paths):
    m = _modal()
    assert m._tabs.count() == 4
    assert m._stack.count() == 4
    assert m._active_tab_idx == 0
    assert m._tab_buttons[0].isChecked()
    assert m._gw_cid.text() == ""
    assert m._alexa_status_badge.text() == "NOT CONFIGURED"
    assert m._gmail_stack.currentIndex() == 0


def test_loads_values_from_store(cfg_paths):
    store = FakeStore({
        "google_workspace.client_id": VALID_GW_ID,
        "google_workspace.client_secret": VALID_GW_SECRET,
        "spotify.client_id": VALID_SPOTIFY_ID,
        "spotify.client_secret": VALID_SPOTIFY_SECRET,
        "gmail.user": "bruce@wayne.com",
        "gmail.api_key": "abcdefghijklmnop",
        "alexa.skill_id": VALID_SKILL,
        "alexa.relay_https_url": "https://relay.example.com",
    })
    m = _modal(store)
    assert m._gw_cid.text() == VALID_GW_ID
    assert m._spot_cid.text() == VALID_SPOTIFY_ID
    assert m._spot_secret.text() == VALID_SPOTIFY_SECRET
    assert m._gmail_email.text() == "bruce@wayne.com"
    assert m._gmail_pw.text() == "abcdefghijklmnop"
    assert m._alexa_skill_id.text() == VALID_SKILL
    assert m._alexa_relay_https.text() == "https://relay.example.com"
    # skill id present → state manager moves to READY_TO_LINK
    assert m._alexa_state_mgr.get_snapshot().status == AlexaConnectionStatus.READY_TO_LINK
    assert m._alexa_status_badge.text() == "READY TO LINK"


def test_placeholder_spotify_values_fall_back_to_config_file(cfg_paths):
    cfg_paths["spotify"].write_text(json.dumps({
        "spotify_client_id": VALID_SPOTIFY_ID,
        "spotify_client_secret": VALID_SPOTIFY_SECRET,
    }), encoding="utf-8")
    store = FakeStore({"spotify.client_id": "a" * 32, "spotify.client_secret": "your_client_secret"})
    m = _modal(store)
    assert m._spot_cid.text() == VALID_SPOTIFY_ID
    assert m._spot_secret.text() == VALID_SPOTIFY_SECRET


def test_placeholder_spotify_values_not_shown_when_no_fallback(cfg_paths):
    m = _modal(FakeStore({"spotify.client_id": "a" * 32}))
    assert m._spot_cid.text() == ""


def test_gmail_falls_back_to_config_file(cfg_paths):
    cfg_paths["gmail"].write_text(json.dumps({
        "gmail_email": "alfred@wayne.com", "gmail_passkey": "pppppppppppppppp",
    }), encoding="utf-8")
    m = _modal()
    assert m._gmail_email.text() == "alfred@wayne.com"
    assert m._gmail_pw.text() == "pppppppppppppppp"


def test_corrupt_config_file_is_tolerated(cfg_paths):
    cfg_paths["spotify"].write_text("{not json", encoding="utf-8")
    cfg_paths["gmail"].write_text("{not json", encoding="utf-8")
    m = _modal()
    assert m._gw_cid.text() == ""
    assert m._gmail_email.text() == ""


def test_stored_oauth_json_switches_gmail_mode(cfg_paths):
    blob = '{"installed": {"client_id": "x", "client_secret": "y"}}'
    m = _modal(FakeStore({"gmail.credentials_json": blob}))
    assert m._gmail_stack.currentIndex() == 1
    assert m._gmail_mode_oauth.isChecked() and not m._gmail_mode_pw.isChecked()
    assert m._gmail_json.toPlainText() == blob


# ── tab switching ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("requested, expected", [(2, 2), (-5, 0), (99, 3)])
def test_switch_tab_clamps_and_checks_button(cfg_paths, requested, expected):
    m = _modal()
    m._status_lbl.setText("stale")
    m._switch_tab(requested)
    assert m._active_tab_idx == expected
    assert m._stack.currentIndex() == expected
    assert [b.isChecked() for b in m._tab_buttons] == [i == expected for i in range(4)]
    assert m._status_lbl.text() == ""


def test_set_gmail_mode_toggles_pages(cfg_paths):
    m = _modal()
    m._set_gmail_mode("oauth_json")
    assert m._gmail_stack.currentIndex() == 1
    m._set_gmail_mode("api_key")
    assert m._gmail_stack.currentIndex() == 0
    assert m._gmail_mode_pw.isChecked()


# ── submission ───────────────────────────────────────────────────────────────

def test_submit_spotify_saves_and_syncs_config(cfg_paths):
    cfg_paths["spotify"].write_text("{}", encoding="utf-8")
    store = FakeStore()
    m = _modal(store)
    got = _emitted(m)
    m._spot_cid.setText(VALID_SPOTIFY_ID)
    m._spot_secret.setText(VALID_SPOTIFY_SECRET)
    m._submit_spotify()
    assert got == ["Spotify"]
    assert store.get("spotify.client_id") == VALID_SPOTIFY_ID
    cfg = json.loads(cfg_paths["spotify"].read_text(encoding="utf-8"))
    assert cfg["spotify_client_secret"] == VALID_SPOTIFY_SECRET
    assert m._status_lbl.text().startswith("✓")


def test_submit_invalid_spotify_reports_error_and_saves_nothing(cfg_paths):
    store = FakeStore()
    m = _modal(store)
    got = _emitted(m)
    m._spot_cid.setText("short")
    m._spot_secret.setText(VALID_SPOTIFY_SECRET)
    m._submit_spotify()
    assert got == []
    assert store.data == {}
    assert m._status_lbl.text().startswith("✕")
    assert "32 alphanumeric" in m._status_lbl.text()


def test_submit_gw_uses_backend_display_name(cfg_paths):
    store = FakeStore()
    m = _modal(store)
    got = _emitted(m)
    m._gw_cid.setText(VALID_GW_ID)
    m._gw_secret.setText(VALID_GW_SECRET)
    m._submit_gw()
    assert got == ["Google Workspace"]
    assert store.get("google_workspace.client_secret") == VALID_GW_SECRET
    assert not cfg_paths["spotify"].exists()  # sync only when file already exists


def test_submit_gmail_app_password_mode_syncs_user_and_config(cfg_paths):
    cfg_paths["gmail"].write_text("{}", encoding="utf-8")
    store = FakeStore()
    m = _modal(store)
    got = _emitted(m)
    m._gmail_email.setText("bruce@wayne.com")
    m._gmail_pw.setText("abcd efgh ijkl mnop")
    m._submit_gmail()
    assert got == ["Gmail API"]
    assert store.get("gmail.auth_mode") == "api_key"
    assert store.get("gmail.user") == "bruce@wayne.com"
    cfg = json.loads(cfg_paths["gmail"].read_text(encoding="utf-8"))
    assert cfg["gmail_app_password"] == "abcdefghijklmnop"  # spaces stripped
    assert cfg["gmail_user"] == "bruce@wayne.com"


def test_submit_gmail_oauth_mode_validates_json(cfg_paths):
    store = FakeStore()
    m = _modal(store)
    got = _emitted(m)
    m._set_gmail_mode("oauth_json")
    m._gmail_json.setPlainText('{"web": {}}')
    m._submit_gmail()
    assert got == []
    assert "missing client_id" in m._status_lbl.text()

    m._gmail_json.setPlainText('{"installed": {"client_id": "a", "client_secret": "b"}}')
    m._submit_gmail()
    assert got == ["Gmail API"]
    assert store.get("gmail.auth_mode") == "oauth_json"


def test_submit_alexa_marks_configured(cfg_paths):
    store = FakeStore()
    m = _modal(store)
    got = _emitted(m)
    m._alexa_skill_id.setText(VALID_SKILL)
    m._alexa_relay_ws.setText("wss://relay.example.com/ws")
    m._submit_alexa()
    assert got == ["Alexa Connection"]
    assert store.get("alexa.relay_ws_url") == "wss://relay.example.com/ws"
    assert m._alexa_status_badge.text() == "READY TO LINK"


def test_save_alexa_dev_config_routes_to_alexa_tab(cfg_paths):
    m = _modal()
    m._alexa_skill_id.setText(VALID_SKILL)
    with patch.object(modal_mod.threading, "Thread", _SyncThread):
        m._save_alexa_dev_config()
    assert m._active_tab_idx == 3
    assert m.store.get("alexa.skill_id") == VALID_SKILL


def test_async_submit_runs_on_background_thread(cfg_paths):
    m = _modal()
    with patch.object(modal_mod.threading, "Thread") as thr:
        m._switch_tab(1)
        m._on_submit_current_tab()
    assert thr.call_args.kwargs["daemon"] is True
    thr.return_value.start.assert_called_once()
    assert m._status_lbl.text() == "Validating spotify..."


# ── Alexa developer panel / validation ───────────────────────────────────────

def test_validate_alexa_dev_config(cfg_paths):
    m = _modal()
    m._validate_alexa_dev_config()
    assert m._status_lbl.text() == "✕ Alexa Skill ID is required."
    m._alexa_skill_id.setText(VALID_SKILL)
    m._alexa_relay_https.setText("http://evil.example.com")
    m._validate_alexa_dev_config()
    assert "HTTPS" in m._status_lbl.text() and m._status_lbl.text().startswith("✕")
    m._alexa_relay_https.setText("https://relay.example.com")
    m._validate_alexa_dev_config()
    assert m._status_lbl.text() == "✓ Alexa configuration format is valid."


def test_toggle_dev_panel_flips_label(cfg_paths):
    m = _modal()
    assert m._alexa_dev_toggle_btn.text().startswith("▸")
    assert m._alexa_dev_widget.isHidden()
    # Dialog itself is never shown, so isVisible() is False before the toggle → expands.
    m._toggle_alexa_dev_panel()
    assert not m._alexa_dev_widget.isHidden()
    assert m._alexa_dev_toggle_btn.text() == "▾  DEVELOPER CONFIGURATION"


def test_start_linking_requires_configuration(cfg_paths):
    m = _modal()
    m._start_alexa_linking()
    assert "configure Alexa Skill ID" in m._status_lbl.text()
    assert not m._alexa_dev_widget.isHidden()
    assert m._alexa_dev_toggle_btn.text().startswith("▾")
    cfg_paths["browser"].assert_not_called()


def test_start_linking_builds_url_and_opens_browser(cfg_paths):
    store = FakeStore({"alexa.skill_id": VALID_SKILL, "alexa.relay_https_url": "https://relay.example.com/"})
    m = _modal(store)
    m._alexa_linking_mgr.create_linking_state = MagicMock(return_value="TOKEN123")
    m._start_alexa_linking()
    url = "https://relay.example.com/api/alexa/link?state=TOKEN123"
    assert m._alexa_link_url_input.text() == url
    cfg_paths["browser"].assert_called_once_with(url)
    assert m._alexa_state_mgr.get_snapshot().status == AlexaConnectionStatus.LINK_PENDING
    assert m._alexa_status_badge.text() == "LINKING IN PROGRESS..."
    assert COLOR_CYAN in m._status_lbl.styleSheet()
    # QR rendered either as a pixmap (qrcode installed) or fallback text.
    lbl = m._alexa_qr_label
    assert (lbl.pixmap() is not None and not lbl.pixmap().isNull()) or lbl.text() == "[QR Code]"


def test_render_qr_code_fallback_when_qrcode_missing(cfg_paths):
    m = _modal()
    with patch.dict(sys.modules, {"qrcode": None}):
        m._render_qr_code("https://x")
    assert m._alexa_qr_label.text() == "[QR Code]"


def test_disconnect_revokes_tokens_only(cfg_paths):
    store = FakeStore({
        "alexa.skill_id": VALID_SKILL,
        "alexa.oauth_access_token": "a",
        "alexa.oauth_refresh_token": "r",
        "spotify.client_id": VALID_SPOTIFY_ID,
    })
    m = _modal(store)
    m._alexa_state_mgr.set_linked(True)
    m._on_alexa_disconnect()
    assert "alexa.oauth_access_token" not in store.data
    assert "alexa.oauth_refresh_token" not in store.data
    assert store.get("spotify.client_id") == VALID_SPOTIFY_ID
    assert store.get("alexa.skill_id") == VALID_SKILL
    assert m._alexa_state_mgr.get_snapshot().linked is False
    assert m._alexa_status_badge.text() == "READY TO LINK"
    assert COLOR_YELLOW in m._status_lbl.styleSheet()


@pytest.mark.parametrize("status, text", [
    (AlexaConnectionStatus.NOT_CONFIGURED, "NOT CONFIGURED"),
    (AlexaConnectionStatus.CONNECTED, "CONNECTED"),
    (AlexaConnectionStatus.OFFLINE, "OFFLINE"),
    (AlexaConnectionStatus.ERROR, "ERROR"),
])
def test_refresh_alexa_badge_maps_status(cfg_paths, status, text):
    m = _modal()
    m._alexa_state_mgr._status = status
    m._refresh_alexa_ui_state()
    assert m._alexa_status_badge.text() == text


# ── Alexa permissions ────────────────────────────────────────────────────────

def test_permissions_open_load_save_and_return(cfg_paths):
    first_cap = CAPABILITY_DEFINITIONS[0][0]
    store = FakeStore({f"alexa.perm.{first_cap}": "false"})
    m = _modal(store)
    m._open_alexa_permissions()
    assert m._alexa_stack.currentIndex() == 1
    assert not m._alexa_perms_checkboxes[first_cap].isChecked()

    before = m._alexa_policy.count_allowed_intents()
    m._save_alexa_perms(and_return=True)
    assert m._alexa_stack.currentIndex() == 0
    assert store.get(f"alexa.perm.{first_cap}") == "false"
    assert m._alexa_policy.is_capability_enabled(first_cap) is False
    after = m._alexa_policy.count_allowed_intents()
    assert after <= before
    assert m._alexa_allowed_count_lbl.text() == f"ALLOWED COMMANDS: {after}"
    assert "permissions saved" in m._status_lbl.text()


def test_permissions_reset_defaults(cfg_paths):
    m = _modal()
    for cb in m._alexa_perms_checkboxes.values():
        cb.setChecked(False)
    m._reset_alexa_perms_defaults()
    for cap_id, _t, _d, default in CAPABILITY_DEFINITIONS:
        assert m._alexa_perms_checkboxes[cap_id].isChecked() is default


def test_save_perms_without_return_stays_on_page(cfg_paths):
    m = _modal()
    m._open_alexa_permissions()
    m._save_alexa_perms(and_return=False)
    assert m._alexa_stack.currentIndex() == 1
    m._close_alexa_permissions()
    assert m._alexa_stack.currentIndex() == 0


# ── OAuth launchers ──────────────────────────────────────────────────────────

def test_google_oauth_requires_credentials(cfg_paths):
    m = _modal()
    with patch.object(modal_mod.threading, "Thread") as thr:
        m._start_google_oauth()
    thr.assert_not_called()
    assert "Google Client ID and Secret" in m._status_lbl.text()


def test_google_oauth_worker_persists_and_reports(cfg_paths):
    cfg_paths["spotify"].write_text("{}", encoding="utf-8")
    store = FakeStore()
    m = _modal(store)
    got = _emitted(m)
    m._gw_cid.setText(VALID_GW_ID)
    m._gw_secret.setText(VALID_GW_SECRET)
    flow = MagicMock()
    flow.return_value.execute.return_value = (True, None, "Authorized")
    with patch.object(modal_mod.threading, "Thread", _SyncThread), \
         patch("core.apis.oauth.GoogleOAuthFlow", flow):
        m._start_google_oauth()
    flow.assert_called_once_with(VALID_GW_ID, VALID_GW_SECRET, store=store)
    assert store.get("google_workspace.client_id") == VALID_GW_ID
    assert json.loads(cfg_paths["spotify"].read_text())["google_workspace_client_id"] == VALID_GW_ID
    assert got == ["Google Workspace"]
    assert m._status_lbl.text() == "✓ Authorized"


def test_spotify_oauth_requires_credentials(cfg_paths):
    m = _modal()
    with patch.object(modal_mod.threading, "Thread") as thr:
        m._start_spotify_oauth()
    thr.assert_not_called()
    assert "Spotify Client ID and Secret" in m._status_lbl.text()


@pytest.mark.parametrize("ok, prefix", [(True, "✓"), (False, "✕")])
def test_spotify_oauth_worker_reports_result(cfg_paths, ok, prefix):
    m = _modal()
    got = _emitted(m)
    m._spot_cid.setText(VALID_SPOTIFY_ID)
    m._spot_secret.setText(VALID_SPOTIFY_SECRET)
    client = MagicMock()
    with patch.object(modal_mod.threading, "Thread", _SyncThread), \
         patch("actions.spotify_control.get_spotify_client", return_value=client), \
         patch("actions.spotify_control.authorize_user", return_value=ok):
        m._start_spotify_oauth()
    assert client._client_id == VALID_SPOTIFY_ID
    assert m._status_lbl.text().startswith(prefix)
    assert got == (["Spotify"] if ok else [])


# ── misc ─────────────────────────────────────────────────────────────────────

def test_on_validation_result_failure_does_not_emit(cfg_paths):
    m = _modal()
    got = _emitted(m)
    m._on_validation_result("X", False, "nope")
    assert got == []
    assert m._status_lbl.text() == "✕ nope"


def test_paint_event_renders_offscreen(cfg_paths):
    from PyQt6.QtGui import QImage
    m = _modal()
    img = QImage(m.width(), m.height(), QImage.Format.Format_ARGB32)
    img.fill(0)
    m.render(img)
    # Rounded-rect background (#040c16) is painted inside the border.
    c = img.pixelColor(m.width() // 2, m.height() - 4)
    assert c.alpha() > 0


def test_show_event_reloads_and_clears_status(cfg_paths):
    from PyQt6.QtGui import QShowEvent
    store = FakeStore()
    m = _modal(store)
    m._status_lbl.setText("old")
    store.set("spotify.client_id", VALID_SPOTIFY_ID)
    m.showEvent(QShowEvent())
    assert m._status_lbl.text() == ""
    assert m._spot_cid.text() == VALID_SPOTIFY_ID
