---
type: "query"
date: "2026-09-28T14:21:56.590178+00:00"
question: "change wake key to hey Alfred no t jarvis"
contributor: "graphify"
outcome: "useful"
source_nodes: ["WakeWordDetector", "is_ready", "install_and_download", "JarvisLive", "WAKE_PHRASE"]
---

# Q: change wake key to hey Alfred no t jarvis

## Answer

Expanded from original query via graph vocabulary: [wake, word, model, detector, alfred, sleep, audio, enabled]. Replaced the Hey Jarvis recognizer and all wake-facing messages with Hey Alfred, bundled and integrity-pinned an Alfred ONNX classifier, loaded it explicitly in WakeWordDetector, and added regression tests for phrase, model hash, and score routing. Validation passed with a real OpenWakeWord ONNX load and prediction.

## Outcome

- Signal: useful

## Source Nodes

- WakeWordDetector
- is_ready
- install_and_download
- JarvisLive
- WAKE_PHRASE