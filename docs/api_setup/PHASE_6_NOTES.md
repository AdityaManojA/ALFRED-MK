# Phase 6 Notes: Credential Injection into Tools

## Graphify Citations
- Target nodes: `actions.spotify_control:SpotifyClient._load_credentials`, `actions.gmail_manager:_load_gmail_creds`
- Integration: `core.secrets.store:get_secret_store`

## Implementation Summary
1. **Spotify Control (`actions/spotify_control.py`)**:
   - `SpotifyClient._load_credentials()` queries `get_secret_store()` first for `spotify.client_id`, `spotify.client_secret`, and `spotify.refresh_token`.
   - Preserves backward compatibility with `config/api_keys.json` and `os.environ`.
2. **Gmail Manager (`actions/gmail_manager.py`)**:
   - `_load_gmail_creds()` queries `get_secret_store()` first for `gmail.user` and `gmail.app_password` / `gmail.api_key`.
   - Preserves fallback to environment and config.
3. **Security & Non-Logging**:
   - Keys are never logged in clear text; missing credentials log a single clean warning without throwing unhandled exceptions.
