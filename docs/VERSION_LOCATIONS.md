# 🦇 ALFRED Tactical Assistant — Version Registry & Mutation Codex

This registry documents every single location across the repository where the version title (**Mark-VIII**) and its associated tokens are configured.

When bumping to a new version (e.g., `Mark-IX`, `Mark-X`), consult this table or run the automated bumper script:
```powershell
python tools/bump_version.py Mark-IX
```

---

## 🧭 Token Variant Glossary

Each file uses a specific token format suited to its context (headers, URLs, telemetry, or system IDs):

| Token Variant | Example (Current) | Target Context |
|---|---|---|
| `FULL_HYPHEN` | `Mark-VIII` / `MARK-VIII` | App versions, release names, markdown headers, UI constant `APP_VERSION` |
| `SHORT_HYPHEN` | `MK-VIII` | HUD telemetry strings, vector overlays, Git URLs, benchmarks |
| `SPACE_CASE` | `Mark VIII` | Section titles (e.g. `What's New in Mark VIII`) |
| `NUMERIC_ID` | `mk8` | Windows OS `AppUserModelID` (`alfred.wayne.batcomputer.mk8`) |
| `TITLE_CASE` | `Alfred-Mark-VIII` | User-Agents, repo directory paths, simulated test windows |

---

## 📑 Complete Master Location Registry

### 1. Main Project Documentation & Repository Branding
| File | Line(s) | Current Content | Variant | Purpose |
|---|---|---|---|---|
| [`readme.md`](file:///d:/Projects/Alfred-Mark-VIII/readme.md) | 1–3 | `# 🦇 ALFRED — MARK-VIII...` / `**Version 8 — Stable Build (Windows)**` | `FULL_HYPHEN` | H1 Title & Build Subtitle |
| [`readme.md`](file:///d:/Projects/Alfred-Mark-VIII/readme.md) | 4 | `[![Version 8 (Stable Build · Windows)](...)...` | `FULL_HYPHEN` | Stable Windows build shield badge |
| [`readme.md`](file:///d:/Projects/Alfred-Mark-VIII/readme.md) | 10 | `[...](https://github.com/AdityaManojA/ALFRED-MK-VIII)` | `SHORT_HYPHEN` | Remote dashboard badge URL |
| [`readme.md`](file:///d:/Projects/Alfred-Mark-VIII/readme.md) | 13 | `> **ALFRED MARK-VIII (Version 8 — Stable Build · Windows)**...` | `FULL_HYPHEN` | Executive summary lead quote |
| [`readme.md`](file:///d:/Projects/Alfred-Mark-VIII/readme.md) | 16 | `alt="ALFRED MARK-VIII Tactical HUD Interface"` | `FULL_HYPHEN` | Hero image alt text |
| [`readme.md`](file:///d:/Projects/Alfred-Mark-VIII/readme.md) | 27 | `5. [🆕 What's New in Version 8 (Stable Build · Windows)](#whats-new)` | `SPACE_CASE` | Table of contents entry |
| [`readme.md`](file:///d:/Projects/Alfred-Mark-VIII/readme.md) | 48 | `* **Operating System**: **Windows 10/11 (Primary Target — Version 8 Stable Build)**...` | `FULL_HYPHEN` | OS Prerequisites |
| [`readme.md`](file:///d:/Projects/Alfred-Mark-VIII/readme.md) | 64–65 | `git clone .../ALFRED-MK-VIII.git` / `cd ALFRED-MK-VIII` | `SHORT_HYPHEN` | Windows setup quick-start |
| [`readme.md`](file:///d:/Projects/Alfred-Mark-VIII/readme.md) | 78–79 | `git clone .../ALFRED-MK-VIII.git` / `cd ALFRED-MK-VIII` | `SHORT_HYPHEN` | macOS setup quick-start |
| [`readme.md`](file:///d:/Projects/Alfred-Mark-VIII/readme.md) | 92–93 | `git clone .../ALFRED-MK-VIII.git` / `cd ALFRED-MK-VIII` | `SHORT_HYPHEN` | Linux setup quick-start |
| [`readme.md`](file:///d:/Projects/Alfred-Mark-VIII/readme.md) | 255 | `**ALFRED MARK-VIII is fundamentally different**` | `FULL_HYPHEN` | Architecture comparison lead |
| [`readme.md`](file:///d:/Projects/Alfred-Mark-VIII/readme.md) | 259 | `\| Pillar \| ALFRED MARK-VIII \| Typical...` | `FULL_HYPHEN` | Comparison table header |
| [`readme.md`](file:///d:/Projects/Alfred-Mark-VIII/readme.md) | 281 | `MARK-VIII invests in the glue that fails...` | `FULL_HYPHEN` | Performance paragraph |
| [`readme.md`](file:///d:/Projects/Alfred-Mark-VIII/readme.md) | 283 | `> **The Verdict:** ALFRED MARK-VIII is not...` | `FULL_HYPHEN` | Section conclusion quote |
| [`readme.md`](file:///d:/Projects/Alfred-Mark-VIII/readme.md) | 288 | `## 🆕 5. What's New in Version 8 / Mark VIII (Stable Build · Windows)` | `SPACE_CASE` | Changelog section header |
| [`readme.md`](file:///d:/Projects/Alfred-Mark-VIII/readme.md) | 808 | `ALFRED-MK-VIII/` | `SHORT_HYPHEN` | System architecture tree root |
| [`readme.md`](file:///d:/Projects/Alfred-Mark-VIII/readme.md) | 962–963 | `file:///d:/Projects/Alfred-Mark-VIII/graphify-out/...` | `TITLE_CASE` | Knowledge graph local paths |
| [`readme.md`](file:///d:/Projects/Alfred-Mark-VIII/readme.md) | 966 | `### 🎁 Mark VIII New Actions (Auto-Discovered)` | `SPACE_CASE` | Actions table header |
| [`readme.md`](file:///d:/Projects/Alfred-Mark-VIII/readme.md) | 1036 | `* **🦇 Project:** ALFRED-MK-VIII — Version 8 (Stable Build · Windows...)` | `SHORT_HYPHEN` | Licensing attribution block |

---

### 2. Core Desktop Application & GUI Runtime
| File | Line(s) | Current Content | Variant | Purpose |
|---|---|---|---|---|
| [`ui.py`](file:///d:/Projects/Alfred-Mark-VIII/ui.py) | 745 | `APP_VERSION  = "MARK-VIII"` | `FULL_HYPHEN` | **Single source of truth** for Qt window title & header badge |
| [`ui.py`](file:///d:/Projects/Alfred-Mark-VIII/ui.py) | 746 | `APP_PROTOCOL = "MARK-VIII"` | `FULL_HYPHEN` | Protocol version constant |
| [`ui.py`](file:///d:/Projects/Alfred-Mark-VIII/ui.py) | 1867 | `Qt.AlignmentFlag.AlignLeft, "MK-VIII // ARC-GEN"` | `SHORT_HYPHEN` | Reticle corner telemetry badge |
| [`ui.py`](file:///d:/Projects/Alfred-Mark-VIII/ui.py) | 2516 | `●  REACTIVE HUD // VOCAL SYNTHESIS ACTIVE // ALFRED MARK-VIII` | `FULL_HYPHEN` | Vocal active status bar text |
| [`ui.py`](file:///d:/Projects/Alfred-Mark-VIII/ui.py) | 2607 | `SUBJECT ALFRED.MK-VIII // VECTOR HUD` | `SHORT_HYPHEN` | Vector HUD upper telemetry line |
| [`ui.py`](file:///d:/Projects/Alfred-Mark-VIII/ui.py) | 2610 | `WAYNE TECH PROTOCOL MK-VIII` | `SHORT_HYPHEN` | Vector HUD bottom right protocol line |
| [`ui.py`](file:///d:/Projects/Alfred-Mark-VIII/ui.py) | 2917 | `def __init__(self, assistant_name="ALFRED.MK-VIII", ...):` | `SHORT_HYPHEN` | `SubjectDossierCard` default fallback |
| [`ui.py`](file:///d:/Projects/Alfred-Mark-VIII/ui.py) | 3875 | `self.setWindowTitle(f"ALFRED MARK-VIII // ...")` | `FULL_HYPHEN` | Minimized HUD window title |
| [`ui.py`](file:///d:/Projects/Alfred-Mark-VIII/ui.py) | 9371 | `# Update top header app icon next to MARK-VIII` | `FULL_HYPHEN` | Codebase comment |
| [`main.py`](file:///d:/Projects/Alfred-Mark-VIII/main.py) | 17 | `SetCurrentProcessExplicitAppUserModelID("alfred.wayne.batcomputer.mk8")` | `NUMERIC_ID` | Windows taskbar icon isolation |
| [`ui/overlays/setup_overlay.py`](file:///d:/Projects/Alfred-Mark-VIII/ui/overlays/setup_overlay.py) | 538 | `"User-Agent": "ALFRED-Mark-VIII"` | `TITLE_CASE` | OpenRouter API authentication probe agent |

---

### 3. Quantum Mobile & Web Remote Dashboard
| File | Line(s) | Current Content | Variant | Purpose |
|---|---|---|---|---|
| [`dashboard/static/app.html`](file:///d:/Projects/Alfred-Mark-VIII/dashboard/static/app.html) | 6 | `<title>ALFRED — Wayne Mark-VIII Tactical Uplink</title>` | `TITLE_CASE` | Web browser tab title |
| [`dashboard/static/app.html`](file:///d:/Projects/Alfred-Mark-VIII/dashboard/static/app.html) | 1152 | `<div class="sub-brand">WAYNE MARK-VIII</div>` | `FULL_HYPHEN` | Top dashboard header sub-brand |
| [`dashboard/static/app.html`](file:///d:/Projects/Alfred-Mark-VIII/dashboard/static/app.html) | 1181 | `... // MOBILE UPLINK ACTIVE [MK-VIII]` | `SHORT_HYPHEN` | Welcome card subtitle tag |
| [`dashboard/static/app.html`](file:///d:/Projects/Alfred-Mark-VIII/dashboard/static/app.html) | 1262 | `'dossier': { ... sub: '... MOBILE UPLINK ACTIVE [MK-VIII]' }` | `SHORT_HYPHEN` | Dossier theme subtitle metadata |
| [`dashboard/static/app.html`](file:///d:/Projects/Alfred-Mark-VIII/dashboard/static/app.html) | 1263 | `'vector':  { ... sub: '... BANE VECTOR [MK-VIII]' }` | `SHORT_HYPHEN` | Vector theme subtitle metadata |
| [`dashboard/static/app.html`](file:///d:/Projects/Alfred-Mark-VIII/dashboard/static/app.html) | 1265 | `'wayne':   { ... sub: '... OBSIDIAN GOLD [MK-VIII]' }` | `SHORT_HYPHEN` | Wayne Gold theme subtitle metadata |
| [`dashboard/static/app.html`](file:///d:/Projects/Alfred-Mark-VIII/dashboard/static/app.html) | 2354 | `<span class="lbl">ALFRED // WAYNE MK-VIII</span>` | `SHORT_HYPHEN` | Incoming chat message author label |
| [`dashboard/static/login.html`](file:///d:/Projects/Alfred-Mark-VIII/dashboard/static/login.html) | 311 | `title="Wayne Mark-VIII Tactical Reactor"` | `TITLE_CASE` | Quantum reactor tooltip text |
| [`dashboard/static/login.html`](file:///d:/Projects/Alfred-Mark-VIII/dashboard/static/login.html) | 318 | `<span class="badge">MARK-VIII</span>` | `FULL_HYPHEN` | Login card badge |

---

### 4. Installation, Dependency & Environment Setup
| File | Line(s) | Current Content | Variant | Purpose |
|---|---|---|---|---|
| [`setup.py`](file:///d:/Projects/Alfred-Mark-VIII/setup.py) | 2 | `MARK-VIII — one-time setup.` | `FULL_HYPHEN` | Module docstring |
| [`setup.py`](file:///d:/Projects/Alfred-Mark-VIII/setup.py) | 50 | `print(f"\n❌ Python ... — MARK-VIII needs at ...")` | `FULL_HYPHEN` | Python version validation error message |
| [`setup.py`](file:///d:/Projects/Alfred-Mark-VIII/setup.py) | 70 | `print(f"⚙  MARK-VIII setup — detected OS: ...")` | `FULL_HYPHEN` | Setup startup banner |
| [`requirements.txt`](file:///d:/Projects/Alfred-Mark-VIII/requirements.txt) | 1 | `# ── MARK-VIII — Python dependencies ──` | `FULL_HYPHEN` | Requirements file header banner |

---

### 5. Core Platform, APIs, Themes, & Mesh Visuals
| File | Line(s) | Current Content | Variant | Purpose |
|---|---|---|---|---|
| [`core/llm_client.py`](file:///d:/Projects/Alfred-Mark-VIII/core/llm_client.py) | 74 | `headers["HTTP-Referer"] = ".../ALFRED-MK-VIII"` | `SHORT_HYPHEN` | OpenRouter analytics referrer header |
| [`core/llm_client.py`](file:///d:/Projects/Alfred-Mark-VIII/core/llm_client.py) | 75 | `headers["X-Title"] = "ALFRED-Mark-VIII"` | `TITLE_CASE` | OpenRouter analytics title header |
| [`core/image_viewer/fetch.py`](file:///d:/Projects/Alfred-Mark-VIII/core/image_viewer/fetch.py) | 44 | `USER_AGENT: str = "Alfred-Mark-VIII/1.0 ..."` | `TITLE_CASE` | Web image fetch user agent |
| [`core/cache.py`](file:///d:/Projects/Alfred-Mark-VIII/core/cache.py) | 2 | `... Centralized Caching Layer for ALFRED Mark-VIII.` | `SPACE_CASE` | Cache module docstring |
| [`core/apis/oauth.py`](file:///d:/Projects/Alfred-Mark-VIII/core/apis/oauth.py) | 70 | `<h2>&#x25C8; ALFRED-MK-VIII // AUTHENTICATION SUCCESSFUL</h2>` | `SHORT_HYPHEN` | OAuth redirect success HTML |
| [`core/hud/visuals/slots/batcave.py`](file:///d:/Projects/Alfred-Mark-VIII/core/hud/visuals/slots/batcave.py) | 238 | `self.title_text: str = "BATWING MK-VIII BLUEPRINT // 3D"` | `SHORT_HYPHEN` | Batcave 3D wireframe title |
| [`core/batman_cowl.obj`](file:///d:/Projects/Alfred-Mark-VIII/core/batman_cowl.obj) | 1 | `# Batman Cowl 3D Tactical Mesh for Alfred / Mark-VIII` | `TITLE_CASE` | 3D Wavefront OBJ mesh header |
| [`core/secrets/store.py`](file:///d:/Projects/Alfred-Mark-VIII/core/secrets/store.py) | 2, 200 | `... Encrypted Secrets Store for ALFRED-MK-VIII.` | `SHORT_HYPHEN` | Secrets store docstring and file header |
| [`core/ui/themes/apply.py`](file:///d:/Projects/Alfred-Mark-VIII/core/ui/themes/apply.py) | 2 | `... ThemeChrome provider for ALFRED-MK-VIII.` | `SHORT_HYPHEN` | Theme engine docstring |
| [`core/ui/themes/registry.py`](file:///d:/Projects/Alfred-Mark-VIII/core/ui/themes/registry.py) | 2 | `Registry for ALFRED-MK-VIII themes.` | `SHORT_HYPHEN` | Theme registry docstring |
| [`core/ui/themes/__init__.py`](file:///d:/Projects/Alfred-Mark-VIII/core/ui/themes/__init__.py) | 2 | `ALFRED-MK-VIII Thematic UI Skins.` | `SHORT_HYPHEN` | Theme package docstring |
| [`core/ui/themes/schema.py`](file:///d:/Projects/Alfred-Mark-VIII/core/ui/themes/schema.py) | 2 | `Theme schema definitions for ALFRED-MK-VIII.` | `SHORT_HYPHEN` | Theme schema docstring |
| [`core/ui/themes/catalog.py`](file:///d:/Projects/Alfred-Mark-VIII/core/ui/themes/catalog.py) | 2 | `Theme catalog for ALFRED-MK-VIII.` | `SHORT_HYPHEN` | Theme catalog docstring |

---

### 6. Actions & Plugins
| File | Line(s) | Current Content | Variant | Purpose |
|---|---|---|---|---|
| [`actions/daily_brief.py`](file:///d:/Projects/Alfred-Mark-VIII/actions/daily_brief.py) | 2 | `Daily Brief Action for ALFRED Mark-VIII.` | `TITLE_CASE` | Action header docstring |
| [`actions/gmail_manager.py`](file:///d:/Projects/Alfred-Mark-VIII/actions/gmail_manager.py) | 2 | `Gmail Manager Action for ALFRED Mark-VIII.` | `TITLE_CASE` | Action header docstring |
| [`actions/update_app_icon.py`](file:///d:/Projects/Alfred-Mark-VIII/actions/update_app_icon.py) | 2 | `Update App Icon Action for ALFRED Mark-VIII.` | `TITLE_CASE` | Action header docstring |
| [`actions/update_daily_briefing.py`](file:///d:/Projects/Alfred-Mark-VIII/actions/update_daily_briefing.py) | 2 | `Update Daily Briefing Preferences Action for ALFRED Mark-VIII.` | `TITLE_CASE` | Action header docstring |
| [`plugins/focus_protocol.py`](file:///d:/Projects/Alfred-Mark-VIII/plugins/focus_protocol.py) | 2 | `Focus Protocol Plugin for ALFRED Mark-VIII.` | `TITLE_CASE` | Plugin header docstring |
| [`plugins/calendar_sync.py`](file:///d:/Projects/Alfred-Mark-VIII/plugins/calendar_sync.py) | 2 | `Calendar Sync Plugin for ALFRED Mark-VIII.` | `TITLE_CASE` | Plugin header docstring |

---

### 7. Unit Tests & Benchmark Diagnostics
| File | Line(s) | Current Content | Variant | Purpose |
|---|---|---|---|---|
| [`tools/benchmark_latency_pipeline.py`](file:///d:/Projects/Alfred-Mark-VIII/tools/benchmark_latency_pipeline.py) | 35 | `=== Running ALFRED-MK-VIII Latency Profiling Benchmark ===` | `SHORT_HYPHEN` | Latency benchmark log output |
| [`tests/test_platform_stability.py`](file:///d:/Projects/Alfred-Mark-VIII/tests/test_platform_stability.py) | 1 | `... runtime stability fixes in ALFRED-MK-VIII.` | `SHORT_HYPHEN` | Test suite docstring |
| [`tests/test_thematic_hud.py`](file:///d:/Projects/Alfred-Mark-VIII/tests/test_thematic_hud.py) | 2, 219 | `... for ALFRED-MK-VIII ...` / `ui.SubjectDossierCard("ALFRED.MK-VIII")` | `SHORT_HYPHEN` | HUD theme test suite & card assertion |
| [`tests/test_screen_processor.py`](file:///d:/Projects/Alfred-Mark-VIII/tests/test_screen_processor.py) | 63, 64, 144, 164 | `format_window_context(..., "main.py - Alfred-Mark-VIII", ...)` | `TITLE_CASE` | Screen OCR context window title tests |
| [`tests/test_clipboard_manager.py`](file:///d:/Projects/Alfred-Mark-VIII/tests/test_clipboard_manager.py) | 46, 95, 140 | `... overview of ALFRED-MK-VIII` / `... Terminal MK-VIII` / `.../ALFRED-MK-VIII` | `SHORT_HYPHEN` | Clipboard manager test blocks & URL test |

---

## ⚡ How to Bump Version with 1 Command

Use the repository automation script:

```powershell
# Bump to Mark-IX and automatically update graphify + run tests:
python tools/bump_version.py Mark-IX

# Dry-run preview without modifying files:
python tools/bump_version.py Mark-IX --dry-run
```

The script will automatically calculate:
- `FULL_HYPHEN` (`Mark-IX` / `MARK-IX`)
- `SHORT_HYPHEN` (`MK-IX`)
- `SPACE_CASE` (`Mark IX`)
- `NUMERIC_ID` (`mk9`)
- `TITLE_CASE` (`Alfred-Mark-IX`)

And update all registered files atomically.
