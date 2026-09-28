"""Dialogue Pools for Focus Mode Drift Callouts.

Ground Rules:
- ALFRED persona ('sir'), terse.
- Four lines per tier, each containing the {label} placeholder.
- First callout of a session names both the intent and the distraction.
- Drill-sergeant pool is selectable by voice ('be harsh today').
- Nameless fallback pool used when NAME_DISTRACTIONS is False.
"""
from __future__ import annotations

import random

# ── Dialogue Pools (4 lines each) ─────────────────────────────────────────────

FIRST_CALLOUT = [
    "Sir — {label} does not look like '{intent}' to me.",
    "Sir, we agreed on '{intent}', yet you find yourself on {label}.",
    "Sir, '{intent}' was the mission. {label} is not.",
    "Pardon me, sir, but {label} seems a curious path toward '{intent}'.",
]

TIER1 = [
    "Sir, {label} can wait.",
    "A brief detour into {label}, sir?",
    "Sir, gentle reminder: {label} is not your target.",
    "Eyes on the prize, sir. {label} is waiting.",
]

TIER2 = [
    "Twice into {label}, sir. It is starting to look deliberate.",
    "Sir, {label} is consuming the session.",
    "Another excursion into {label}, sir. Shall we refocus?",
    "Sir, your target awaits while you browse {label}.",
]

TIER3 = [
    "Third time in {label}, sir. The detours are becoming the project.",
    "Sir, {label} has completely derailed this session. Return to target.",
    "Enough of {label}, sir. Back to the task at hand.",
    "Sir, {label} is winning. Your actual work is not.",
]

NAMELESS = [
    "Sir, you have drifted from your task.",
    "Focus is slipping, sir.",
    "We are off target again, sir.",
    "Sir, back to the session, if you please.",
]

DRILL_SERGEANT = [
    "Drop the {label}, sir! Get back to work immediately!",
    "Are you paying me to watch you slack off on {label}, sir? Move!",
    "Zero discipline on {label}, sir! Target now!",
    "{label}? Unacceptable, sir. Lock back in!",
]


def get_drift_line(
    tier: int,
    label: str = "",
    intent: str = "",
    is_first: bool = False,
    drill_sergeant: bool = False,
) -> str:
    """Select and format a drift callout line."""
    clean_label = (label or "").strip()
    clean_intent = (intent or "").strip() or "your goal"

    # If no label available, use nameless pool
    if not clean_label:
        return random.choice(NAMELESS)

    # Drill sergeant mode takes precedence if active
    if drill_sergeant:
        template = random.choice(DRILL_SERGEANT)
        return template.format(label=clean_label)

    # First callout with stated intent
    if is_first and intent:
        template = random.choice(FIRST_CALLOUT)
        return template.format(label=clean_label, intent=clean_intent)

    # Tier selection
    if tier <= 1:
        template = random.choice(TIER1)
    elif tier == 2:
        template = random.choice(TIER2)
    else:
        template = random.choice(TIER3)

    return template.format(label=clean_label)
