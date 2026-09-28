---
type: "query"
date: "2026-09-28T14:53:12.057130+00:00"
question: "the hud text is quite hard to see"
contributor: "graphify"
outcome: "useful"
source_nodes: ["MinimizedHudOverlay", "TestMinimizedHudOverlay"]
---

# Q: the hud text is quite hard to see

## Answer

Expanded from graph vocabulary: [hud, overlay, text, font, color, transcript, window, style]. Increased the minimized overlay shell opacity and border contrast, added a nearly opaque transcript backing layer to prevent controls behind the overlay from bleeding through, changed transcript text to high-contrast white, selected a clear installed monospace family with cross-platform fallbacks, raised the transcript to 10pt medium weight, and added an accessible name. Native Windows rendering and six focused tests passed.

## Outcome

- Signal: useful

## Source Nodes

- MinimizedHudOverlay
- TestMinimizedHudOverlay