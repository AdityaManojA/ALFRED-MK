# Phase 4 Notes: Modal UI (Tabbed Setup Panel)

**Date:** 2026-09-30
**Status:** Complete

---

## Changes Implemented

1. **`ui/setup_api_modal.py`**:
   * Implemented frameless glassmorphic `SetupApiModal(QDialog)` matching the active Batcomputer CRT theme tokens (`ThemeChrome.get_active().palette`).
   * **Tab Bar:** Top-level navigation between `[Google Workspace]`, `[Spotify API]`, and `[Gmail API]` with active theme accent highlights.
   * **Security & Masking:** All sensitive credential inputs use `QLineEdit.EchoMode.Password` with no plaintext echoing on focus or blur.
   * **Asynchronous Validation:** Validation runs on a background daemon thread (`BackendValidateThread`), signaling results back through Qt thread signals without dropping HUD paint frames.
   * **OAuth Triggering:** Direct `[AUTHORIZE WITH GOOGLE BROWSER]` button launches loopback OAuth flow seamlessly from the Google Workspace tab.
