# Phase 1 Notes: Alexa Connection Model, State, Protocol & Policy

## 1. Graphify Citations

- State Manager & Snapshot:
  - `core/integrations/alexa/state.py` (`AlexaConnectionStatus`, `AlexaSnapshot`, `AlexaStateManager`)
- Protocol & Serialization:
  - `core/integrations/alexa/protocol.py` (`AlexaCommandEnvelope`, `AlexaResultEnvelope`, `parse_inbound_message`)
- Policy & Authorization:
  - `core/integrations/alexa/policy.py` (`AlexaActionPolicy`, `AlexaRiskLevel`, `AuthorizationDecision`, `AlexaContext`)
- Account Linking & Token Lifecycle:
  - `core/integrations/alexa/account_link.py` (`AccountLinkingManager`, `LinkingState`)
- Configuration & Timing Constants:
  - `core/integrations/alexa/config.py` (`AlexaConfig`, `load_alexa_config_from_store`, `save_alexa_config_to_store`)
- Outbound Relay Client:
  - `core/integrations/alexa/client.py` (`AlexaRelayClient`)
- Server Relay & Verification Package:
  - `server/alexa/verification.py` (`AlexaRequestVerifier`, `validate_certificate_url`, `validate_timestamp`, `validate_skill_id`, `RequestReplayCache`)
  - `server/alexa/relay.py` (`DesktopRelayBridge`)
  - `server/alexa/endpoint.py` (`create_alexa_app`)

---

## 2. Key Architecture & Constraints Met

1. **State Whitelist Privacy**:
   - `AlexaSnapshot` is a frozen dataclass containing only:
     - `status: AlexaConnectionStatus`
     - `configured: bool`
     - `linked: bool`
     - `relay_connected: bool`
     - `last_request_ok: bool`
     - `allowed_intent_count: int`
   - Verified that no access tokens, refresh tokens, user IDs, device IDs, URLs, or spoken requests are present in client state.
2. **Named Constants**:
   - `ALEXA_RELAY_CONNECT_TIMEOUT_S = 10.0`
   - `ALEXA_RECONNECT_BASE_S = 1.0`
   - `ALEXA_RECONNECT_MAX_S = 30.0`
   - `ALEXA_REQUEST_MAX_AGE_S = 150.0`
   - `ALEXA_COMMAND_TIMEOUT_S = 8.0`
   - `ALEXA_MAX_RESPONSE_CHARS = 700`
   - `ALEXA_CLOCK_SKEW_S = 30.0`
3. **Outbound Architecture**:
   - No inbound firewall or local listening port required on user desktop.
   - ALFRED connects outbound via persistent authenticated WebSocket to the relay.
4. **Idempotency & Replay Protection**:
   - Both client and server maintain bounded TTL caches preventing duplicate executions of request IDs.
5. **Strict Command Policy**:
   - Explicit denylist rejects shell, script execution, computer control, keyboard, mouse, screenshot, camera, file deletion, and shutdown directives.
   - Dynamic capability toggles permit immediate disablement of capabilities without relay reconnection.

---

## 3. Test Verification Output

### `tests/test_alexa_state.py`
```text
Ran 14 tests in 0.001s: OK
- Constants match platform directive exactly.
- State transitions (NOT_CONFIGURED -> READY_TO_LINK -> LINK_PENDING -> CONNECTED / OFFLINE -> ERROR) verified.
- Snapshot field whitelist and forbidden substring checks verified.
- Command and result envelope serialization and response truncation verified.
- Account linking single-use token consumption verified.
```

### `tests/test_alexa_verification.py`
```text
Ran 5 tests in 0.001s: OK
- Amazon HTTPS certificate URL validation verified.
- Timestamp freshness & 150s + 30s skew verified.
- Constant-time Skill ID comparison verified.
- Request replay detection verified.
- Consolidated verification pipeline verified.
```

### `tests/test_alexa_policy.py`
```text
Ran 5 tests in 0.000s: OK
- Default allowlist (telemetry, focus, media, speed, calendar) verified.
- Explicit denylist (shell, keyboard, screenshot, destructive) verified.
- Dynamic permission toggles verified.
- Dangerous argument injection rejection verified.
```

---

## 4. Limitations & Open Questions
- Next phase (Phase 2) will build the **Alexa** tab in `core/ui/setup_api_modal.py` and integrate it beside Google Workspace, Spotify, and Gmail.
