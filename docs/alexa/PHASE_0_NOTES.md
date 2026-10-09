# Phase 0 Reconnaissance & Architecture Decisions: Alexa Connection

## 1. Graphify Node & Edge Citations

The following symbols and architectural elements were located in `graphify-out/graph.json`:

- **SetupApiModal**:
  - Node ID: `core_ui_setup_api_modal_setupapimodal` (Community 242 `SetupApiModal`, `core/ui/setup_api_modal.py:L58`)
  - Invocation Node: `ui_mainwindow__open_api_setup` (`ui.py:L10715`)
  - Signal Node: `ui_tacticalcontrols_setup_api_requested` connected via `ui.py:L10240`
- **Window Layering & Z-Order**:
  - `core_hud_video_layering_make_frameless_overlay` (`core/hud_video/layering.py:L35`)
  - `core_hud_video_layering_raise_overlay` (`core/hud_video/layering.py:L52`)
  - `core_hud_video_layering_centre_overlay_globally` (`core/hud_video/layering.py:L68`)
  - Constant: `Z_SETTINGS_MODAL` (Community 93 `VideoTimeline`)
- **API Registry & Validation**:
  - `core_apis_registry_apibackend` (`core/apis/registry.py:L20`)
  - `core_apis_registry_validate_backend_fields` (`core/apis/registry.py:L147`)
  - `core_apis_registry_save_backend_credentials` (`core/apis/registry.py:L157`)
- **Encrypted Secret Store**:
  - `core_secrets_store_secretstore` (Community 117 `SecretStore`, `core/secrets/store.py:L58`)
  - Persistence Path Helper: `core_secrets_store_get_secrets_file_path` (`core/secrets/store.py:L53`)
- **OAuth Helpers**:
  - `core_apis_oauth_googleoauthflow` (Community 117 `SecretStore`, `core/apis/oauth.py:L97`)
  - `core_apis_oauth_oauthredirecthandler` (`core/apis/oauth.py:L44`)
- **Remote Uplink & Channels**:
  - `dashboard_server_dashboardserver` (Community 344 `DashboardServer`, `dashboard/server.py:L463`)
- **Intent Router & Dispatcher**:
  - `core_intents_router_intentrouter` (Community 200 `IntentRouter`, `core/intents/router.py:L51`)
  - Main Dispatcher: `main_agent_dispatch_tool` (`main.py:L2205`)
  - Action Callback: `main_agent__on_dashboard_action` (`main.py:L3475`)

---

## 0.1 Existing API Connections UI

1. **Tactical Controls / Setup API Backend Button**:
   - Located on Tactical Controls overlay widget (`ui.py:L10240`).
   - Signal `setup_api_requested` triggers `MainWindow._open_api_setup()` (`ui.py:L10715`).
2. **Popup / Dialog**:
   - Implemented in `core/ui/setup_api_modal.py` (`SetupApiModal`), exposed via `ui/setup_api_modal.py`.
   - Current backends: `google_workspace`, `spotify`, `gmail`.
3. **Tab Registration & Rendering**:
   - `SetupApiModal._init_ui()` defines tab metadata in `tab_defs: list[tuple[str, str]]`.
   - Styled toggle `QPushButton` instances are placed in a horizontal header row (`_tab_buttons`).
   - Content pages reside in a `QStackedWidget` (`_stack`).
   - Switching tabs invokes `_switch_tab(idx)`.
4. **Field Masking & Validation**:
   - Secret inputs use `QLineEdit.EchoMode.Password` (e.g. `self._spot_secret`, `self._gw_secret`).
   - Format validation runs off the Qt thread via `validate_backend_fields(backend_id, fields)` in `core/apis/registry.py`.
   - Asynchronous validation signals completion back to the main thread via `_async_validation_done = pyqtSignal(str, bool, str)`.
5. **Connection State Display**:
   - Displayed in modal footer via `self._status_lbl` with color tokens (`✓ {message}` in green, `✕ {message}` in red).
   - Real-time status update during background validation thread.
6. **Modal Stacking & Layering**:
   - Built as a frameless top-level overlay: `make_frameless_overlay(self, parent)` from `core/hud_video/layering.py`.
   - Positioned and raised on display: `centre_overlay_globally(modal, self)` and `raise_overlay(modal, self)`.
   - Layering hierarchy in `core/hud_video/layering.py` assigns `Z_SETTINGS_MODAL` priority above `Z_VISUAL_HUD`, `Z_HUD_BUTTONS`, and card toasts.
7. **Secret Store API & Persistence**:
   - Class `SecretStore` in `core/secrets/store.py`.
   - Persistence file: `config/secrets.env` (or project root fallback).
   - Encryption: PBKDF2HMAC (100,000 iterations, SHA256) deriving a Fernet key from machine fingerprint (`MachineGuid` on Windows).
   - Key API:
     - `get(key: str, default: Optional[str] = None) -> Optional[str]`
     - `set(key: str, value: str) -> None`
     - `delete(key: str) -> bool`
     - `has(key: str) -> bool`
   - Secondary compatibility persistence: `config/api_keys.json`.

---

## 0.2 Existing Authentication

1. **OAuth Helpers**:
   - `core/apis/oauth.py` implements `GoogleOAuthFlow`.
   - Local loopback server: `_OAuthRedirectHandler` using `http.server.HTTPServer` on `http://localhost:8080` (`OAUTH_LOCAL_PORT`).
   - Browser launching: `webbrowser.open(auth_url)`.
2. **Keyring & Encrypted Storage**:
   - Centralized in `core/secrets/store.py` (`SecretStore`). No second encryption framework should be built.
3. **Token Refresh Patterns**:
   - Google: stores refresh token at `google_workspace.refresh_token` and access token at `google_workspace.access_token`.
   - Spotify: client in `actions/spotify_control.py` refreshes tokens automatically with stored client credentials.
4. **User Identity & Account System**:
   - ALFRED has **no** cloud account or multi-user identity system. It is purely a local, single-user desktop application.
   - For Alexa integration, user/device mapping will link an Amazon user identifier to this specific ALFRED desktop instance identifier.

---

## 0.3 Existing Remote Channels

1. **Mobile Uplink Transport**:
   - `DashboardServer` (`dashboard/server.py`) hosts a local FastAPI server (default port 8000).
   - WebSockets:
     - `/ws`: JSON messages for commands, telemetry, actions, history.
     - `/ws/audio`: Bidirectional PCM streaming.
     - `/ws/phone-audio`: Mobile mic input.
2. **Hosted Relay**:
   - **None exists in repository.** The uplink is strictly local LAN.
3. **Authentication & Device Pairing**:
   - Query parameters `token` and `device_token`.
   - Optional symmetric payload encryption (`_decrypt(tok, enc)`).
4. **Remote Command Envelope**:
   - Inbound: `{"type": "command", "text": "..."}` or `{"type": "action", "action": "...", "params": {...}}`.
   - Outbound: `{"type": "action_result", "action": "...", "data": {...}, "error": "..."}`.
5. **Reconnection & Backoff**:
   - Mobile dashboard client initiates connection to desktop server. Desktop does not act as a client.
6. **Uplink Suitability for Alexa**:
   - Echo devices and the Alexa Skills Kit cloud require a publicly reachable, HTTPS endpoint with valid TLS and Amazon request signature verification.
   - Desktop ALFRED cannot receive inbound HTTPS requests from Amazon without public IP / port forwarding.
   - Reusing local uplink as-is is not feasible.
   - **Architecture requirement**: An outbound, persistent WebSocket connection from ALFRED desktop to a hosted relay (or secure tunnel) that receives and verifies Alexa Skills Kit requests.

---

## 0.4 Dispatcher and Safe Commands

Remote commands flow into `MainWindow._on_dashboard_action()` or `MainWindow._dispatch_tool()` (`main.py:L2205`).

### Command Classification & Alexa Policy

| Category | Command / Intent Examples | Alexa Policy Default | Rationale |
|---|---|---|---|
| **Read-Only** | `system_status` (CPU/RAM), `get_time`, `get_date`, `weather_report`, `get_deck_state` | **ALLOW** | Safe telemetry, no system modification |
| **Reversible Local State** | `audio_core` (pause/resume/volume), `spotify` (pause/resume/skip), `toggle_mute`, `sentry_focus` (start/stop) | **ALLOW** | Safe playback and focus controls |
| **Privacy-Sensitive** | `gmail_manager` (read emails), calendar event details, `recall_memory` | **DENY / CONFIRM** | Prevents Echo from speaking private data aloud |
| **Device Control** | `mute_system_microphone`, `open_app`, `toggle_dark_mode`, `close_tab` | **PER-COMMAND** | Mute/dark mode allowed; arbitrary app launch denied |
| **Destructive** | `undo`, file deletion, shutdown (`shutdown_alfred`, `shutdown_jarvis`) | **DENY** | Irreversible without interactive confirmation |
| **Arbitrary Execution** | `computer_control` (keyboard, mouse, click, write, shell) | **DENY** | Extreme risk of remote code execution |
| **Screen / Private Media** | `computer_control(action="screenshot")`, `screen_monitor`, `screen_process`, raw webcam | **DENY** | Echo cannot display visuals; leaks user desktop |

---

## 0.5 Owner Clarification Decisions

Confirmed by owner:
1. **Communication Scope**: Bidirectional (Inbound commands Echo -> ALFRED + ALFRED announcement support via Alexa Proactive Events / Skill messaging where authorized).
2. **Deployment Tier**: Personal development skill (`DEVELOPMENT` stage in Alexa Developer Console test mode).
3. **Relay Infrastructure**: No external relay deployed yet; provide a standalone deployable server package (`server/alexa/`) along with local mock/testing harness.
4. **Permitted Actions**: Safe telemetry, media playback (Spotify/Audio Core), focus mode, internet speed test, and non-private Calendar/Schedule summaries.
5. **Sensitive Command Policy**: Strictly disabled by default (no shell, keyboard/mouse automation, private emails, or destructive actions callable from Alexa).

## 0.6 Architectural Consensus

- **Skill Type**: Alexa Custom Skill (`ALFRED Alexa Skill`).
- **Account Linking**: OAuth 2.0 authorization code / state-token linking between Amazon Alexa User ID and local ALFRED installation token.
- **Relay & Endpoint**:
  - `server/alexa/`: FastAPI / Starlette HTTPS endpoint for Amazon Skills Kit webhooks with request verification (certificate chain, signature, timestamp, request ID replay cache).
  - Outbound authenticated WebSocket (`wss://`) connection from desktop ALFRED client (`core/integrations/alexa/client.py`) to relay server.
- **Command Security**:
  - Intent router with strict `AlexaActionPolicy` allowlist.
  - Zero storage/logging of Amazon passwords, tokens, or spoken request bodies.
  - Replay protection & deadline enforcement (`ALEXA_COMMAND_TIMEOUT_S = 8`).

