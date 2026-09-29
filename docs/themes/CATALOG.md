# ALFRED-MK-V — Theme Catalog (`docs/themes/CATALOG.md`)

This document is the canonical reference catalog for all selectable themes in ALFRED-MK-V.
Every theme is a complete contextual skin defined in `core/ui/themes/catalog.py` complying with the `ThemeDefinition` schema.

---

## Data vs. Presentation Rules (Universal Across All Themes)

- **Real Telemetry:** CPU %, Memory %, Network KB/s, GPU %, and Temperature readouts are factual system telemetry and never falsified.
- **Focus Countdown & Timers:** Sentry focus remaining duration (`FOC mm:ss`) and drift alerts reflect true timer countdowns.
- **Threat Level Mapping:** The Threat Assessment row dynamically reflects live HUD state:
  - **Benign HUD Idle:** Displays the theme's `clear` level display name.
  - **Active Monitoring / Focus:** Displays the theme's `elevated` level display name.
  - **Focus Drifting (Distracted):** Displays the theme's `critical` level display name.
- **Subject Display:** When `subject_value_mode == keep_real`, the user's configured assistant name is shown; when `thematic_codename`, the theme's character codename is shown. User desktop credentials are never exfiltrated.

---

## 1. DEFAULT BATCAVE (Wayne Classic)
- **ID:** `dossier`
- **Display Name:** `DEFAULT BATCAVE`
- **Tagline:** Standard Wayne Enterprises CRT interface with phosphor lavender accents
- **Primary Accent:** `#8e9bff` | **Background:** `#090a12`
- **Palette Story:** Authentic CRT obsidian floor, cool steel panels, electric phosphor lavender accent bloom, tactical crimson threat highlights.
- **Top-Right Identity:**
  - Subject Label: `SUBJECT A-34`
  - Codename: `ALFRED`
  - Subject Mode: `keep_real`
  - Threat Header: `THREAT ASSESSMENT`
  - Threat Levels: Clear `★★★`, Low `★☆☆`, Elevated `★★☆`, Critical `★★★`
  - Clearance: `VERIFIED // ALPHA-1`
  - Affiliation: `WAYNE ENTERPRISES • BATCOMPUTER`
- **Chrome Copy:**
  - Status Prefix: `SYS:`
  - Recon Header: `● ● ●  RECON FEED // OPTICAL`
  - Telemetry Header: `SYS TELEMETRY`
  - Tabs: `[ ◈ ]  TELEMETRY` / `[ ▤ ]  INTEL // NOTES`
  - Idle Readout: `TARGET ACQUIRED: LOCAL`

---

## 2. BANE MODE (Venom Protocol)
- **ID:** `vector`
- **Display Name:** `BANE MODE`
- **Tagline:** Heavy venom green CRT tactical terminal engineered for dominance
- **Primary Accent:** `#a8ff3e` | **Background:** `#060d07`
- **Palette Story:** Brutalist venom-pumping toxic lime, deep swamp shadows, toxin hazard amber, bruised charcoal secondary.
- **Top-Right Identity:**
  - Subject Label: `SUBJECT — VENOM`
  - Codename: `BANE`
  - Subject Mode: `keep_real`
  - Threat Header: `DOMINANCE ASSESSMENT`
  - Threat Levels: Clear `SUPPRESSED`, Low `SUBDUED`, Elevated `SURGING`, Critical `BREAK THE BAT`
  - Clearance: `OVERRIDE // LEVEL-Ω`
  - Affiliation: `PEÑA DURA • LEAGUE OF SHADOWS`
- **Chrome Copy:**
  - Status Prefix: `VENOM:`
  - Recon Header: `● ● ●  SURVEILLANCE GRID // OVERRUN`
  - Telemetry Header: `VENOM METRICS`
  - Tabs: `[ ◈ ]  COMBAT METRICS` / `[ ▤ ]  TARGET DOSSIER`
  - Idle Readout: `OCTANE FLOW // MAXIMUM READY`

---

## 3. BATMAN BEYOND (Neo-Gotham)
- **ID:** `beyond`
- **Display Name:** `BATMAN BEYOND`
- **Tagline:** Sleek cybernetic Neo-Gotham interface with piercing crimson circuitry
- **Primary Accent:** `#ff003c` | **Background:** `#050508`
- **Palette Story:** Ultra high-contrast obsidian black, piercing Beyond crimson, cold cyber blue telemetry, laser red borders.
- **Top-Right Identity:**
  - Subject Label: `CALLSIGN — BEYOND`
  - Codename: `TERRY // BATMAN`
  - Subject Mode: `keep_real`
  - Threat Header: `CITY THREAT MATRIX`
  - Threat Levels: Clear `PATROL STABLE`, Low `GANG DISPERSED`, Elevated `JOKERZ CONVERGING`, Critical `MAX GOTHAM ALERT`
  - Clearance: `WAYNE TECH // CLEARANCE ZERO`
  - Affiliation: `WAYNE-POWERED • NEO-GOTHAM GRID`
- **Chrome Copy:**
  - Status Prefix: `BEYOND:`
  - Recon Header: `● ● ●  OPTICAL DRONE MATRIX // FEED`
  - Telemetry Header: `EXOSUIT TELEMETRY`
  - Tabs: `[ ◈ ]  SUIT TELEMETRY` / `[ ▤ ]  NEO-INTEL ARCHIVE`
  - Idle Readout: `TERRY CALLSIGN LOCKED`

---

## 4. JOKER (Clown Prince of Crime)
- **ID:** `joker`
- **Display Name:** `JOKER`
- **Tagline:** Deranged neon acid purple and toxic smile green with manic flair
- **Primary Accent:** `#b537f2` | **Background:** `#09030e`
- **Palette Story:** Acid laughing-gas violet, chemical neon green, carnival red hazard highlights.
- **Top-Right Identity:**
  - Subject Label: `PUNCHLINE CODE 00`
  - Codename: `THE JOKER`
  - Subject Mode: `thematic_codename`
  - Threat Header: `WHY SO SERIOUS`
  - Threat Levels: Clear `BORING SMILE`, Low `GIGGLING`, Elevated `LAUGHING GAS`, Critical `KILLING JOKE`
  - Clearance: `VIP // ARKHAM ESCAPEE`
  - Affiliation: `ACE CHEMICALS • GOTHAM UNDERGROUND`
- **Chrome Copy:**
  - Status Prefix: `HA-HA:`
  - Recon Header: `● ● ●  JACK-IN-THE-BOX OPTICAL FEED`
  - Telemetry Header: `MANIC METRICS`
  - Tabs: `[ ◈ ]  GAG REEL` / `[ ▤ ]  RANSOM NOTES`
  - Idle Readout: `WAITING FOR PUNCHLINE`

---

## 5. RIDDLER (Enigma Routine)
- **ID:** `riddler`
- **Display Name:** `RIDDLER`
- **Tagline:** Cryptographic emerald cipher console tuned for obsessive deduction
- **Primary Accent:** `#00e676` | **Background:** `#040f07`
- **Palette Story:** Cipher question-mark emerald green, digital green phosphor glow, cryptographic teal.
- **Top-Right Identity:**
  - Subject Label: `CIPHER — Q.ED`
  - Codename: `EDWARD NIGMA // E.NYGMA`
  - Subject Mode: `thematic_codename`
  - Threat Header: `RIDDLE DENSITY`
  - Threat Levels: Clear `TRIVIAL`, Low `COMPLEX`, Elevated `CONFOUNDING`, Critical `MASTER OF PUZZLES`
  - Clearance: `IQ 180+ // VERIFIED`
  - Affiliation: `ENIGMA CRACKED // ARCHIVE`
- **Chrome Copy:**
  - Status Prefix: `ENIGMA:`
  - Recon Header: `● ● ●  SURVEILLANCE CIPHER // PUZZLE FEED`
  - Telemetry Header: `COGNITIVE DENSITY`
  - Tabs: `[ ◈ ]  PUZZLE MATRIX` / `[ ▤ ]  ENCRYPTED CLUES`
  - Idle Readout: `SOLVE FOR X // SYSTEM READY`

---

## 6. MR. FREEZE (Cryogenic Hold)
- **ID:** `mr_freeze`
- **Display Name:** `MR. FREEZE`
- **Tagline:** Sub-zero cryogenic coolant interface bathed in glacial cyan luminescents
- **Primary Accent:** `#00e5ff` | **Background:** `#030a12`
- **Palette Story:** Glacial frost cyan, ice crystal white, deep sub-zero oceanic backing.
- **Top-Right Identity:**
  - Subject Label: `CONTAINMENT — SUB-ZERO`
  - Codename: `DR. VICTOR FRIES`
  - Subject Mode: `thematic_codename`
  - Threat Header: `CORE TEMPERATURE`
  - Threat Levels: Clear `-273.15°C [STABLE]`, Low `-200°C [COOLED]`, Elevated `-50°C [LEAKING]`, Critical `0°C MELTDOWN`
  - Clearance: `CRYO-SUIT // ACTIVE FEED`
  - Affiliation: `GOTHAM COLD STORAGE • CRYO-LAB`
- **Chrome Copy:**
  - Status Prefix: `CRYO:`
  - Recon Header: `● ● ●  THERMAL SPECTRUM // FROST SENSOR`
  - Telemetry Header: `COOLANT TELEMETRY`
  - Tabs: `[ ◈ ]  CRYO-FEED` / `[ ▤ ]  NORA DOSSIER`
  - Idle Readout: `HEART OF ICE // SYSTEM COLD`

---

## 7. HARVEY TWO-FACE (Duality Matrix)
- **ID:** `harvey_two_face`
- **Display Name:** `HARVEY TWO-FACE`
- **Tagline:** Split justice console balancing courtroom brass gold against scarred slate
- **Primary Accent:** `#ffb300` | **Background:** `#0c0a06`
- **Palette Story:** Polished DA courtroom brass gold balanced against charred silver-slate and acid crimson.
- **Top-Right Identity:**
  - Subject Label: `SPLIT RECORD — 50/50`
  - Codename: `HARVEY DENT // TWO-FACE`
  - Subject Mode: `thematic_codename`
  - Threat Header: `DOUBLE-ENTRY CHANCE`
  - Threat Levels: Clear `HEADS [FAIR]`, Low `EVEN ODDS`, Elevated `COIN IN AIR`, Critical `TAILS [VERDICT]`
  - Clearance: `DISTRICT ATTORNEY // DUAL PASS`
  - Affiliation: `50/50 COIN PROJECTION`
- **Chrome Copy:**
  - Status Prefix: `COIN:`
  - Recon Header: `● ● ●  DUAL SPLIT // CAM FEED`
  - Telemetry Header: `LEDGER TELEMETRY`
  - Tabs: `[ ◈ ]  HEADS // STATS` / `[ ▤ ]  TAILS // CHARGES`
  - Idle Readout: `FLIP THE COIN // WAITING ON FATE`

---

## 8. CATWOMAN (East End Rooftops)
- **ID:** `catwoman`
- **Display Name:** `CATWOMAN`
- **Tagline:** Nocturnal jewel-thief terminal with diamond-cut violet and rooftop stealth
- **Primary Accent:** `#e040fb` | **Background:** `#0a040d`
- **Palette Story:** Midnight roof stealth, diamond magenta-violet brilliance, muted amethyst terminal readouts.
- **Top-Right Identity:**
  - Subject Label: `CALLSIGN — CAT`
  - Codename: `SELINA KYLE // CAT`
  - Subject Mode: `thematic_codename`
  - Threat Header: `HEIST CONTINGENCY`
  - Threat Levels: Clear `SHADOWS CLEAR`, Low `SECURITY ON PATROL`, Elevated `LASERS ACTIVE`, Critical `VAULT ALARM TRIPPED`
  - Clearance: `MASTER BURGLAR // BLACK CARD`
  - Affiliation: `EAST END • ROOFTOPS GRID`
- **Chrome Copy:**
  - Status Prefix: `FELINE:`
  - Recon Header: `● ● ●  CATWALK IR FEED // ROOFTOP SCAN`
  - Telemetry Header: `AGILITY METRICS`
  - Tabs: `[ ◈ ]  AGILITY FEED` / `[ ▤ ]  SAFE COMBOS`
  - Idle Readout: `SILENT PAWS // ROOFTOPS CLEAR`

---

## 9. ARKHAM ASYLUM (Patient Monitor)
- **ID:** `arkham`
- **Display Name:** `ARKHAM ASYLUM`
- **Tagline:** Clinical psychiatric containment terminal with emergency quarantine amber
- **Primary Accent:** `#76ff03` | **Background:** `#070c07`
- **Palette Story:** High-security sanitarium containment green, cautionary quarantine amber, padded cell shadows.
- **Top-Right Identity:**
  - Subject Label: `PATIENT LOG — CELL 08`
  - Codename: `INMATE // SEC-001`
  - Subject Mode: `thematic_codename`
  - Threat Header: `INSANITY INDEX`
  - Threat Levels: Clear `SEDATED`, Low `AGITATED`, Elevated `RIOT IMMINENT`, Critical `FULL BREACH`
  - Clearance: `CHIEF OF PSYCHIATRY // DR. ARKHAM`
  - Affiliation: `ELIZABETH ARKHAM ASYLUM FOR CRIMINALLY INSANE`
- **Chrome Copy:**
  - Status Prefix: `ARKHAM:`
  - Recon Header: `● ● ●  CELL CCTV // MAXIMUM SECURITY`
  - Telemetry Header: `SEDATION MONITOR`
  - Tabs: `[ ◈ ]  CELL CAMS` / `[ ▤ ]  PATIENT FILES`
  - Idle Readout: `WARD LOCKDOWN // CAMERAS ACTIVE`

---

## 10. WATCHTOWER OMNI (Justice League Satellite)
- **ID:** `watchtower`
- **Display Name:** `WATCHTOWER OMNI`
- **Tagline:** Geosynchronous Justice League orbital telemetry array with high ops clarity
- **Primary Accent:** `#2979ff` | **Background:** `#040914`
- **Palette Story:** High-altitude deep orbital space navy, vivid Justice League blue, solar gold telemetry, star-chart crispness.
- **Top-Right Identity:**
  - Subject Label: `TERMINAL — ORBITAL-1`
  - Codename: `ORBITAL TAC-AI`
  - Subject Mode: `keep_real`
  - Threat Header: `GLOBAL THREAT LEVEL`
  - Threat Levels: Clear `PLANETARY STABLE`, Low `REGIONAL CRISIS`, Elevated `EXTINCTION EVENT`, Critical `OMEGA INVASION`
  - Clearance: `FOUNDING MEMBER // JL-ALPHA`
  - Affiliation: `JUSTICE LEAGUE • ORBITAL SATELLITE`
- **Chrome Copy:**
  - Status Prefix: `ORBIT:`
  - Recon Header: `● ● ●  GEO-STATIONARY ARRAY // EARTH FEED`
  - Telemetry Header: `ORBITAL METRICS`
  - Tabs: `[ ◈ ]  GLOBAL SCAN` / `[ ▤ ]  LEAGUE INTEL`
  - Idle Readout: `ORBIT 22,300 MILES // COMM LOCKED`
