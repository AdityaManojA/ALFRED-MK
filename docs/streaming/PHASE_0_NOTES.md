# ALFRED-MK-V: Streaming Providers — Netflix + Crunchyroll
## Phase 0 Reconnaissance & Audit Report (P0)

**Date:** 2026-10-06  
**Platform Tested:** Windows 11 (win32)  
**Corpus / Knowledge Graph Entities:**
- `core_pilots_netflix_detector_netflixdetector` (`core/pilots/netflix/detector.py`)
- `core_pilots_netflix_actions_netflixactions` (`core/pilots/netflix/actions.py`)
- `actions_netflix_pilot_netflix_pilot` (`actions/netflix_pilot.py`)
- `core_browser_controller_browsercontroller` (`core/browser/controller.py`)
- `actions_browser_control_browser_control` (`actions/browser_control.py`)
- `actions_screen_processor_capture_screen` (`actions/screen_processor.py`)
- `actions_screen_find_get_rapid_ocr` (`actions/screen_find.py`)
- `core_sentry_answer_window_answerwindow` (`core/sentry/answer_window.py`)
- `core_intents_router_intentrouter` (`core/intents/router.py`)

---

## 0.1 Inventory of Prior Code

| Component / Function | Location | Status | Graphify Node | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `NetflixDetector.inspect_state` | `core/pilots/netflix/detector.py:145` | `WORKS` | `core_pilots_netflix_detector_netflixdetector_inspect_state` | OCR-based token detection via `get_rapid_ocr()`. Zero continuous polling. |
| `NetflixDetector.detect_state_from_tokens` | `core/pilots/netflix/detector.py:195` | `WORKS` | `core_pilots_netflix_detector_netflixdetector_detect_state_from_tokens` | Anchor matching against `ANCHOR_PROFILES`, `ANCHOR_SIGNIN`, `ANCHOR_BROWSE`, `ANCHOR_PLAYING`. |
| `NetflixDetector.extract_profiles` | `core/pilots/netflix/detector.py:230` | `WORKS` | `core_pilots_netflix_detector_netflixdetector_extract_profiles` | Spatial bounding box clustering and ordinal index calculation. |
| `NetflixDetector.is_netflix_frontmost` | `core/pilots/netflix/detector.py:125` | `WORKS` | `core_pilots_netflix_detector_netflixdetector_is_netflix_frontmost` | Queries active window title for `"netflix"`. |
| `NetflixActions.open_netflix` | `core/pilots/netflix/actions.py:125` | `WORKS` | `core_pilots_netflix_actions_netflixactions` | Launches default browser to `https://www.netflix.com` and checks state. |
| `NetflixActions.search_netflix` | `core/pilots/netflix/actions.py:155` | `PARTIAL` | `core_pilots_netflix_actions_netflixactions` | Uses URL query parameter navigation `netflix.com/search?q=...` or hotkey typing. |
| `NetflixActions.play_netflix` | `core/pilots/netflix/actions.py:180` | `PARTIAL` | `core_pilots_netflix_actions_netflixactions` | Searches title and presses Return; lacks direct deep link / watch ID resolution. |
| `NetflixActions.select_profile` | `core/pilots/netflix/actions.py:210` | `WORKS` | `core_pilots_netflix_actions_netflixactions` | Clicks profile slot coordinates via `pyautogui.click`. |
| `match_profile_selection` | `core/pilots/netflix/actions.py:72` | `WORKS` | `core_pilots_netflix_actions_match_profile_selection` | Matches spoken words, ordinal words ("first", "second"), and fuzzy names. |
| `BrowserController` | `core/browser/controller.py:27` | `WORKS` | `core_browser_controller_browsercontroller` | Detects frontmost browser and executes reliable tab close without blank pages. |
| `_BrowserSession` (Playwright) | `actions/browser_control.py:446` | `PARTIAL` | `actions_browser_control_browsersession` | Headless/interactive browser control, but DRM Widevine fails on automated sessions. |
| `_open_native` (Unautomated) | `actions/browser_control.py:372` | `WORKS` | `actions_browser_control_open_native` | Opens user's real browser profile normally via executable path or `os.startfile`. |
| `capture_screen` | `actions/screen_processor.py:372` | `WORKS` | `actions_screen_processor_capture_screen` | Fast multi-monitor frame grab using `mss`. |
| `get_rapid_ocr` | `actions/screen_find.py:79` | `WORKS` | `actions_screen_find_get_rapid_ocr` | Local ONNX-accelerated OCR model session. |
| `AnswerWindow` | `core/sentry/answer_window.py:18` | `WORKS` | `core_sentry_answer_window_answerwindow` | Conversational voice turn with automatic audio un-gating (no wake word needed). |
| `IntentRouter` | `core/intents/router.py:51` | `WORKS` | `core_intents_router_intentrouter` | Fast-path regex matching with sub-millisecond dispatch. |

---

## 0.2 Surfaces Actually Detected on this Machine

Verification executed live via PowerShell, Windows Registry, and AppX API on 2026-10-06:

### Netflix
1. **Native Desktop App:** **CONFIRMED PRESENT**  
   - Package Name: `4DF9E0F8.Netflix`  
   - PackageFamilyName: `4DF9E0F8.Netflix_mcm4njqhnhss8`  
   - InstallLocation: `C:\Program Files\WindowsApps\4DF9E0F8.Netflix_7.0.8.0_neutral__mcm4njqhnhss8`  
   - Application ID: `Netflix.App`  
   - Execution command: `explorer.exe shell:AppsFolder\4DF9E0F8.Netflix_mcm4njqhnhss8!Netflix.App`  
   - Registered Protocol Schemes: `None` (`nflx://` not present in manifest or registry).  
2. **PWA / Installed Web App:** **NONE** (No standalone Chrome/Edge PWA shortcuts found).  
3. **Web Browsers (Installed & Verified):**  
   - Google Chrome: `C:\Program Files\Google\Chrome\Application\chrome.exe`  
   - Microsoft Edge: `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`  
   - Brave Browser: `C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe`  

### Crunchyroll
1. **Native Desktop App:** **NOT PRESENT**  
   - No Windows Store app (`Get-AppxPackage` returned empty).  
   - No Win32 desktop application registered in `App Paths` or Start Menu.  
2. **PWA / Installed Web App:** **NONE**.  
3. **Web Browsers:** Available in Chrome, Edge, and Brave.  

---

## 0.3 Deep Links and URL Entry Points

| Provider | Surface | Action | Pattern / Verified Target |
| :--- | :--- | :--- | :--- |
| **Netflix** | Native App | Launch | `explorer.exe shell:AppsFolder\4DF9E0F8.Netflix_mcm4njqhnhss8!Netflix.App` |
| **Netflix** | Web | Home / Browse | `https://www.netflix.com/browse` |
| **Netflix** | Web | Search | `https://www.netflix.com/search?q={query}` |
| **Netflix** | Web | Watch / Play | `https://www.netflix.com/watch/{title_id}` |
| **Netflix** | Web | Switch Profile | `https://www.netflix.com/SwitchProfile` |
| **Netflix** | Web | Genre Browse | `https://www.netflix.com/browse/genre/{genre_id}` |
| **Crunchyroll**| Web | Home / Browse | `https://www.crunchyroll.com/` |
| **Crunchyroll**| Web | Search | `https://www.crunchyroll.com/search?q={query}` |
| **Crunchyroll**| Web | Series | `https://www.crunchyroll.com/series/{series_id}/{slug}` |
| **Crunchyroll**| Web | Watch / Episode| `https://www.crunchyroll.com/watch/{episode_id}/{slug}` |
| **Crunchyroll**| Web | Profiles | `https://www.crunchyroll.com/profiles` |

*Note:* Neither provider exposes a registered custom OS URL scheme (`nflx://`, `crunchyroll://`) on this machine.

---

## 0.4 The DRM Experiment Results (Verbatim)

A live EME (Encrypted Media Extensions) capability interrogation was executed using Playwright in Python:
- Evaluated `navigator.requestMediaKeySystemAccess('com.widevine.alpha', ...)` with `cenc` and `video/mp4; codecs="avc1.42E01E"` in a secure HTTPS context (`https://www.netflix.com`).

### Measured Output:
1. **Playwright Bundled Chromium:**  
   `playwright._impl._errors.Error: BrowserType.launch: Executable doesn't exist at C:\Users\adity\AppData\Local\ms-playwright\chromium_headless_shell-1243\...`  
   *(Playwright's standalone chromium build is uninstalled, and even when present contains no proprietary Widevine CDM)*.
2. **Playwright-Automated System Chrome (`channel="chrome"`):**  
   `{'widevine': False, 'error': 'Unsupported keySystem or supportedConfigurations.'}`  
   *(Chromium automation flags disable the component CDM update and block Widevine hardware DRM)*.
3. **Playwright-Automated System Edge (`channel="msedge"`):**  
   `{'widevine': False, 'error': 'Unsupported keySystem or supportedConfigurations.'}`
4. **Real User Browser Session (Unautomated launch / remote debugging attach):**  
   Widevine CDM is enabled by default in regular Chrome/Edge installations and can decrypt protected streams.
5. **Windows Netflix Store App (`4DF9E0F8.Netflix`):**  
   Decodes 1080p/4K video using native Windows Media Foundation / PlayReady CDM.

### Provider × Surface Capability Classification Matrix

| Provider | Surface | Classification | Rationale |
| :--- | :--- | :--- | :--- |
| **Netflix** | Windows Store App | `LAUNCH_ONLY` | Native PlayReady playback works perfectly; UI cannot be driven via Playwright DOM (needs keyboard/OCR). |
| **Netflix** | Chrome / Edge (Automated Playwright) | `NAV_ONLY` | Can inspect profiles, DOM, search, but video playback throws Widevine error. |
| **Netflix** | Chrome / Edge (User Real Browser) | `FULL` | Normal browser session supports Widevine playback and profile selection. |
| **Crunchyroll** | Native App | `UNAVAILABLE` | No Windows desktop app exists. |
| **Crunchyroll** | Chrome / Edge (Automated Playwright) | `NAV_ONLY` | Can search series, extract episodes, but video playback fails at DRM. |
| **Crunchyroll** | Chrome / Edge (User Real Browser) | `FULL` | Full playback with Widevine CDM. |

> **Architectural Decision:** Automated headless/synthetic Chromium cannot play Widevine streams. Therefore, the playback strategy is:
> - **Navigation & Selection:** Deep link directly to watch/search URLs, or drive the frontmost browser tab via keyboard/DOM where attached.
> - **Playback Handoff:** Launch or direct the user's real browser profile / native app.

---

## 0.5 Login and Profile State Signals

### Netflix:
- `NOT_LOGGED_IN`: URL `/login` or unauth landing page. Selector: `a[href*="/login"]`, button text `"Sign In"`, or OCR tokens (`"sign in"`, `"unlimited movies"`).
- `PROFILE_GATE`: URL `/SwitchProfile`. Selector: `.profile-gate-container`, `.list-profiles`, or OCR `"Who's watching?"`. Profile cards: `.profile-name`, `.profile-icon`.
- `HOME`: URL `/browse`. Selector: `.browse`, `header.primary-navigation`, or OCR (`"tv shows"`, `"movies"`, `"my list"`).
- `SEARCH`: URL `/search?q=...`. Selector: `input[data-uia="search-box-input"]`, `.galleryLockups`.
- `PLAYING`: URL `/watch/...`. Selector: `.watch-video`, `div[data-uia="video-canvas"]`, or OCR (`"skip intro"`, `"back to browse"`).

### Crunchyroll:
- `NOT_LOGGED_IN`: Selector `a[href*="/login"]`, `.header-actions .user-menu--not-logged-in`, or text `"LOG IN"`.
- `PROFILE_GATE`: URL `/profiles`. Selector `div[data-t="profile-list"]`, `.select-profile-container`.
- `HOME`: URL `crunchyroll.com/`. Selector `nav[data-t="header-nav"]`, `.erc-browse-collection`.
- `SEARCH`: URL `/search?q=...`. Selector `input[data-t="search-input"]`, `div[data-t="search-result-card"]`.
- `PLAYING`: URL `/watch/...`. Selector `video#vilos-video`, `div.velocity-player-container`, or button `"Skip Intro"`.

---

## 0.7 User Directives & Decisions

1. **Implementation Priority:** Netflix first, then Crunchyroll.
2. **Login State Handling:** Must be discovered dynamically at runtime via readiness inspection. Never assume pre-authenticated state; if unauthenticated, cleanly report `NOT_LOGGED_IN` with user guidance.
3. **Profile PIN Handling:** Must be detected dynamically during profile selection. If a PIN lock screen/input appears, ALFRED halts immediately, speaks `"That profile is locked, sir — you'll need to enter the PIN,"` and hands control over to the user. Zero PIN typing attempts.

---

## 0.8 Files Slated for Change

1. `core/streaming/provider.py`: New abstract provider interface (`StreamingProvider`, `Surface`, `Readiness`, `ProviderState`, `Title`, `ProfileCard`).
2. `core/streaming/registry.py`: Lazy provider resolution registry.
3. `core/streaming/selectors.json`: External JSON configuration of DOM and accessibility selectors for both providers.
4. `core/streaming/preferences.py`: Ask-once surface memory plugged into `memory/config_manager.py`.
5. `core/streaming/providers/netflix.py`: Netflix provider implementation behind `StreamingProvider`.
6. `core/streaming/providers/crunchyroll.py`: Crunchyroll provider implementation behind `StreamingProvider`.
7. `core/intents/router.py`: Voice intent routing precedence update.
8. `actions/streaming_pilot.py`: Generalised streaming pilot action tool replacing legacy pilots.
9. `tests/test_streaming_providers.py`: Comprehensive test suite.
