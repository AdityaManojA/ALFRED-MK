---
type: "query"
date: "2026-09-28T14:14:45.979973+00:00"
question: "Remove Classic HUD mode from ALFRED MK-IV"
contributor: "graphify"
source_nodes: ["HudCanvas", "MainWindow", "get_hud_style", "save_hud_style"]
---

# Q: Remove Classic HUD mode from ALFRED MK-IV

## Answer

Expanded from original query via vocab: [hud, style, toggle, button, config, canvas, globe, face, core]. Removed the Classic HUD execution path and gear-drawer selector. HudCanvas now always initializes the speech-reactive renderer, all animation branches are unconditional, get_hud_style always returns reactive, and save_hud_style coerces every legacy or external value to reactive for compatibility. Verified a real MainWindow reports mode=reactive and has no classic toggle.

## Source Nodes

- HudCanvas
- MainWindow
- get_hud_style
- save_hud_style