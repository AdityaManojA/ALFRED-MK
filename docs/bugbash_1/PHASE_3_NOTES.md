# Phase 3 — Browser Tab Close Fix (Bug 2)

## Root Cause Analysis
Previously, when the voice command `"close this tab"` was issued, the intent router only had `^close tab\b` in its fast path, missing `"close this tab"`. When handled or fallen back, if the frontmost window was ALFRED's HUD or an unrecognized window, no focus restoration took place, causing browser detection to fail or trigger fallback navigation routines which launched browser binaries or blank pages (`about:blank` / `chrome.exe`).

## Graphify Nodes Referenced
- `core/browser/commands.py` (new module)
- `close_active_tab() [src=core/browser/controller.py]`
- `BrowserController [src=core/browser/controller.py]`
- `close_tab() [src=actions/computer_settings.py]`
- `browser_control() [src=actions/browser_control.py]`
- `IntentRouter [src=core/intents/router.py]`
- `test_browser_controller.py [src=tests/test_browser_controller.py]`

## Changes Made
1. **Named Constants defined at top of files**:
   - `HOTKEY_CLOSE_WIN = ('ctrl', 'w')`
   - `HOTKEY_CLOSE_MAC = ('command', 'w')`
2. **Created `core/browser/commands.py`**:
   - Implemented `close_tab()` with pure keyboard automation.
   - Programmatically checks if ALFRED's HUD or python process is the foreground window; if so, enumerates top-level windows to focus the browser, or uses `Alt+Tab` (`pyautogui.hotkey('alt', 'tab')`) before issuing the tab close hotkey.
   - Executes `pyautogui.hotkey(*HOTKEY_CLOSE_WIN)` on Windows/Linux and `pyautogui.hotkey(*HOTKEY_CLOSE_MAC)` on macOS.
   - **Guaranteed zero subprocess execution**: Does NOT invoke `chrome.exe`, `subprocess.Popen`, or Playwright browser spawning when closing tabs.
3. **Updated `core/browser/controller.py`**:
   - Added `HOTKEY_CLOSE_WIN` and `HOTKEY_CLOSE_MAC`.
   - Integrated keyboard automation fallback to `core.browser.commands.close_tab` when driver reports no foreground browser.
4. **Updated `actions/computer_settings.py`**:
   - Bound `close_tab()` to invoke `core.browser.commands.close_tab()` with `HOTKEY_CLOSE_WIN` / `HOTKEY_CLOSE_MAC`.
5. **Updated `core/intents/router.py`**:
   - Updated `FAST_PATTERNS` regex to match `close this tab`, `close active tab`, `shut this tab`, and `kill tab`.
6. **Unit Tests**:
   - Added `test_intent_router_close_this_tab_fast_path` in `tests/test_browser_controller.py`.
   - Added `test_browser_commands_close_tab_hotkey_windows` in `tests/test_browser_controller.py`.
   - Added `test_browser_commands_close_tab_hotkey_mac` in `tests/test_browser_controller.py`.
   - All 10 tests passed.

## Verification
- Unit test suite: `py -3.12 -m unittest tests/test_browser_controller.py` -> 10 tests OK (0.274s).
