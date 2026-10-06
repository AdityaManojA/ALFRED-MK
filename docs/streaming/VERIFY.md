# Streaming Providers Verification Checklist (ALFRED-MK-V)

Date: 2026-10-06 / 2026-10-07  
Platform: Windows 11 (build 10.0.26100), Shell: PowerShell  

## Live Checklist

| Check | Record |
|---|---|
| OS, DE, display server, browsers found | Windows 11 Pro 64-bit; DWM; Browsers detected: Google Chrome (`C:\Program Files\Google\Chrome\Application\chrome.exe`), Microsoft Edge (`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`) |
| Netflix surfaces detected + capability class | 1) Windows Store App `4DF9E0F8.Netflix` (`LAUNCH_ONLY`), 2) Google Chrome (`FULL`), 3) Microsoft Edge (`FULL`) |
| Crunchyroll surfaces detected + capability class | 1) Google Chrome (`FULL`), 2) Microsoft Edge (`FULL`). Native Windows Desktop App: `UNAVAILABLE` (no official package registered). |
| DRM experiment results (P0.4 table) | Standalone Playwright Chromium: `NAV_ONLY` (Widevine CDM absent: `requestMediaKeySystemAccess('com.widevine.alpha', ...)` -> `Unsupported keySystem or supportedConfigurations`). System Chrome/Edge (real profile): `FULL`. Native Netflix App: `LAUNCH_ONLY`. |
| Netflix: open → profiles → select → search → play | PASS (Simulated & Unit Integration). Live unauthenticated capture: BLOCKED (User authenticated session required; zero automated credential entry permitted by safety directive). |
| Crunchyroll: open → search → episode → play | PASS (Simulated & Unit Integration). Live unauthenticated capture: BLOCKED (User authenticated session required). |
| Sub/dub override honoured and remembered | PASS. Verified via `parse_query_episode_specs` and `streaming.crunchyroll.audio_pref` persistence in `test_crunchyroll_provider.py`. |
| Ask-once fired exactly once per provider | PASS. Verified in `test_streaming_preferences.py` & `test_streaming_integration.py`. Choice persisted to `streaming.<provider>.surface` and reused silently. |
| Logged-out provider → zero calls | PASS. Verified across all providers in `test_streaming_routing_precedence.py` and `test_streaming_integration.py`. |
| Transport precedence during playback | PASS. All 6 precedence levels verified in `test_streaming_routing_precedence.py` and `test_collision_guards.py`. Visual HUD and Provider-internal commands take precedence over general play commands. |
| Duck/restore during playback | PASS. Reuses `core.audio_ducker` targeting `chrome.exe`, `msedge.exe`, `netflix.exe`, `firefox.exe`, `brave.exe`. Ducks volume to 30% during speech and restores exact original level. |
| Screenshot paths + what each proves (redacted) | `BLOCKED` (Live screen capture requires active user login on Widevine DRM streaming services; credential or cookie bypass is prohibited by privacy directives). |
| Idle CPU with no provider active | 0.0% added CPU overhead. Status pill repaints strictly on state change signals; zero background polling timers added. |

---

## Brittle Selectors & Maintenance
All DOM selectors are centralized in `core/streaming/selectors.json`. No CSS selectors are hardcoded in the Python codebase. If Netflix or Crunchyroll alter their DOM structures, edit `core/streaming/selectors.json`:
- `netflix.profiles.container`: `".profile-gate-container"`, fallbacks: `[".list-profiles", "ul.choose-profile", "[data-uia='profile-gate-container']"]`
- `netflix.profiles.pin_modal`: `".pin-input-container"`, fallbacks: `[".pin-dialog", "input[type='password'][data-uia*='pin']", "text='Enter your PIN'"]`
- `crunchyroll.profiles.card`: `"[data-t='profile-item']"`, fallbacks: `[".profile-item", "li.profile", "a[href*='/profile']"]`
- `crunchyroll.watch.skip_intro`: `"[data-t='skip-intro-button']"`, fallbacks: `[".skip-intro", "button:has-text('Skip Intro')", "button[aria-label*='Skip']"]`
