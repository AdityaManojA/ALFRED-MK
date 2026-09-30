---
type: "query"
date: "2026-09-29T19:36:22.008769+00:00"
question: "Audit reliability and performance of the current working tree"
contributor: "graphify"
outcome: "useful"
source_nodes: ["main.py", "ui.py", "local_pipeline.py"]
---

# Q: Audit reliability and performance of the current working tree

## Answer

Expanded graph vocabulary: crash queue audio stream cache timer memory worker shutdown startup thread monitor. Used graph as navigation, then checked source and tests. Report: docs/audit-2026-09-30.md. Full run recorded 382 passed and 13 failed; concurrent source changes mean this is not an immutable baseline. Confirmed remaining issues include missing os names, duplicate local speech override, unscheduled warmup, worker crash reporting gap and quadratic mailto trimming. Benchmark tests passed. See report for isolated evidence and limitations.

## Outcome

- Signal: useful

## Source Nodes

- main.py
- ui.py
- local_pipeline.py