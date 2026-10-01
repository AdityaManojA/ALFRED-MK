"""
Theme schema definitions for ALFRED-MK-VIII.
Every selectable theme is a structured ThemeDefinition instance.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class SubjectValueMode(str, Enum):
    """How the subject name/codename is presented in the top-right dossier."""
    KEEP_REAL = "keep_real"               # Retain configured assistant/operator name
    THEMATIC_CODENAME = "thematic_codename" # Show thematic codename instead
    HIDE = "hide"                         # Mask or hide the subject value


@dataclass(frozen=True)
class PaletteDefinition:
    """
    1:1 mapping with ALFRED's CRT palette tokens on class C.
    No unused tokens, no magic numbers.
    """
    bg: str
    panel: str
    panel2: str
    panel_bg: str
    border: str
    border_b: str
    border_a: str
    pri: str
    pri_dim: str
    pri_gho: str
    acc: str
    acc2: str
    green: str
    green_d: str
    red: str
    muted: str
    muted_c: str
    text: str
    text_dim: str
    text_med: str
    text_bright: str
    white: str
    dark: str
    bar_bg: str

    def to_dict(self) -> dict[str, str]:
        """Convert to class C uppercase attribute mapping."""
        return {
            "BG": self.bg,
            "PANEL": self.panel,
            "PANEL2": self.panel2,
            "PANEL_BG": self.panel_bg,
            "BORDER": self.border,
            "BORDER_B": self.border_b,
            "BORDER_A": self.border_a,
            "PRI": self.pri,
            "PRI_DIM": self.pri_dim,
            "PRI_GHO": self.pri_gho,
            "ACC": self.acc,
            "ACC2": self.acc2,
            "GREEN": self.green,
            "GREEN_D": self.green_d,
            "RED": self.red,
            "MUTED": self.muted,
            "MUTED_C": self.muted_c,
            "TEXT": self.text,
            "TEXT_DIM": self.text_dim,
            "TEXT_MED": self.text_med,
            "TEXT_BRIGHT": self.text_bright,
            "WHITE": self.white,
            "DARK": self.dark,
            "BAR_BG": self.bar_bg,
        }


@dataclass(frozen=True)
class ThreatLevels:
    """Thematic display labels for threat levels (cosmetic display strings only)."""
    clear: str = "★★★"
    low: str = "★☆☆"
    elevated: str = "★★☆"
    critical: str = "★★★"


@dataclass(frozen=True)
class IdentityDefinition:
    """Structured fields for the top-right SubjectDossierCard block."""
    subject_label: str = "SUBJECT A-34"
    subject_value_mode: SubjectValueMode = SubjectValueMode.KEEP_REAL
    codename: str = "ALFRED"
    incept_date: str = "03/05/2026"
    function_line: str = "TACTICAL PERSONAL ASSISTANT"
    mental_state: str = "OPERATIONAL // ACTIVE"
    location_line: str = "WAYNE MANOR // LOCALHOST"
    threat_header: str = "THREAT ASSESSMENT"
    threat_levels: ThreatLevels = field(default_factory=ThreatLevels)
    special_skills: str = "[AI]  [SYS]  [SEC]  [AUDIO]"
    clearance_label: str = "VERIFIED // ALPHA-1"
    affiliation_line: str = "WAYNE ENTERPRISES • BATCOMPUTER"


@dataclass(frozen=True)
class ChromeDefinition:
    """Flavour framing copy for peripheral widgets, tabs, and headers."""
    status_prefix: str = "SYS:"
    ready_line: str = "ALFRED online."
    idle_line: str = "TARGET ACQUIRED: LOCAL"
    empty_archive: str = "No archived directives found."
    focus_locked_line: str = "LOCKED ON TARGET"
    monitor_active_line: str = "RECON FEED // OPTICAL"
    telemetry_header: str = "SYS TELEMETRY"
    tab_telemetry: str = "[ ◈ ]  TELEMETRY"
    tab_intel: str = "[ ▤ ]  INTEL // NOTES"
    bio_scan_header: str = "BIO-SCAN // FINGERPRINT"
    pose_track_header: str = "TELEMETRY // POSE TRACK"
    window_title_suffix: str = "BATCOMPUTER MATRIX"
    mini_hud_placeholder: str = "Awaiting ALFRED response…"


@dataclass(frozen=True)
class SpeechFlavour:
    """Optional speech persona flavour (OFF by default)."""
    enabled_default: bool = False
    address_form: str = "sir"


@dataclass(frozen=True)
class ThemeDefinition:
    """Complete structured definition of a selectable ALFRED skin."""
    id: str                            # Stable identifier (persisted in config)
    display_name: str                  # Human-readable title (No emoji)
    tagline: str                       # Subtitle / description in settings picker
    hex: str                           # Primary accent hex code
    palette: PaletteDefinition         # Complete 1:1 color palette
    identity: IdentityDefinition = field(default_factory=IdentityDefinition)
    chrome: ChromeDefinition = field(default_factory=ChromeDefinition)
    speech_flavour: SpeechFlavour = field(default_factory=SpeechFlavour)
