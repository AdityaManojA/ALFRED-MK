# Phase 1 Notes: Uplink Transport Hardening

## Summary
Hardened the Windows Proactor asyncio event loop and websocket transport endpoints against unhandled `WinError 10054` / `ConnectionResetError` exceptions.

## Graphify Citations
- Node: `dashboard/server.py`
- Node: `main.py::AlfredApp::run`
- Node: `dashboard/static/app.html::initWebSocket`

## Key Implementation Details
1. **Loop Exception Handler in `main.py`:**
   - Installed `_proactor_exc_handler` on `self._loop` in `AlfredApp.run()`.
   - Benign proactor pipe teardown errors (`_call_connection_lost`, `WinError 10054`, `ConnectionResetError`) are captured and logged at debug level without full traceback spam.
2. **Hardened WebSocket Handlers in `dashboard/server.py`:**
   - Added named constants:
     - `RECONNECT_BASE_S = 2.0`
     - `RECONNECT_MAX_S = 30.0`
   - Added explicit `(WebSocketDisconnect, ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError, asyncio.CancelledError)` handlers in `ws_ep`, `audio_ws`, and `phone_audio_ws`.
3. **Client-side Reconnection Backoff in `dashboard/static/app.html`:**
   - Added `RECONNECT_BASE_S = 2.0` and `RECONNECT_MAX_S = 30.0`.
   - Exponential backoff kicks in on unexpected socket drops and resets cleanly upon successful connection.
