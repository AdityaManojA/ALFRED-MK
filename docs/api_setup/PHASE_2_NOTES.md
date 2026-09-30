# Phase 2 Notes: API Backend Registry & Format Validators

**Date:** 2026-09-30
**Status:** Complete

---

## Changes Implemented

1. **`core/apis/registry.py`**:
   * Defined `APIBackend` dataclass with `required_fields`, `optional_fields`, and validation hooks.
   * Registered 3 primary backends:
     1. **Google Workspace**: Validates Google Client ID (`.apps.googleusercontent.com` / length) and Client Secret.
     2. **Spotify API**: Validates 32-character alphanumeric Spotify Client ID and Client Secret.
     3. **Gmail API**: Supports dual mode: App Password (email regex + 16-char token) or OAuth credentials JSON structure (`installed` / `web` block with `client_id` & `client_secret`).
   * Implemented `save_backend_credentials()` to validate and persist fields directly to the encrypted `SecretStore`.
   * Implemented `get_configured_backends_count()` to report `(configured, total)` for the UI status badge.

2. **`tests/test_api_registry.py`**:
   * Unit tests verifying backend schemas, format validation rules (positive & negative cases), and encrypted storage integration.
