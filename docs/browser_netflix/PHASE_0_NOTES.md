# Phase 0 Reconnaissance Notes: Browser Suite & Netflix Pilot

**Date:** 2026-09-30  
**Repository:** ALFRED-Mark-V  
**Knowledge Graph Entities:**  
- `actions_browser_control_browser_control` (Community 5 — `actions/browser_control.py:L932`)
- `actions_browser_control_browsersession_close_tab` (`actions/browser_control.py:L801`)
- `actions_browser_control_browsersession_launch` (`actions/browser_control.py:L531`)
- `actions_computer_settings_close_tab` (`actions/computer_settings.py:L322`)
- `actions_screen_processor_capture_screen` (Community 188 — `actions/screen_processor.py:L270`)
- `actions_screen_find_get_rapid_ocr` (Community 77 — `actions/screen_find.py:L79`)
- `core_sentry_focus_platform_win_winplatformreader` (`core/sentry/focus/platform/win.py:L35`)
- `core_sentry_answer_window_answerwindow` (Community 143 — `core/sentry/answer_window.py:L18`)

---

## 1. The "Close Tab" Bug Analysis

### Intent Routing Path
1. **Tool Self-Declaration:**
   `actions/browser_control.py` declares the tool `browser_control` via `TOOL` at lines 1070–1120. In the parameters schema:
   ```json
   "action": {
       "type": "STRING",
       "description": "go_to | search | click | type | scroll | fill_form | smart_click | smart_type | get_text | get_url | press | new_tab | close_tab | screenshot | back | forward | reload | switch | list_browsers | close | close_all"
   }
   ```
2. **Model Invocation:**
   When the user utters *"close tab"* or *"close this tab"*, the LLM invokes `browser_control(action="close_tab")`.

### Root Cause: Why it opens a blank page
1. In `actions/browser_control.py`, simple native navigation actions are handled at line 971:
   ```python
   # Line 971
   if action in ("go_to", "search", "new_tab"):
   ```
   `"close_tab"` is **omitted** from this native branch.
2. As a result, execution falls through to line 1007:
   ```python
   # Line 1007
   sess = _registry.get(browser)
   ```
3. `_registry.get(browser)` instantiates a `_BrowserSession` which calls `sess.start()`, initiating Playwright `launch_persistent_context` at line 550 / 557 / 573 / 603.
4. Line 637 opens a fresh blank page (`about:blank`):
   ```python
   # Line 636-637:
   if self._page is None or self._page.is_closed():
       self._page = await self._context.new_page()
   ```
5. Line 1040–1041 then calls `sess.close_tab()`:
   ```python
   elif action == "close_tab":
       result = sess.run(sess.close_tab())
   ```
   **The flaw:** Playwright spawns a completely new browser window on `about:blank`, attaches to it, closes that new tab, and leaves behind the user's real browser completely untouched while popping up a blank page/window!
6. **Secondary route bug in `actions/computer_settings.py`:**
   `close_tab()` at line 322 sends `pyautogui.hotkey("ctrl", "w")` without validating if the frontmost window is actually a browser HWND/PID, and `"close_tab"` is completely missing from `_ALIASES` (line 685).

---

## 2. Current Browser Automation Architecture

### Libraries in Use
1. **Playwright (`actions/browser_control.py`):**
   - Drives Chromium, Firefox, and WebKit through `playwright.async_api.async_playwright()`.
   - Used for headless/interactive scraping and automation sessions (`_BrowserSession`).
2. **PyAutoGUI (`actions/computer_settings.py`):**
   - Blind global keyboard shortcuts (`pyautogui.hotkey("ctrl", "w")`, `pyautogui.hotkey("command", "w")`). Lacks window-targeting, PID awareness, or OS-native accessibility APIs.
3. **OS-Native Inspection in Sentry Focus Engine:**
   - **Windows:** `core/sentry/focus/platform/win.py` uses Win32 API (`ctypes.windll.user32`) and UI Automation (`uiautomation` / `IUIAutomation`).
   - **macOS:** `core/sentry/focus/platform/mac.py` uses `lsappinfo` and AppleScript (`osascript`).
   - **Linux:** `core/sentry/focus/platform/linux.py` uses `xdotool` / `xprop` for X11 and Wayland compositor readers.

### Currently Detected Browsers
- **Windows (`KNOWN_BROWSERS`):** `chrome.exe`, `msedge.exe`, `brave.exe`, `firefox.exe`, `opera.exe`, `vivaldi.exe`, `arc.exe`.
- **macOS (`KNOWN_MAC_BROWSERS`):** `com.google.Chrome`, `com.brave.Browser`, `com.microsoft.edgemac`, `company.thebrowser.Browser` (Arc), `org.mozilla.firefox`, `com.apple.Safari`.
- **Linux (`KNOWN_LINUX_BROWSERS`):** `google-chrome`, `chromium`, `firefox`, `brave-browser`, `microsoft-edge`.

---

## 3. Desktop Screen Capture & Inspection Facilities

1. **Desktop Capture:**
   - Central implementation: `actions/screen_processor.py::capture_screen(monitor=1)` (Node ID: `actions_screen_processor_capture_screen`).
   - Uses `mss` for high-speed, zero-copy multi-monitor frame grabbing (<30 ms), converting to PIL RGB image and returning a hybrid payload with active window title and dimensions.
2. **OCR Engine:**
   - Local ONNX-accelerated OCR: `actions/screen_find.py::get_rapid_ocr()` (Node ID: `actions_screen_find_get_rapid_ocr`) backed by `rapidocr_onnxruntime`.
   - Pre-warmed detection and recognition sessions operating in ~75–95 ms without cloud dependency.
3. **UI Automation / Tree Reader:**
   - Windows: `WinPlatformReader._read_uia_address_bar` utilizes `uiautomation` library.
   - macOS: AppleScript front-window query capabilities in `MacPlatformReader`.

---

## 4. Single-Utterance Conversational Answer Window

- Implemented in `core/sentry/answer_window.py` (Class: `AnswerWindow`, Node ID: `core_sentry_answer_window_answerwindow`).
- **Mechanism:**
  1. Speaks the conversational prompt (e.g. *"Which profile shall I select, sir?"*) using `self._speak_fn`.
  2. Un-gates the audio recording pipeline (`self._un_gate_fn(True)`), enabling STT transcription without requiring the user to speak the wake word (*"Alfred"* / *"Jarvis"*).
  3. Registers itself in `core.registry` as `"active_answer_window"`.
  4. Waits asynchronously (`await asyncio.wait_for(...)`) or synchronously via `threading.Event` up to `timeout_s = ANSWER_WINDOW_S` (default 8.0s).
  5. Upon receiving speech transcription from Live API, local STT, or UI typed input, `submit_answer(text)` resolves the future/event and closes the window.

---

## 5. Proposed Architecture & Package Layout

```
core/browser/
├── __init__.py
├── controller.py       # Cross-platform browser controller (close_active_tab, new_tab, etc.)
└── platform/
    ├── __init__.py
    ├── win.py          # Win32/UIA frontmost browser verification and virtual keys
    ├── mac.py          # AppleScript front-browser tab control and fallback hotkeys
    └── linux.py        # xdotool / Wayland frontmost browser tab control
core/pilots/
└── netflix/
    ├── __init__.py
    ├── detector.py     # On-demand NetflixState detection (NOT_LOGGED_IN, PROFILE_GATE, BROWSE_HOME, PLAYING)
    └── actions.py      # Profile selection dialog, search execution, playback trigger
```

---
*Ready to proceed to Phase 1.*
