---
type: "query"
date: "2026-09-28T13:23:10.610960+00:00"
question: "Why did completed screen monitoring issue duplicate stop calls?"
contributor: "graphify"
source_nodes: ["ScreenMonitorController", "._on_screen_monitor_completion()", "._analyze_screen_monitor_event()", "._stop_screen_monitor()"]
---

# Q: Why did completed screen monitoring issue duplicate stop calls?

## Answer

Expanded from original query via vocab: [screen, monitor, stop, stopped, completion, controller, event, analysis, active, tool]. The ScreenMonitorController already changes active to false and emits completion before JarvisLive analyzes the completion frame, but the completion prompt still instructed the AI to call screen_monitor stop. Split the prompt by completion_hint: locally completed runs now only verify and notify and explicitly do not call screen_monitor; active visual-change checks may stop exactly once. Added tests for the completion prompt and idempotent repeated helper stops.

## Source Nodes

- ScreenMonitorController
- ._on_screen_monitor_completion()
- ._analyze_screen_monitor_event()
- ._stop_screen_monitor()