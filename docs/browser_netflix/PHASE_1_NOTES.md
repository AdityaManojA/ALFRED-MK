# Phase 1 Notes: Cross-Browser Control Core & Close Tab Fix

## 1. Summary of Changes
In this phase, we eliminated the bug where saying *"close tab"* opened a blank page (`about:blank`) and standardized tab/window control across Chrome, Brave, Edge, Firefox, Arc, Opera, and Safari.

### Graphify Entities Referenced:
- **`actions/browser_control.py`** [Community 18]
- **`actions/computer_settings.py`** [Community 80]
- **`core/sentry/focus/platform/`** [Community 80]
- **`_detect_action()`** [Node in Community 80]
- **`_BrowserSession`** [Node in Community 18]

---

## 2. Root Cause & Solution Architecture

### The Root Cause:
In `actions/browser_control.py`, native handling was restricted solely to:
```python
if action in ("go_to", "search", "new_tab"):
```
When `action == "close_tab"` arrived, execution fell through directly to:
```python
sess = _registry.get(browser)
```
This instantiated a Playwright persistent context on `about:blank`, created an empty browser window, and invoked `sess.close_tab()` on that newly spawned blank page. The user's active native browser was completely untouched, leaving an extra blank window behind.

### The Solution:
1. **Created `core/browser/` Suite:**
   - `core/browser/platform/base.py`: `BaseBrowserPlatformDriver` contract.
   - `core/browser/platform/win.py`: `WinBrowserDriver` using Win32 API (`keybd_event`) targeting virtual keys (`Ctrl+W`, `Ctrl+T`, `Ctrl+Tab`, `Ctrl+Shift+T`, `Alt+F4`) directly to the frontmost browser HWND.
   - `core/browser/platform/mac.py`: `MacBrowserDriver` targeting the frontmost browser via clean AppleScript (`tell application "..." to close active tab of front window`), falling back to System Events keystrokes.
   - `core/browser/platform/linux.py`: `LinuxBrowserDriver` utilizing `xdotool` and `xprop` targeting the active window ID.
   - `core/browser/controller.py`: `BrowserController` orchestrating tab and window primitives (`close_active_tab`, `new_tab`, `switch_tab`, `reopen_closed_tab`, `close_window`).

2. **Intercepted Tab/Window Actions in `actions/browser_control.py`:**
   Tab actions (`close_tab`, `switch_tab`, `reopen_closed_tab`, `close_window`, and parameterless `new_tab`) now check whether an automated Playwright session is actively being managed. If not, they route directly to `core.browser.controller` using the OS-native driver. No Playwright contexts or `about:blank` windows are ever spawned.

3. **Updated Intent Routing & Collision Guards in `actions/computer_settings.py`:**
   - Added `close_tab` and `reopen_tab` phrases to `_ALIASES`:
     - `"close tab"`, `"close this tab"`, `"shut this tab"`, `"kill tab"`, `"close active tab"` -> `close_tab`
     - `"reopen tab"`, `"reopen closed tab"`, `"undo close tab"` -> `reopen_tab`
   - Added guard in `_detect_action()` to prevent `"close this tab"` from colliding with `"close_window"` (`"close this"`).
   - Delegated `close_tab()`, `new_tab()`, `next_tab()`, `prev_tab()`, and `reopen_closed_tab()` to `core.browser.controller`.

---

## 3. Verification & Test Results
- Unit test suite `tests/test_browser_controller.py`:
  - `test_controller_delegates_to_driver`: PASSED
  - `test_mac_driver_applescript_generation`: PASSED
  - `test_linux_driver_xdotool`: PASSED
  - `test_win_driver_constants`: PASSED
  - `test_close_tab_aliases`: PASSED
  - `test_reopen_tab_aliases`: PASSED
  - `test_browser_control_action_close_tab_no_playwright_spawn`: PASSED
- Voice and text intents map cleanly without opening blank windows.
