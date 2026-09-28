"""Focus Mode State: Whitelisted dataclass and named constants.

Structural Privacy Law:
FocusState contains ONLY booleans, counters, and progress integers.
No app names, no window titles, no URLs, no hostnames, and no intent strings.
The verbal user intent string lives on the session engine, never in FocusState.
"""
from __future__ import annotations

from dataclasses import dataclass

# ── Named Constants ──────────────────────────────────────────────────────────
DEFAULT_SESSION_MIN: int = 25
MAX_SESSION_MIN: int = 180
SNOOZE_DEFAULT_S: int = 15
NAG_DEFAULT_S: int = 30
NAG_MIN_S: int = 10
NAG_MAX_S: int = 120
DRIFT_GRACE_MS: int = 800
TICK_INTERVAL_S: float = 1.0


# ── Whitelist State Dataclass ────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class FocusState:
    """Client-visible state for FOCUS mode.

    Guaranteed structural privacy: contains no identifying strings.
    """
    active: bool = False
    paused: bool = False
    deferred_lock: bool = False
    locked_app: bool = False
    locked_tab: bool = False
    planned_s: int = 0
    elapsed_s: int = 0
    on_target_s: int = 0
    remaining_s: int = 0
    drifting: bool = False
    drift_count: int = 0
    current_drift_s: int = 0
    tier: int = 0  # Escalation tier: 0 (on target), 1 (subtle), 2 (firm), 3 (blunt)
    snoozed_until_s: float = 0.0
    excused: bool = False
    nag_interval_s: int = NAG_DEFAULT_S
    intent_set: bool = False
