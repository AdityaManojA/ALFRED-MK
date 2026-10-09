# Phase 8 Notes: Long-Running Commands

## Status: COMPLETE

### 1. Overview
Implemented immediate verbal acknowledgment and background execution for operations that exceed Alexa's response window (e.g. speed tests, diagnostics).

### 2. Graphify Nodes & Target References
- Typed Dispatcher: [core/integrations/alexa/dispatcher.py](file:///d:/Projects/Alfred-Mark-VIII/core/integrations/alexa/dispatcher.py)
- Network Tools: [actions/network_tools.py](file:///d:/Projects/Alfred-Mark-VIII/actions/network_tools.py)
- Unit Tests: [tests/test_alexa_dispatcher.py](file:///d:/Projects/Alfred-Mark-VIII/tests/test_alexa_dispatcher.py)

### 3. Rules & Execution Model
1. **Immediate Spoken Acknowledgment**:
   - Long-running commands acknowledge in < 0.1s:
     > *"The speed test is running, sir. I’ll put the result in ALFRED."*
   - Never holds the Alexa HTTP connection open beyond the platform 8-second deadline.
2. **Background Execution**:
   - Task runs off-thread via `asyncio.create_task` and `actions.network_tools.network_tools_action`.
   - Results are logged to the ALFRED desktop HUD and uplink telemetry when finished.
3. **No False Promises**:
   - ALFRED does not claim Alexa will proactively speak the final result on the Echo device unless an authorized Proactive Events skill notification is explicitly supported and granted.

### 4. Verification Results
```text
test_long_running_speed_test_immediate_ack (tests.test_alexa_dispatcher.TestAlexaDispatcherAndPolicy) ... ok
Execution time: < 0.05 seconds to verbal return.
```
