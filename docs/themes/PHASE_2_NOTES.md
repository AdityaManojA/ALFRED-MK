# ALFRED-MK-V — Thematic HUD Overhaul: Phase 2 Notes

**Date:** 2026-09-29  
**Branch / Workspace:** ALFRED-MK-V  
**Knowledge Graph Nodes Referenced:**
- `ui_subjectdossiercard` (`ui.py:L2820`)
- `ui_crtreconwidget` (`ui.py:L2600`)
- `ui_biometricfingerprintwidget` (`ui.py:L2658`)
- `ui_wireframeposewidget` (`ui.py:L2746`)
- `core.ui.themes.catalog` (`core/ui/themes/catalog.py`)

---

## 1. Deepening Existing Themes

Rather than treating themes as superficial color swaps, each existing skin now drives complete contextual narrative framing across top-right identity and peripheral HUD widgets.

### 1.1 Default Batcave (`dossier`)
- **Accent Hex:** `#8e9bff` (CRT Phosphor Lavender)
- **Palette Story:** Deep CRT obsidian backing (`#090a12`), cool steel paneling (`#0d0f1e`), phosphorescent lavender accents (`#8e9bff`), and restrained threat crimson (`#ff2a55`). Contrast tuned for high legibility (> 10:1 text on bg).
- **Identity Block:**
  - Subject Label: `SUBJECT A-34`
  - Subject Value Mode: `SubjectValueMode.KEEP_REAL` (truthfully displays configured assistant name)
  - Threat Header: `THREAT ASSESSMENT`
  - Threat Levels: Clear `★★★`, Low `★☆☆`, Elevated `★★☆`, Critical `★★★`
  - Affiliation: `WAYNE ENTERPRISES • BATCOMPUTER`
- **Peripheral Chrome:**
  - Status Prefix: `SYS:`
  - Recon Scanner Header: `● ● ●  RECON FEED // OPTICAL`
  - Biometric Badge: `VERIFIED // ALPHA-1`
  - Pose Header: `TELEMETRY // POSE TRACK`
  - Idle Readout: `TARGET ACQUIRED: LOCAL`

### 1.2 Bane Mode (`vector`)
- **Accent Hex:** `#a8ff3e` (Venom Green)
- **Palette Story:** Toxin-saturated emerald green (`#a8ff3e`), deep swamp obsidian (`#060d07`), bruised panel shadows (`#0f2613`), toxic amber alerts (`#ffaa33`), and hazard red (`#ff3838`).
- **Identity Block:**
  - Subject Label: `SUBJECT — VENOM`
  - Subject Value Mode: `SubjectValueMode.KEEP_REAL` (retains real operator name)
  - Threat Header: `DOMINANCE ASSESSMENT`
  - Threat Levels: Clear `SUPPRESSED`, Low `SUBDUED`, Elevated `SURGING`, Critical `BREAK THE BAT`
  - Clearance: `OVERRIDE // LEVEL-Ω`
  - Affiliation: `PEÑA DURA • LEAGUE OF SHADOWS`
- **Peripheral Chrome:**
  - Status Prefix: `VENOM:`
  - Recon Scanner Header: `● ● ●  SURVEILLANCE GRID // OVERRUN`
  - Biometric Badge: `OVERRIDE // LEVEL-Ω`
  - Pose Header: `KINETIC MASS TRACKER`
  - Idle Readout: `OCTANE FLOW // MAXIMUM READY`

### 1.3 Batman Beyond (`beyond`)
- **Accent Hex:** `#ff003c` (Neo-Gotham Crimson)
- **Palette Story:** High-contrast pitch black backing (`#050508`), stark carbon panels (`#0a0a10`), searing Beyond red (`#ff003c`), cold cyber blue secondary (`#00e5ff`), and neon amber telemetry (`#ffaa00`).
- **Identity Block:**
  - Subject Label: `CALLSIGN — BEYOND`
  - Subject Value Mode: `SubjectValueMode.KEEP_REAL` (retains real operator name)
  - Threat Header: `CITY THREAT MATRIX`
  - Threat Levels: Clear `PATROL STABLE`, Low `GANG DISPERSED`, Elevated `JOKERZ CONVERGING`, Critical `MAX GOTHAM ALERT`
  - Clearance: `WAYNE TECH // CLEARANCE ZERO`
  - Affiliation: `WAYNE-POWERED • NEO-GOTHAM GRID`
- **Peripheral Chrome:**
  - Status Prefix: `BEYOND:`
  - Recon Scanner Header: `● ● ●  OPTICAL DRONE MATRIX // FEED`
  - Biometric Badge: `WAYNE TECH // CLEARANCE ZERO`
  - Pose Header: `EXOSUIT TELEMETRY // RIG`
  - Idle Readout: `TERRY CALLSIGN LOCKED`

---

## 2. Layout & Geometry Invariants
- **No HUD reflow:** The `SubjectDossierCard` preserves an exact 7-row specification with fixed line heights and corner bracket arms.
- **Data Truthfulness:** Live operational data (CPU/RAM/GPU telemetry bars, Sentry focus countdown timer, and screen monitor active status) remain 100% factual. Thematic wording applies strictly to headers, badges, empty states, and framing copy.
