# ALFRED-MK-V — Thematic HUD Overhaul: Phase 3 Notes

**Date:** 2026-09-29  
**Branch / Workspace:** ALFRED-MK-V  
**Knowledge Graph Nodes Referenced:**
- `core.ui.themes.catalog` (`core/ui/themes/catalog.py`)
- `core.ui.themes.registry` (`core/ui/themes/registry.py`)
- `ui_customizeoverlay` (`ui.py:L5359`)

---

## 1. New Interactive Themes (7 New Sourced Universes)

Phase 3 shipped 7 completely articulated interactive themes alongside the 3 existing ones, bringing the total theme count to 10. Each theme provides a full 24-token CRT palette, custom identity block, and peripheral chrome copy.

| Theme ID | Display Name | Accent Hex | Direction / Story | Threat Header | Subject Framing |
|---|---|---|---|---|---|
| `joker` | `JOKER` | `#b537f2` | Deranged acid purple, toxic smile green, and manic neon red alerts | `WHY SO SERIOUS` | `THE JOKER` / `ACE CHEMICALS • GOTHAM UNDERGROUND` |
| `riddler` | `RIDDLER` | `#00e676` | Obsessive emerald green, question-mark cipher styling, glowing cyan secondary | `RIDDLE DENSITY` | `EDWARD NIGMA // E.NYGMA` / `ENIGMA CRACKED // ARCHIVE` |
| `mr_freeze` | `MR. FREEZE` | `#00e5ff` | Glacial sub-zero cyan, crisp frost white, and deep cryo-chamber navy backing | `CORE TEMPERATURE` | `DR. VICTOR FRIES` / `GOTHAM COLD STORAGE • CRYO-LAB` |
| `harvey_two_face` | `HARVEY TWO-FACE` | `#ffb300` | Duality split: polished judicial brass gold vs charred scarred slate grey | `DOUBLE-ENTRY CHANCE` | `HARVEY DENT // TWO-FACE` / `50/50 COIN PROJECTION` |
| `catwoman` | `CATWOMAN` | `#e040fb` | Sleek jewel-thief violet, diamond white luminescents, and rooftop stealth black | `HEIST CONTINGENCY` | `SELINA KYLE // CAT` / `EAST END • ROOFTOPS GRID` |
| `arkham` | `ARKHAM ASYLUM` | `#76ff03` | Clinical containment green-grey, asylum hazard amber, and padded room obsidian | `INSANITY INDEX` | `INMATE // SEC-001` / `ELIZABETH ARKHAM ASYLUM FOR CRIMINALLY INSANE` |
| `watchtower` | `WATCHTOWER OMNI` | `#2979ff` | Orbital JL telemetry, ultra-clean star-field navy, solar gold and clean laser blue | `GLOBAL THREAT LEVEL` | `ORBITAL TAC-AI` / `JUSTICE LEAGUE • ORBITAL SATELLITE` |

---

## 2. Selection & Persistence Architecture
- **Stable IDs:** All theme IDs use strict snake_case format (`joker`, `riddler`, `mr_freeze`, `harvey_two_face`, `catwoman`, `arkham`, `watchtower`).
- **Emoji-Free Constraints:** Verified by unit test suite (`assertFalse(any(ord(c) > 0x2000 for c in theme.display_name))`).
- **Persistence Round-Trip:** Selection persists into `config/api_keys.json` under `"ui_color"` via `ThemeRegistry.get()`, surviving app restarts without loss of identity state.
