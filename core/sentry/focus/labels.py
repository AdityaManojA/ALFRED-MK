"""Distraction Label Resolver for Focus Mode.

Structural Privacy Law:
- Distraction labels are transient. They ride for exactly one engine tick into the
  spoken callout line and are NEVER stored in state, logs, ledger, or history.
- Home base (ALFRED) is never labelled.
- The NAME_DISTRACTIONS switch allows global fallback to nameless pools.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.sentry.focus.reader import SurfaceIdentity

# ── Named Switches & Constants ───────────────────────────────────────────────
NAME_DISTRACTIONS: bool = True

HOST_LABEL_MAP: dict[str, str] = {
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "instagram.com": "Instagram",
    "twitter.com": "X",
    "x.com": "X",
    "reddit.com": "Reddit",
    "tiktok.com": "TikTok",
    "netflix.com": "Netflix",
    "twitch.tv": "Twitch",
    "facebook.com": "Facebook",
    "linkedin.com": "LinkedIn",
    "mail.google.com": "Gmail",
    "gmail.com": "Gmail",
    "discord.com": "Discord",
    "amazon.com": "Amazon",
    "hulu.com": "Hulu",
    "disneyplus.com": "Disney+",
    "pinterest.com": "Pinterest",
}


def resolve_distraction_label(surface: SurfaceIdentity) -> str:
    """Derive a spoken distraction name from the surface identity.

    Returns an empty string if naming is disabled, if surface is home base,
    or if no meaningful label can be determined.
    """
    if not NAME_DISTRACTIONS:
        return ""

    if surface.is_home_base or surface.is_self:
        return ""

    # If surface already has a spoken_label explicitly set (e.g. from tests or reader)
    if surface.spoken_label and surface.spoken_label.lower() != "unknown":
        # Check if spoken label matches a known host map key
        low_label = surface.spoken_label.lower()
        for host, friendly in HOST_LABEL_MAP.items():
            if host in low_label or friendly.lower() == low_label:
                return friendly
        # Otherwise use the spoken label directly (e.g. synthetic test token or desktop app name)
        return surface.spoken_label

    # Browser inspection: check raw title for domain mentions
    if surface.is_browser and surface.raw_title:
        low_title = surface.raw_title.lower()
        for host, friendly in HOST_LABEL_MAP.items():
            if host in low_title or friendly.lower() in low_title:
                return friendly

        # Check for bare registrable domain in title
        match = re.search(r"\b([a-zA-Z0-9\-]+\.(?:com|org|io|dev|net|ai|edu|gov))\b", surface.raw_title, re.I)
        if match:
            return match.group(1).lower()

    # Desktop app inspection
    if surface.app_id and surface.app_id.lower() != "unknown":
        clean_app = surface.app_id.lower().replace(".exe", "")
        # Clean common names
        return clean_app.capitalize()

    return ""
