# Phase 2 Notes: API Connections Alexa Tab Implementation

## 1. Graphify Citations

- Setup API Modal & Integration:
  - `core_ui_setup_api_modal_setupapimodal` (`core/ui/setup_api_modal.py:L60`)
  - Stacking & Layering: `core_hud_video_layering_make_frameless_overlay` (`core/hud_video/layering.py:L35`)
- Permissions Management Dialog:
  - `core/ui/alexa_permissions_dialog.py` (`AlexaPermissionsDialog`)
- Backend Registry:
  - `core_apis_registry_apibackend` (`core/apis/registry.py:L130`)
  - `_validate_alexa` (`core/apis/registry.py:L104`)

---

## 2. Key Accomplishments & Deliverables

1. **Integrated Alexa Tab in Existing Modal**:
   - Added `("alexa", "🎙  ALEXA")` beside Google Workspace, Spotify, and Gmail.
   - Preserved existing layering: `make_frameless_overlay()`, `centre_overlay_globally()`, and `raise_overlay()` ensuring modal sits safely above Visual HUD video, Bat Globe, and Minimised HUD.
2. **User Mode Experience**:
   - Clean, uncluttered interface:
     - Prominent status indicator: `NOT CONFIGURED`, `READY TO LINK`, `LINKING IN PROGRESS...`, `CONNECTED`, `OFFLINE`, `ERROR`.
     - Tactical `[ CONNECT ALEXA ]` and `[ DISCONNECT ]` buttons.
     - `ALLOWED COMMANDS: X` display with `[ MANAGE PERMISSIONS ]` button.
     - Dynamic single-use account linking flow generating QR code and copyable URL.
3. **Collapsed Developer Configuration**:
   - Placed behind expandable `▸ DEVELOPER CONFIGURATION` toggle.
   - Collects only developer parameters: Skill ID, Relay HTTPS URL, Relay WebSocket URL, Skill Store URL, OAuth Client ID, OAuth Client Secret, OAuth Redirect URL.
   - Secret inputs use `QLineEdit.EchoMode.Password` with masking and placeholder retention.
   - Action buttons: `[ VALIDATE CONFIGURATION ]` and `[ SAVE CONFIGURATION ]`.
4. **Permissions Dialog**:
   - Created `AlexaPermissionsDialog` with checkboxes for approved capabilities (Telemetry, Focus, Media, Speed, Reminders, Calendar, Mic Mute) and clear notices for prohibited capabilities (Shell, Keyboard/Mouse automation, Screen capture, File modification).

---

## 3. Unit Tests & Live Verification

### Unit Tests (`tests/test_api_setup_ui.py`)
```text
Ran 9 tests in 2.506s: OK
- Modal initializes with 4 tabs including "ALEXA".
- All secret inputs remain masked in Password echo mode.
- Submitting valid Alexa configuration persists credentials to encrypted SecretStore and emits config_saved signal.
- Spotify, Google Workspace, and Gmail tests continue to pass without regression.
```

### Live Screenshot Gate
- Headless off-thread screenshot capture executed via `tests/render_alexa_tab_screenshot.py`.
- Rendered image saved to `docs/alexa/screenshots/api_connections_alexa_tab.png` and artifact path.
- Verified visual output:
  - All 4 tabs rendered with active theme palette.
  - Alexa status badge showing `READY TO LINK` in cyan.
  - Secret fields masked with password echo mode bullets.
  - Zero sensitive secrets or raw tokens in logs or labels.

---

## 4. Limitations & Open Questions
- Proceed to Phase 3: Alexa Custom Skill Contract (intent fixtures and mapping).
