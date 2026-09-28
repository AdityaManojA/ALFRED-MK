# Phase 5 Implementation Notes: Deferred Lock, Settle Rule, Voice Routing & Card Trap

## 1. Objectives & Summary
Phase 5 addresses the critical human ergonomics and OS friction points of Focus Mode:
1. **OS Lock Prevention**: Guard against voice utterance 'lock on this tab' triggering 'lock_screen' (Win+L) in \ctions/computer_settings.py\.
2. **Deferred Lock Flow**: Allow users to trigger Focus Mode from ALFRED's HUD or voice without prematurely locking on ALFRED itself.
3. **Card Trap**: When clicking 'Lock on this tab' from the floating card or HUD, locate the top-most non-ALFRED browser window underneath using \EnumWindows\.
4. **Settle Rule**: Wait until the user lands on a target surface for 2 consecutive ticks before locking on; announce 'Locked on, sir.' Fallback to app-level lock after 45s on home base.
5. **Intent Prompting**: When starting deferred lock, prompt via \AnswerWindow\ ('Go to what you\'re working on and I\'ll lock on there. And what are we focusing on?'), record intent, and confirm ('Noted, sir.').

## 2. Graphify References & Hot Paths
- \ctions.computer_settings._detect_action\: Intercepted tab lock phrases to prevent triggering screen lock.
- \core.sentry.focus.engine.FocusEngine\: Added \_settle_count\, \_pending_target\, settle logic in \_tick()\, and \lock_current_surface()\.
- \core.sentry.focus.platform.win._find_top_browser_window\: Implemented enumeration to bypass ALFRED window when frontmost.
- \ctions.sentry_focus.run\: Added action \lock_tab\ (\lock_on_this_tab\).
- \main.py\: Registered \lock_tab\ action dispatching to \engine.lock_current_surface(from_card=False)\.

## 3. Verification & Test Suite
- \	ests/focus/test_deferred_lock.py\:
  - Verified deferred start from home-base with \AnswerWindow\ question.
  - Verified settle rule (2 ticks on non-home-base target locks on).
  - Verified 45-second fallback to app-level focus if user stays on home-base.
- \	ests/focus/test_voice_routing.py\:
  - Verified OS screen lock collision avoidance for all variations of 'lock on this tab'.
  - Verified 'lock the pc' / 'lock the screen' still executes screen lock.
  - Verified \lock_current_surface\ voice action behavior for tab, home-base, and app targets.
- All 18 Focus tests and 17 Sentry tests passing cleanly.
