# Phase 3 Notes: Chat History on Uplink Connect

## Summary
Immediate chat history synchronization on WebSocket connection handshake to eliminate trickle delay and prevent duplicate speech playback for historic messages.

## Graphify Citations
- Node: `dashboard/server.py::ws_ep`
- Node: `dashboard/static/app.html::initWebSocket`
- Node: `dashboard/static/app.html::append`

## Key Implementation Details
1. **Named Constant:**
   - `UPLINK_HISTORY_N = 100` defined at the top of `dashboard/server.py`.
2. **Server-Side Push on Connect (`dashboard/server.py`):**
   - On new websocket connection in `ws_ep()`, `ledger._events[-UPLINK_HISTORY_N:]` is extracted and pushed immediately via `{"type": "history", "items": [...]}` before real-time event streaming starts.
3. **Client-Side Batch Rendering (`dashboard/static/app.html`):**
   - Handled `mType === 'history'` by batch-populating the chat feed.
   - Set `_initialHistoryLoaded = true` to ensure historical messages are displayed instantly without triggering client-side mobile TTS utterance audio.
