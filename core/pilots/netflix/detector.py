"""
core/pilots/netflix/detector.py — Netflix UI State Detection Engine.

Performs on-demand snapshot inspection of the frontmost Netflix surface.
Zero continuous polling (0 Hz when idle or closed).
Ephemeral reads only; no watch history, emails, or credentials stored.
"""
from __future__ import annotations

import difflib
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, List, Optional, Tuple

import numpy as np

# ── Named Constants ──────────────────────────────────────────────────────────
INSPECT_TIMEOUT_S: float = 4.0
TARGET_LATENCY_MAX_S: float = 1.5
CONFIDENCE_THRESHOLD: float = 0.70

ANCHOR_PROFILES: tuple[str, ...] = (
    "who's watching?",
    "whos watching?",
    "who's watching",
    "whos watching",
    "who is watching?",
    "who is watching",
    "manage profiles",
    "add profile",
)

ANCHOR_SIGNIN: tuple[str, ...] = (
    "sign in",
    "unlimited movies",
    "tv shows, and more",
    "starts at",
    "cancel anytime",
    "ready to watch?",
    "enter your email",
    "get started",
    "finish sign-up",
    "restart your membership",
)

ANCHOR_BROWSE: tuple[str, ...] = (
    "home",
    "tv shows",
    "movies",
    "new & popular",
    "my list",
    "browse by languages",
    "play",
    "more info",
    "top 10",
)

ANCHOR_PLAYING: tuple[str, ...] = (
    "back to browse",
    "skip intro",
    "skip recap",
    "episodes & info",
    "audio & subtitles",
    "next episode",
)

EXCLUDED_PROFILE_LABELS: tuple[str, ...] = (
    "who's watching?",
    "whos watching?",
    "who's watching",
    "whos watching",
    "who is watching?",
    "who is watching",
    "manage profiles",
    "done",
    "edit",
)

NETFLIX_TITLE_TOKENS: tuple[str, ...] = (
    "netflix",
)

_LOGGER = logging.getLogger(__name__)


class NetflixState(Enum):
    """Observable states of Netflix desktop web surface or native app."""
    NOT_LOGGED_IN = auto()
    PROFILE_GATE = auto()
    BROWSE_HOME = auto()
    PLAYING = auto()
    UNKNOWN = auto()


@dataclass(frozen=True)
class ProfileSlot:
    """Ephemeral representation of a profile avatar on the profile gate screen."""
    name: str
    slot_index: int                  # 1-indexed, left-to-right (1 to N)
    center_norm: Tuple[float, float] # (norm_x, norm_y) in [0.0, 1.0]
    box: Optional[Tuple[int, int, int, int]] = None  # (left, top, right, bottom)


class NetflixDetector:
    """Detects Netflix state on-demand via frontmost check, title cues, and snapshot OCR."""

    def __init__(self, ocr_engine: Optional[Any] = None) -> None:
        self._ocr = ocr_engine

    def _get_ocr(self) -> Any:
        if self._ocr is not None:
            return self._ocr
        try:
            from actions.screen_find import get_rapid_ocr
            self._ocr = get_rapid_ocr()
        except Exception as exc:
            _LOGGER.warning("[NetflixDetector] RapidOCR unavailable: %s", exc)
            self._ocr = None
        return self._ocr

    def is_netflix_frontmost(self) -> bool:
        """Check if Netflix browser tab or native application is currently frontmost."""
        # 1. Windows platform check
        if sys.platform == "win32":
            try:
                import ctypes
                user32 = ctypes.windll.user32
                hwnd = user32.GetForegroundWindow()
                if not hwnd:
                    return False
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value.lower()
                    if any(t in title for t in NETFLIX_TITLE_TOKENS):
                        return True
            except Exception:
                pass

        # 2. macOS platform check
        elif sys.platform == "darwin":
            try:
                import subprocess
                cmd = ["osascript", "-e", 'tell application "System Events" to get name of (first process whose frontmost is true)']
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=1.0)
                if res.returncode == 0 and "netflix" in res.stdout.lower():
                    return True
            except Exception:
                pass

        # 3. Linux platform check
        elif sys.platform.startswith("linux"):
            try:
                import subprocess
                res = subprocess.run(["xdotool", "getactivewindow", "getwindowname"], capture_output=True, text=True, timeout=1.0)
                if res.returncode == 0 and any(t in res.stdout.lower() for t in NETFLIX_TITLE_TOKENS):
                    return True
            except Exception:
                pass

        return False

    def detect_state_from_tokens(
        self,
        tokens_with_boxes: List[Tuple[str, float, Tuple[float, float]]],
    ) -> Tuple[NetflixState, List[ProfileSlot]]:
        """
        Pure deterministic pattern matcher for detected text tokens.
        Each token item: (text, confidence, (norm_x, norm_y)).
        Returns: (NetflixState, detected_profiles)
        """
        if not tokens_with_boxes:
            return NetflixState.UNKNOWN, []

        all_text = " ".join(t[0].lower().strip() for t in tokens_with_boxes)

        # 1. Profile Gate Anchor Check
        has_profile_anchor = any(p in all_text for p in ANCHOR_PROFILES)
        if has_profile_anchor:
            profiles = self._extract_profiles(tokens_with_boxes)
            return NetflixState.PROFILE_GATE, profiles

        # 2. Video Playing Anchor Check
        has_playing_anchor = any(p in all_text for p in ANCHOR_PLAYING)
        if has_playing_anchor:
            return NetflixState.PLAYING, []

        # 3. Not Logged In (Landing / Sign-in) Anchor Check
        has_signin_anchor = any(s in all_text for s in ANCHOR_SIGNIN)
        if has_signin_anchor:
            return NetflixState.NOT_LOGGED_IN, []

        # 4. Browse Home Grid Anchor Check
        has_browse_anchor = any(b in all_text for b in ANCHOR_BROWSE)
        if has_browse_anchor:
            return NetflixState.BROWSE_HOME, []

        return NetflixState.UNKNOWN, []

    def _extract_profiles(
        self,
        tokens_with_boxes: List[Tuple[str, float, Tuple[float, float]]],
    ) -> List[ProfileSlot]:
        """
        Extract profile cards from profile gate screen sorted horizontally left to right.
        Tokens: (text, conf, (norm_x, norm_y))
        """
        candidate_profiles: List[Tuple[str, float, float]] = []

        for text, conf, (norm_x, norm_y) in tokens_with_boxes:
            cleaned = text.strip()
            low = cleaned.lower()
            if not cleaned or len(cleaned) < 2:
                continue
            if any(exc in low for exc in EXCLUDED_PROFILE_LABELS):
                continue
            # Profiles typically appear in vertical range ~30% to ~75% of viewport
            if 0.25 <= norm_y <= 0.85:
                candidate_profiles.append((cleaned, norm_x, norm_y))

        # Sort left to right
        candidate_profiles.sort(key=lambda item: item[1])

        # Deduplicate spatially close labels (within 5% screen width)
        deduped: List[Tuple[str, float, float]] = []
        for name, nx, ny in candidate_profiles:
            if not deduped:
                deduped.append((name, nx, ny))
            else:
                last_name, last_nx, last_ny = deduped[-1]
                if abs(nx - last_nx) > 0.05:
                    deduped.append((name, nx, ny))
                elif len(name) > len(last_name):
                    # Replace with longer / clearer name
                    deduped[-1] = (name, nx, ny)

        slots: List[ProfileSlot] = []
        for idx, (name, nx, ny) in enumerate(deduped, start=1):
            slots.append(ProfileSlot(name=name, slot_index=idx, center_norm=(nx, ny)))

        return slots

    def inspect_state(
        self,
        image_np: Optional[np.ndarray] = None,
        force: bool = False,
    ) -> Tuple[NetflixState, List[ProfileSlot]]:
        """
        Snapshot inspect frontmost Netflix surface.
        Returns: (NetflixState, profiles)
        Execution is on-demand only (0 Hz when idle).
        """
        t0 = time.time()

        if not force and not self.is_netflix_frontmost():
            _LOGGER.debug("[NetflixDetector] Netflix is not frontmost. Skipping inspection.")
            return NetflixState.UNKNOWN, []

        # Acquire screenshot if not supplied
        if image_np is None:
            try:
                from actions.screen_processor import capture_screen
                screen_cap = capture_screen(monitor=1)
                if screen_cap is None:
                    return NetflixState.UNKNOWN, []
                image_np = np.array(screen_cap)
            except Exception as exc:
                _LOGGER.warning("[NetflixDetector] Screen capture failed: %s", exc)
                return NetflixState.UNKNOWN, []

        h, w = image_np.shape[:2]
        ocr = self._get_ocr()
        if ocr is None:
            _LOGGER.warning("[NetflixDetector] OCR engine unavailable.")
            return NetflixState.UNKNOWN, []

        # Run OCR
        tokens: List[Tuple[str, float, Tuple[float, float]]] = []
        try:
            results, _ = ocr(image_np)
            if results:
                for item in results:
                    box, (text, conf) = item[0], item[1]
                    if conf >= CONFIDENCE_THRESHOLD:
                        cx = sum(p[0] for p in box) / 4.0
                        cy = sum(p[1] for p in box) / 4.0
                        tokens.append((text, float(conf), (cx / w, cy / h)))
        except Exception as exc:
            _LOGGER.warning("[NetflixDetector] OCR execution failed: %s", exc)

        state, profiles = self.detect_state_from_tokens(tokens)
        elapsed = time.time() - t0
        _LOGGER.info(
            "[NetflixDetector] State: %s (%d profiles detected in %.2fs)",
            state.name, len(profiles), elapsed,
        )
        return state, profiles
