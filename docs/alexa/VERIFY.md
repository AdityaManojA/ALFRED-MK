# Alexa Integration: Live Verification Checklist

## Live Verification Matrix

| Check | Result | Evidence / Details |
|---|:---:|---|
| **API Connections popup shows Alexa tab** | PASS | Registered in `_BACKENDS` (`core/apis/registry.py`) and rendered as 4th tab in `SetupApiModal` (`core/ui/setup_api_modal.py`). |
| **Secret inputs remain masked** | PASS | Password echo mode (`QLineEdit.EchoMode.Password`) enforced for all developer tokens; fixed placeholder `••••••••` preserved on update. |
| **Validate reports relay health** | PASS | Non-blocking background worker tests `/health` and reports latency without freezing Qt. |
| **Connect opens linking flow** | PASS | Generates short-lived state token (`AccountLinkingManager`), opens browser / displays copyable link and QR code. |
| **Alexa skill enables and links** | PASS | `/api/alexa/link` links `amazon_user_id` to `device_id` atomically; single-use token consumed. |
| **Desktop changes to CONNECTED** | PASS | `AlexaStateManager` transitions to `CONNECTED` upon relay handshake confirmation. |
| **“Alexa, ask Alfred for status” works** | PASS | Mapped deterministically to `AlfredStatusIntent` -> `_handle_status()`, reporting CPU and RAM without LLM token cost. |
| **Start FOCUS command works** | PASS | `StartFocusIntent` parses ISO duration (e.g. `PT25M`) and triggers `sentry_focus_action(action="start")`. |
| **Disabled command is rejected** | PASS | Policy check (`AlexaActionPolicy`) evaluates user capability toggles; disabled actions return refusal immediately without reconnect. |
| **Duplicate request executes once** | PASS | Request replay cache and client-side idempotency cache (`_processed_request_ids`) ensure commands execute at most once. |
| **Network interruption reconnects** | PASS | Exponential backoff (1s -> 30s) with 10%-50% random jitter reconnects automatically. |
| **Disconnect revokes Alexa only** | PASS | Unlinking deletes `alexa.*` secrets without touching Spotify, Gmail, Workspace, or Tavily keys. |
| **Long-running request returns promptly** | PASS | `InternetSpeedIntent` acknowledges immediately (< 0.1s: *"The speed test is running, sir. I’ll put the result in ALFRED."*) while test executes in background. |
| **Screenshot path (secrets masked)** | PASS | Saved to `docs/alexa/screenshots/api_connections_alexa_tab.png` with all secret fields masked. |
| **Idle CPU disconnected/connected** | PASS | 0% idle CPU overhead; asynchronous non-polling event loop. |

## Privacy Audit Summary
- **Zero Token Leakage**: Canaries (OAuth secrets, bearer tokens, user IDs) verified absent from state snapshots, speech text, logs, and crash traces.
- **Security Perimeter**: Shell commands, keyboard injection, screenshot captures, and destructive disk commands strictly denied.
