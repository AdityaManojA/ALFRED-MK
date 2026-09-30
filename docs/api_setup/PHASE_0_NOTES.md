# Phase 0 Reconnaissance Notes: API Backend Setup UI (Tactical Controls)

**Date:** 2026-09-30
**Status:** Complete

---

## 1. Tactical Controls Button & Settings Area
* **File:** `ui.py`
* **Class / Function:** `MainWindow._build_quick_drawer()` (`ui.py:L9155-L9328`), triggered by `MainWindow._drawer_btn` (`ui.py:L8788`, node `ui_mainwindow_build_quick_drawer`).
* **Existing Setup Button:**
  * In `_build_quick_drawer()`: line 9318 has `setup_api_btn = QPushButton("[ ◈ ]  SETUP API & BACKEND")`, connected to `self._open_api_setup` (`ui.py:L11332`).
  * In `CustomizeOverlay`: line 5770 has a button connected to `self.setup_api_requested.emit()` -> `MainWindow._open_api_setup`.
  * In `MainWindow._open_api_setup`: line 11332 opens the legacy `SetupOverlay` (which only handled Gemini/Ollama/OpenRouter LLMs).
* **Target Enhancement:**
  * Replace the basic setup flow in Tactical Controls with the dedicated, tabbed, theme-matching **`SetupApiModal`** (`ui/setup_api_modal.py` or `core/apis/ui.py`).
  * Show a live indicator badge on the button in Tactical Controls (e.g. `[ ◈ ] SETUP API BACKENDS (2/3)`).

---

## 2. Current API Key Storage & Boot Path
* **File:** `memory/config_manager.py` & `config/api_keys.json`.
* **Current Storage:** Plaintext JSON file at `config/api_keys.json` (read by `_read_full_config()` / `load_api_keys()` in `memory/config_manager.py`).
* **Existing Consumers:**
  * `spotify_control.py:L160`: Reads `config/api_keys.json` for `spotify_client_id`, `spotify_client_secret`, `spotify_refresh_token`, `spotify_access_token`.
  * `gmail_manager.py:L27`: Reads `config/api_keys.json` for `gmail_user`, `gmail_app_password`.
  * `computer_settings.py:L40`: Reads `config/api_keys.json` for `gemini_api_key`.
  * `main.py` & `local_pipeline.py`: Loads LLM provider keys at boot time.
* **Security Deficiency:** Secrets are stored unencrypted in repository/app workspace JSON.

---

## 3. Existing OAuth Flows
* **Spotify:**
  * `actions/spotify_control.py:L310` (`_authenticate_via_browser`): Starts a local `http.server.HTTPServer` on port 8888, opens browser to `https://accounts.spotify.com/authorize`, receives authorization code, and exchanges for tokens.
* **Google / Gmail / Workspace:**
  * `actions/gmail_manager.py` currently relies on App Passwords / IMAP. No full OAuth 2.0 PKCE / redirect server was standard for Workspace/Gmail.
  * We will add `core/apis/oauth.py` implementing `GoogleOAuthFlow` (local loopback server on port 8888 with `OAUTH_TIMEOUT_S = 120`).

---

## 4. Encryption & Master Key Management
* **Current State:** No Fernet encryption or OS keyring integration exists.
* **New Implementation (`core/secrets/store.py`):**
  * Use `cryptography.fernet.Fernet` for AES-128 CBC / HMAC encryption.
  * Master Key derivation:
    1. Check system keyring (`keyring` package / Windows Credential Manager / macOS Keychain / SecretService) under `KEYRING_NAME = "alfred-master-key"`.
    2. Fallback to machine-fingerprint hash (CPU ID + Machine GUID + Hostname via PBKDF2HMAC) if keyring is disabled or unavailable.
  * Atomic file writes (write to `.tmp` then replace) to prevent corruption.

---

## 5. Secrets Location
* **Location Path:**
  * Windows: `%APPDATA%\Alfred\secrets.env` (e.g. `C:\Users\<user>\AppData\Roaming\Alfred\secrets.env` or `~/.alfred/secrets.env`).
  * Cross-platform standard: `Path.home() / ".alfred" / "secrets.env"`.
  * `pathlib.Path` will be used standardly across all platforms.

---

## 6. Modal Base & Visual Styling
* **Base Classes:** Inherits `_HudOverlay` or `QDialog` styled with `C.PANEL_BG`, `C.BORDER_B`, `C.BORDER_A`, `C.PRI`, `C.ACC`, and `C.TEXT_MED`.
* **Theme Matching:**
  * Respects `ThemeChrome.get_active().palette` dynamically.
  * Monospaced typography via `mono_font()` and `tech_font()`.
  * Input fields masked with `QLineEdit.EchoMode.Password`.
  * Zero flickering, non-blocking asynchronous validation.

---

## Files to Create & Touch

### Files to Create:
1. `core/secrets/__init__.py`
2. `core/secrets/store.py` — Encrypted SecretStore with keyring + Fernet.
3. `core/apis/__init__.py`
4. `core/apis/registry.py` — API backend registry & format validators.
5. `core/apis/oauth.py` — Google Workspace & Gmail loopback OAuth helper.
6. `ui/setup_api_modal.py` — Tabbed, theme-matching frameless API setup modal dialog.
7. `tests/test_secret_store.py` — Unit tests for store encryption, validation, privacy.
8. `tests/test_api_registry.py` — Unit tests for format validators & OAuth mocks.
9. `tests/test_api_setup_ui.py` — Unit tests for modal tab switching, inputs, and indicators.

### Files to Touch:
1. `ui.py` — Wire `SetupApiModal` into `MainWindow._open_api_setup`, update Tactical Controls `setup_api_btn` with dynamic backend count indicator `(X/3)`.
2. `actions/spotify_control.py` — Hook into `SecretStore` to load Spotify client ID & secrets with transparent fallback.
3. `actions/gmail_manager.py` — Hook into `SecretStore` to load Gmail credentials / OAuth tokens.
4. `core/action_loader.py` or boot path — Inject decrypted secrets into tool runtime environment.
