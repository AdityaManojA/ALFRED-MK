# ALFRED-MK-V — Thematic HUD Overhaul: Phase 4 Notes

**Date:** 2026-09-29  
**Branch / Workspace:** ALFRED-MK-V  
**Knowledge Graph Nodes Referenced:**
- `ui_mainwindow` (`ui.py:L7858`)
- `ui_subjectdossiercard` (`ui.py:L2816`)
- `ui_crtreconwidget` (`ui.py:L2608`)
- `ui_biometricfingerprintwidget` (`ui.py:L2707`)
- `ui_wireframeposewidget` (`ui.py:L2774`)
- `ui_minimizedhudoverlay` (`ui.py:L3775`)
- `ui_capabilitiesoverlay` (`ui.py:L6171`)
- `core.sentry.mode_manager` (`core/sentry/mode_manager.py`)

---

## 1. Chrome Consumer Integration

Every participating HUD chrome site is bound directly to `ThemeChrome` getters.

| Consumer Site | Bound Property | Fallback / Behavior |
|---|---|---|
| `SubjectDossierCard` | `ThemeChrome.identity()` | Renders 7 rows including thematic threat header and levels |
| `CRTReconWidget` | `ThemeChrome.chrome().monitor_active_line` | Displays themed feed scanner label |
| `BiometricFingerprintWidget` | `ThemeChrome.chrome().bio_scan_header`, `ThemeChrome.identity().clearance_label` | Themed bio-scan header and bottom verification badge |
| `WireframePoseWidget` | `ThemeChrome.chrome().pose_track_header`, `ThemeChrome.chrome().idle_line` | Themed telemetry header and bottom target lock status |
| `MainWindow` Header | `ThemeChrome.identity().affiliation_line`, `ThemeChrome.chrome().window_title_suffix` | Themed window title and center affiliation subtitle |
| `MainWindow` Left Panel | `ThemeChrome.chrome().telemetry_header` | Themed telemetry bar group header |
| `MainWindow` Right Tabs | `ThemeChrome.chrome().tab_telemetry`, `ThemeChrome.chrome().tab_intel` | Themed tab buttons with live unread intel counters |
| `MinimizedHudOverlay` | `ThemeChrome.chrome().window_title_suffix`, `ThemeChrome.chrome().mini_hud_placeholder` | Themed overlay title and transcript awaiting placeholder |
| `CapabilitiesOverlay` | `ThemeChrome.chrome().empty_archive` | Themed empty search result banner |

---

## 2. Data vs. Presentation Rules (Ground Rule Compliance)

### 2.1 Threat Assessment Mapping
No random numbers or fake alerts are generated. The threat assessment row dynamically reflects real application state:
```python
if foc.active and getattr(foc, "drifting", False):
    self._dossier_card.set_threat_state("critical")
elif foc.active or mon.active:
    self._dossier_card.set_threat_state("elevated")
else:
    self._dossier_card.set_threat_state("clear")
```
- **Benign HUD Idle:** Theme's `clear` level displayed (e.g. `★★★` in Batcave, `SUPPRESSED` in Bane, `PATROL STABLE` in Beyond).
- **Active Focus or Screen Monitor:** Theme's `elevated` level displayed (e.g. `★★☆` in Batcave, `SURGING` in Bane, `JOKERZ CONVERGING` in Beyond).
- **Focus Drifting (Distracted):** Theme's `critical` level displayed (e.g. `★★★` in Batcave, `BREAK THE BAT` in Bane, `MAX GOTHAM ALERT` in Beyond).

### 2.2 Sentry Focus & Monitor Timers
- Real timers (`FOC mm:ss`), drift flags, and monitor indicator badges remain strictly truthful and untouched.
- Spoken TTS audio pools remain unparodied and factual.
