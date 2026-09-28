---
type: "query"
date: "2026-09-28T14:09:12.901845+00:00"
question: "Why does opening Alfred show the old UI with no switch to the speech-reactive HUD?"
contributor: "graphify"
source_nodes: ["HudCanvas", "MainWindow", "._refresh_hud_btn()", "._toggle_hud_style()", "get_hud_style", "save_hud_style"]
---

# Q: Why does opening Alfred show the old UI with no switch to the speech-reactive HUD?

## Answer

Expanded from original query via vocab: [hud, style, toggle, button, config, canvas, globe, face, core, launch, main, window]. Two causes were confirmed: HUD configuration still defaulted to removed face/core values and the old toggle was hidden, while the Windows J.A.R.V.I.S shortcut points to D:\Projects\Alfred-Mark-II. Changed Mark IV configuration to persisted reactive/classic modes with legacy migration, made reactive the default, added a visible accessible Reactive HUD selector to the gear drawer, and made HudCanvas switch immediately without reconstruction. The correct A.L.F.R.E.D shortcut already targets D:\Projects\Alfred-Mark-IV\main.py.

## Source Nodes

- HudCanvas
- MainWindow
- ._refresh_hud_btn()
- ._toggle_hud_style()
- get_hud_style
- save_hud_style