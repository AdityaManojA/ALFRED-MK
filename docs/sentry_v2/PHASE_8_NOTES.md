# Phase 8 Implementation Notes: System Prompt Updates

## 1. Objectives & Summary
Phase 8 aligns the agent's core model intelligence with the dual-mode architecture:
1. **System Prompt Alignment** (`core/prompt.txt`):
   - Added dedicated `[SENTRY MODE: MONITOR + FOCUS]` section teaching the LLM:
     - **MONITOR MODE**: Passive surveillance of terminal builds, downloads, or screen tasks; alerts on success/failure/silence via `sentry_monitor`.
     - **FOCUS MODE**: Proactive distraction defense; locks to app or tab; counts down session; nags on drift; reports streak via `sentry_focus`.
2. **Voice Intent Disambiguation**:
   - Explicitly mapped common user voice commands to exact tools and parameters:
     - *"watch this terminal"* -> `sentry_monitor(action="start", target="terminal")`
     - *"keep an eye on this build"* -> `sentry_monitor(action="start", target="build")`
     - *"watch the screen until it's done"* -> `sentry_monitor(action="start", target="screen")`
     - *"focus on this tab for 25 minutes"* -> `sentry_focus(action="start", duration_minutes=25)`
     - *"lock me in for an hour"* -> `sentry_focus(action="start", duration_minutes=60)`
     - *"lock on this tab"* -> `sentry_focus(action="lock_tab")`
     - *"drill sergeant mode"* -> `sentry_focus(action="drill_sergeant")`
     - *"gentle mode"* -> `sentry_focus(action="gentle")`
     - *"snooze" / "extend" / "excuse"* -> corresponding focus tool actions.
3. **Model Privacy Invariants**:
   - Instructs model NEVER to ask the user for URLs or window titles.
   - Clarifies that FocusState only ever conveys booleans and numerical counters.

## 2. Graphify References & Hot Paths
- `core.prompt.txt`: Primary system prompt governing model behavior.
- `actions.sentry_monitor`: Target tool for passive surveillance.
- `actions.sentry_focus`: Target tool for proactive distraction defense.

## 3. Verification & Test Suite
- `tests/sentry/test_prompt_sentry_v2.py`:
  - `test_sentry_section_exists`: Asserts `[SENTRY MODE: MONITOR + FOCUS]` exists.
  - `test_dual_mode_documentation`: Asserts both MONITOR and FOCUS are documented.
  - `test_tool_names_present`: Verifies tool names `sentry_monitor` and `sentry_focus`.
  - `test_voice_intents_documented`: Verifies all representative user phrases.
  - `test_structural_privacy_law_documented`: Verifies that strict privacy rules are encoded.
- All 22 Sentry tests and 27 Focus tests passing cleanly.
