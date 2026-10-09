# ALFRED-MK-V: Alexa Integration

## 1. Overview
The **Alexa Integration** links Amazon Echo devices and the Alexa mobile app with your ALFRED desktop assistant. It allows connected users to issue approved tactical voice directives (such as starting Focus sessions, controlling media, checking system telemetry, and running background speed tests) through their Echo devices.

## 2. Architecture

```text
Amazon Echo / Alexa App
         ↓ Voice Utterance
Amazon Alexa Custom Skill (Cloud)
         ↓ HTTPS POST (with signature & cert validation)
ALFRED Relay Server (server/alexa/)
         ↓ Authenticated WebSocket (WSS)
Desktop ALFRED App (core/integrations/alexa/)
         ↓ Safe Command Policy (AlexaActionPolicy)
Typed Dispatcher (AlexaTypedDispatcher)
         ↓
ALFRED Subsystems (Focus, Media, Telemetry, Network)
```

## 3. Key Design Principles
- **No Direct-Pairing Fiction**: Amazon Echo devices cannot pair locally with a desktop app over arbitrary Bluetooth/LAN APIs. Communication strictly routes through the supported Custom Skill + Relay architecture.
- **Outbound-Only Desktop Client**: The desktop app initiates an outbound WebSocket connection to the relay. No inbound ports, port-forwarding, or UPnP configuration are required on the user's router.
- **Strict Safe Command Policy**: Free-form raw speech text is never fed directly into code execution or shell commands. Every remote directive is evaluated by `AlexaActionPolicy` against an approved allowlist.
- **Zero Token Leakage**: State snapshots, speech replies, and logs are cryptographically scrubbed of access tokens, client secrets, and user IDs.

## 4. Documentation Index
- [User Setup Guide](file:///d:/Projects/Alfred-Mark-VIII/docs/alexa/USER_SETUP.md): 2-step setup process for end users.
- [Developer Setup Guide](file:///d:/Projects/Alfred-Mark-VIII/docs/alexa/DEVELOPER_SETUP.md): Custom skill creation, interaction model, account linking, and relay deployment.
- [Security & Privacy Guide](file:///d:/Projects/Alfred-Mark-VIII/docs/alexa/SECURITY.md): Threat model, signature validation, replay protection, and permission boundaries.
- [Verification Checklist](file:///d:/Projects/Alfred-Mark-VIII/docs/alexa/VERIFY.md): Complete audit matrix and test records.
