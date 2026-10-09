# Alexa Integration: Security & Privacy Specification

## 1. Threat Model & Defensive Boundaries

The Alexa integration bridges a cloud voice assistant with a desktop assistant. To prevent unauthorized execution or compromise of the host machine, ALFRED applies strict, defense-in-depth security boundaries.

---

## 2. Request Verification Standard

Every inbound request received at the webhook endpoint (`server/alexa/endpoint.py`) is verified against the official Amazon Skills Kit requirements:

1. **Certificate Chain URL Inspection**:
   - Scheme: must be strictly `https`.
   - Host: case-insensitive match for `s3.amazonaws.com`.
   - Path prefix: strictly begins with `/echo.api/`.
   - Port: strictly 443 if present.
2. **Timestamp Freshness**:
   - Compares request timestamp with relay server clock.
   - Max allowed request age is `ALEXA_REQUEST_MAX_AGE_S` (150s) + clock skew `ALEXA_CLOCK_SKEW_S` (30s).
   - Stale or skewed timestamps are rejected immediately.
3. **Skill ID Verification**:
   - Compared against configured Skill ID using constant-time string comparison (`hmac.compare_digest`) to prevent side-channel timing attacks.
4. **Replay Protection**:
   - An in-memory bounded TTL cache (`RequestReplayCache`) registers incoming `requestId`s. Duplicate IDs are rejected with HTTP 400.
5. **Payload Size Limits**:
   - Inbound HTTP payloads are capped at 64 KB (`OVERSIZED_PAYLOAD` -> HTTP 413).

---

## 3. Command Execution Policy & Allowlist

ALFRED never routes raw speech text from Alexa into general LLM tool calling. Directives are mapped deterministically via `AlexaActionPolicy`:

### Approved Allowlist:
- Telemetry & Status (`AlfredStatusIntent`, `system_status`)
- Calendar summary (`ScheduleStatusIntent`, without sensitive notes or attendee lists)
- Focus sessions (`StartFocusIntent`, `StopFocusIntent`)
- Media controls (`PauseMediaIntent`, `ResumeMediaIntent`)
- Network speed test (`InternetSpeedIntent` — acknowledged immediately, runs off-thread)
- Reminders (`SetReminderIntent`)

### Prohibited Denylist (Strictly Rejected):
- Arbitrary shell commands (`shell`, `cmd.exe`, `powershell`, `execute_script`)
- Desktop automation (keyboard injection, mouse clicking)
- Screen or webcam capture (`screenshot`, `screen_monitor`, `webcam`)
- Email reading or dispatching
- Clipboard reads and writes
- File modifications or deletions
- System shutdown or account changes

---

## 4. Zero Token Leakage & Data Privacy

1. **No Amazon Passwords**: ALFRED never requests, prompts for, or stores an Amazon password.
2. **Keyring & Encrypted Storage**: OAuth secrets and relay tokens are stored locally using AES-128 Fernet encryption via `core/secrets/store.py` (`~/.alfred/secrets.env`) with master keys protected by the operating system keyring.
3. **Sanitized Logs**:
   - Webhook logging records only hashed request IDs (`sha256(requestId)[:8]`).
   - Tokens, signatures, voice utterances, and user IDs are never written to logs or console output.
4. **Immutability of Visible State**:
   - `AlexaSnapshot` contains only status enums and boolean indicators.
5. **Disconnect Isolation**:
   - Clicking **DISCONNECT** wipes only `alexa.*` secrets. Unrelated keys for Spotify, Gmail, Google Workspace, and Tavily are preserved.
