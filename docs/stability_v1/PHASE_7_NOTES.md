# Phase 7 Notes: Screenshot Delivery to Uplink

## Summary
Reused the existing screenshot capture facility from `actions.screen_processor` to capture the desktop, save to Desktop and dashboard uploads, and deliver it to the mobile uplink as an inline viewable and downloadable file attachment.

## Graphify Citations
- Node: `actions/screen_processor.py::capture_screen`
- Node: `actions/computer_control.py::_screenshot`
- Node: `main.py::AlfredApp::_on_dashboard_action`
- Node: `dashboard/static/app.html::_onFileReceived`

## Key Implementation Details
1. **Named Constants (`actions/computer_control.py`):**
   - `SCREENSHOT_FORMAT: str = "png"`
   - `SCREENSHOT_MAX_MB: float = 10.0`
2. **Facility Reuse:**
   - Reused `actions.screen_processor.capture_screen(monitor=1)` rather than introducing redundant capture mechanisms.
   - Enforced `SCREENSHOT_MAX_MB` bounds check before writing to disk.
3. **Delivery Channel & UI Parity:**
   - Saved captured frame to `dashboard/uploads/alfred_screenshot_{ts}.png`.
   - In `_on_dashboard_action()`, broadcast `file_received` with `is_screenshot: True` so the mobile uplink appends the screenshot card inline with a direct `/uploads/...` download link.
