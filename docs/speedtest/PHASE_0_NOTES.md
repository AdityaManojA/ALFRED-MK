# Phase 0 Reconnaissance Notes — Fast.com Speed Test Tool

## 1. Objective & Scope
Enable ALFRED to handle voice and text queries like *"what's my internet speed"*, running a headless browser speed test on `https://fast.com/`, extracting both download and upload speeds, acknowledging immediately without blocking the event loop or triggering Gemini Live API timeouts, and speaking the results in ALFRED persona (*"Download is 320 megabits, upload is 45, sir."*).

---

## 2. Graphify Knowledge Graph References
* `_speedtest_cli() [src=actions/network_tools.py loc=L44 community=network_tools.py]`
* `network_tools_action() [src=actions/network_tools.py loc=L126 community=network_tools.py]`
* `runner.py [src=core/tools/runner.py loc=L1 community=dataclasses]`
* `execute_bounded_tool() [src=core/tools/runner.py loc=L78 community=dataclasses]`
* `ToolExecutionMetrics [src=core/tools/runner.py loc=L42 community=dataclasses]`
* `SpeculativePrefetcher [src=core/intents/fastpath.py loc=L49 community=SpeculativePrefetcher]`
* `PrefetchRecord [src=core/intents/fastpath.py loc=L37 community=SpeculativePrefetcher]`
* `IntentRouter [src=core/intents/router.py loc=L51 community=IntentRouter]`
* `FAST_PATTERNS [src=core/intents/router.py loc=L55 community=IntentRouter]`
* `discover_actions [src=core/action_loader.py loc=L168 community=main.py]`
* `_BEHAVIORS / _SCHEDULING [src=core/action_loader.py loc=L48-L49]`
* `_dispatch_tool [src=main.py loc=L2153 community=AlfredLive]`
* `_execute_tool [src=main.py loc=L2394 community=AlfredLive]`

---

## 3. Findings Across Recon Areas

### 3.1. Automation Stack
* **Installed Packages:**
  * `playwright`: **Installed** (`playwright>=1.40.0` in Python 3.12 environment).
  * `pyautogui`: **Installed**.
  * `selenium`: **Not installed** (not needed).
* **Browser Runtime & Headless Execution:**
  * Running vanilla `p.chromium.launch(headless=True)` attempts to look for the Playwright standalone bundled browser cache at `%LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1243`.
  * Verified live execution with system channels:
    * `p.chromium.launch(channel="msedge", headless=True)`: **SUCCESS** (Edge version 154.0.4258.53 launch verified).
    * `p.chromium.launch(channel="chrome", headless=True)`: **SUCCESS** (Chrome version 154.0.8037.98 launch verified).
  * **Architecture Decision:**
    In `FastDotComTester`, attempt launching with `channel="msedge"` or `channel="chrome"` first (instant zero-download execution using the host's existing modern evergreen browser), falling back to standard Chromium. This avoids forcing a 150MB+ download unless neither browser exists.

### 3.2. Tool Dispatcher & Long-Running Async UX
* **The Timeout Problem:** Fast.com requires 15–30 seconds for download measurement + clicking `#show-more-details-link` + waiting for upload to settle. Holding a synchronous Gemini Live function call response open for 30 seconds can cause websocket timeout or stalled turns.
* **Current Infrastructure Patterns:**
  1. `core/tools/runner.py`:
     * Defines `execute_bounded_tool()` with `FAST_TOOL_PLACEHOLDERS`.
     * If execution exceeds timeout, it returns a fast placeholder to Gemini (`"Testing your connection, sir. This will take a moment."`), shields the background coroutine, and executes `on_background_finish(tool_name, bg_res)`.
  2. `core/action_loader.py` & `main.py`:
     * `ActionRecord` supports `behavior="NON_BLOCKING"` and `scheduling="WHEN_IDLE"`.
     * `_dispatch_tool` passes context `_ctx = {"player": self.ui, "speak": self.speak, ...}` to action handlers.
     * When triggered via Gemini tool call: The tool handler can return an immediate acknowledgment: `"Speed test started in background. I will notify the user when done."`, then spin off the worker thread (`threading.Thread` or `asyncio.create_task`).
     * When the worker finishes: It emits a HUD toast / chat log (`player.write_log(...)`) and calls `speak("Download is X megabits, upload is Y, sir.")`.

### 3.3. Intent Fast-Path
* **`core/intents/fastpath.py` (Speculative Prefetch):**
  * Speculative prefetch is designed strictly for zero-side-effect, read-only lookups (DNS, time, system status).
  * Running a speedtest speculatively on partial speech would waste bandwidth. Therefore, speedtest must be flagged as `NOT_PREFETCHABLE`. If prefetch touches it at all, it should only warm up the browser module or context, never launch navigation.
* **`core/intents/router.py` (Deterministic Fast-Path):**
  * `IntentRouter.FAST_PATTERNS` can register regex patterns:
    * `r"^(what('s| is) (my )?(internet|connection|network) speed|how fast is my (internet|connection)|speed test|test my internet)\b"`
  * When matched on the fast path: ALFRED directly speaks the immediate verbal acknowledgment (*"Testing your connection, sir. This will take a moment."*), launches the background test, and announces the results upon completion without needing an LLM round-trip.

---

## 4. Exact Files to Touch Across Phases

1. **Phase 1: Headless Fast.com Scraper**
   * `core/tools/speedtest.py` *(New)*: Implementation of `FastDotComTester` with Playwright headless automation, DOM mutation listeners (`#speed-value`, `#show-more-details-link`, `#upload-value`), error handling, and named constants (`FAST_COM_URL`, `TEST_TIMEOUT_S = 45`).
   * `tests/test_fast_dot_com_speedtest.py` *(New)*: Standalone unit test verifying scraper output and mock fallbacks.

2. **Phase 2: Tool Integration & Async UX**
   * `actions/network_tools.py`: Update `speed_test` action handler to invoke `FastDotComTester` in a background thread, return an immediate acknowledgment, and trigger `speak()` / UI log upon completion.
   * `core/tools/runner.py`: Add `"speed_test"` / `"network_speed"` to `FAST_TOOL_PLACEHOLDERS`.

3. **Phase 3: Voice Routing & Fast Path**
   * `core/intents/router.py`: Add regex patterns for voice intent matching.
   * `core/intents/fastpath.py`: Ensure speed test is explicitly marked non-prefetchable.

4. **Phase 4: Tests, Docs, Graphify**
   * `tests/test_speedtest_tool.py` *(New)*: End-to-end tool integration tests.
   * `docs/speedtest/VERIFY.md` *(New)*: Verification checklist.
   * Run `graphify update .` in final phase only.
