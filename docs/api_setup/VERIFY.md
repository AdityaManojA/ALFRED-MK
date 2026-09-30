# ALFRED-MK-V: API Backend Setup Verification Checklist

## 1. Unit Test Suite
Run unit tests for SecretStore, API registry validators, and SetupApiModal UI:
```bash
python -m unittest tests.test_secret_store tests.test_api_registry tests.test_api_setup_ui
```

- [x] **SecretStore**: `test_set_and_get_secret`, `test_persistence_across_instances`, `test_file_is_encrypted_on_disk`, `test_delete_secret`, `test_format_validation`.
- [x] **API Registry**: `test_registry_contains_required_backends`, `test_spotify_validator`, `test_google_workspace_validator`, `test_gmail_app_password_validator`, `test_save_and_retrieve_backend_credentials`.
- [x] **SetupApiModal UI**: `test_modal_initialization_and_tabs`, `test_masked_inputs`, `test_submit_spotify_valid`, `test_submit_spotify_invalid`.

---

## 2. Live Functional Verification Checklist

### A. Modal UI & Aesthetics
1. Open Tactical Controls (`_quick_drawer`).
2. Verify button `[ ◈ ] SETUP API BACKENDS (X/3)` is visible and matches Batcomputer theme buttons (`_BTN_STYLE_PRI`, monospace font, cyan accent).
3. Click the button — verify `SetupApiModal` opens instantly (< 30ms lazy instantiation).
4. Verify 3 tabs are present: **Google Workspace**, **Spotify**, **Gmail API**.
5. Verify active tab is highlighted with palette accent `C.PRI` and inactive tabs use `C.PANEL2`.
6. Verify all credential input fields are masked (`QLineEdit.EchoMode.Password`).
7. Verify CRT scanlines and subtle cyan focus glow are active on the dialog background.

### B. Form Validation & Persistence
1. **Spotify Tab**:
   - Enter invalid client ID (`"short"`). Click `[ SAVE SPOTIFY CONFIG ]`.
   - Verify non-blocking status text shows: `✗ Invalid: Spotify Client ID must be exactly 32 alphanumeric characters`.
   - Enter valid 32-char alphanumeric ID and secret. Click Save.
   - Verify status updates to `✓ Spotify authenticated, sir` and the button in Tactical Controls reflects updated count `(1/3)`.
2. **Google Workspace Tab**:
   - Test OAuth toggle: check `☐ Use OAuth (recommended)` -> verify direct fields hide and `[ AUTHORIZE WITH GOOGLE ]` button displays.
   - Uncheck toggle -> input fields display for manual Client ID & Secret.
3. **Gmail API Tab**:
   - Sub-tabs: Switch between `[ APP PASSWORD / API KEY ]` and `[ OAUTH CREDENTIALS JSON ]`.
   - In App Password tab: enter 16-char app password (spaces optional/auto-stripped). Click Save.
   - In OAuth JSON tab: paste Google Cloud credentials JSON. Click Save -> JSON format is validated before saving.

### C. Security & Privacy Audit
1. Inspect `~/.alfred/secrets.env` (or `%USERPROFILE%\.alfred\secrets.env`):
   - Confirm file permissions are restricted (0600 / current user only).
   - Confirm all values stored are encrypted Fernet ciphertexts (`gAAAAA...`).
   - Confirm master key is stored in OS keyring (`alfred-master-key`) or machine fingerprint fallback.
2. Confirm keys never appear in log files or console stdout/stderr.
3. Confirm closing and reopening the modal displays masked placeholders without echoing cleartext values.

### D. Tool Execution & Credential Injection
1. Run Spotify tool or Gmail manager tool:
   - Tool retrieves credentials dynamically via `get_secret_store().get("spotify.client_id")` and `get_secret_store().get("gmail.user")`.
   - If credentials are removed via `store.delete()`, tool gracefully logs warning once without crashing.
