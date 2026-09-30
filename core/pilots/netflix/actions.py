"""
core/pilots/netflix/actions.py — Netflix Pilot Actions and Conversational Profile Gate.

Handles:
1. Conversational Profile Gate selection via one-shot AnswerWindow.
2. Typing and hotkey search automation with humanized delays.
3. First-result play targeting.
4. Terse, respectful ALFRED persona voice feedback.
"""
from __future__ import annotations

import difflib
import logging
import re
import time
import webbrowser
from typing import Callable, List, Optional, Tuple

from core.pilots.netflix.detector import (
    NetflixDetector,
    NetflixState,
    ProfileSlot,
)

# ── Named Constants ──────────────────────────────────────────────────────────
ANSWER_WINDOW_S: float = 6.0
KEY_DELAY_MS: int = 25
SETTLE_DELAY_MS: int = 1200
INSPECT_SETTLE_DELAY_S: float = 2.0

PROMPT_WHICH_PROFILE: str = "Which profile shall I select, sir?"
MSG_ACCESSING_PROFILE: str = "Accessing {profile}, sir."
MSG_PROFILE_NOT_FOUND: str = "I could not identify that profile, sir."
MSG_NOT_LOGGED_IN: str = "Netflix is not logged in on this browser, sir."
MSG_SEARCHING: str = "Searching Netflix for '{query}', sir."
MSG_PLAYING: str = "Playing '{title}', sir."
MSG_BROWSE_GENRE: str = "Browsing {genre} on Netflix, sir."
MSG_NETFLIX_READY: str = "Netflix is ready, sir."

NETFLIX_HOME_URL: str = "https://www.netflix.com"
NETFLIX_SEARCH_URL: str = "https://www.netflix.com/search?q={query}"
NETFLIX_GENRE_BASE_URL: str = "https://www.netflix.com/browse/genre/"

# Common Netflix Genre IDs
GENRE_MAP: dict[str, int] = {
    "action": 1365,
    "anime": 7424,
    "comedy": 6548,
    "comedies": 6548,
    "documentary": 6839,
    "documentaries": 6839,
    "drama": 5763,
    "dramas": 5763,
    "horror": 8711,
    "sci-fi": 1492,
    "scifi": 1492,
    "thriller": 8933,
    "thrillers": 8933,
}

SLOT_WORDS_MAP: dict[str, int] = {
    "1": 1, "one": 1, "first": 1, "1st": 1,
    "2": 2, "two": 2, "second": 2, "2nd": 2,
    "3": 3, "three": 3, "third": 3, "3rd": 3,
    "4": 4, "four": 4, "fourth": 4, "4th": 4,
    "5": 5, "five": 5, "fifth": 5, "5th": 5,
}

_LOGGER = logging.getLogger(__name__)


def match_profile_selection(
    user_input: str,
    profiles: List[ProfileSlot],
) -> Optional[ProfileSlot]:
    """
    Match spoken user input to one of the detected profile slots.
    Accepts ordinal/slot numbers ("first", "second", "one", "2") or name matching.
    """
    raw = (user_input or "").strip().lower()
    if not raw or not profiles:
        return None

    # 1. Match slot number or ordinal word
    words = re.findall(r"\w+", raw)
    for w in words:
        if w in SLOT_WORDS_MAP:
            target_idx = SLOT_WORDS_MAP[w]
            for p in profiles:
                if p.slot_index == target_idx:
                    return p

    # 2. Exact or substring name match
    for p in profiles:
        p_low = p.name.lower()
        if p_low == raw or p_low in raw or raw in p_low:
            return p

    # 3. Fuzzy name match
    names = [p.name.lower() for p in profiles]
    matches = difflib.get_close_matches(raw, names, n=1, cutoff=0.6)
    if matches:
        matched_name = matches[0]
        for p in profiles:
            if p.name.lower() == matched_name:
                return p

    return None


class NetflixActions:
    """Automates Netflix UI interactions: profile selection, search, and playback."""

    def __init__(
        self,
        detector: Optional[NetflixDetector] = None,
        speak_fn: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.detector = detector or NetflixDetector()
        self.speak_fn = speak_fn

    def _speak(self, text: str) -> None:
        if self.speak_fn:
            try:
                self.speak_fn(text)
            except Exception as exc:
                _LOGGER.warning("[NetflixActions] Failed to speak: %s", exc)
        print(f"[Netflix] {text}")

    def _get_answer_window(self):
        from core.sentry.answer_window import AnswerWindow
        return AnswerWindow(speak_fn=self.speak_fn)

    def select_profile(
        self,
        profile: ProfileSlot,
    ) -> bool:
        """Activate profile via coordinate click or targeted keyboard Tab navigation."""
        try:
            import pyautogui
            sw, sh = pyautogui.size()
            nx, ny = profile.center_norm
            target_x = int(nx * sw)
            target_y = int(ny * sh)
            _LOGGER.info(
                "[NetflixActions] Targeting profile '%s' (slot %d) at (%d, %d)",
                profile.name, profile.slot_index, target_x, target_y,
            )
            pyautogui.click(target_x, target_y)
            return True
        except Exception as exc:
            _LOGGER.warning("[NetflixActions] Coordinate click failed (%s), using keyboard fallback.", exc)
            try:
                import pyautogui
                # Tab navigation fallback: Tab slot_index times from initial gate focus, then Enter
                for _ in range(profile.slot_index):
                    pyautogui.press("tab")
                    time.sleep(KEY_DELAY_MS / 1000.0)
                pyautogui.press("enter")
                return True
            except Exception as exc2:
                _LOGGER.error("[NetflixActions] Keyboard fallback also failed: %s", exc2)
                return False

    def handle_profile_gate(
        self,
        profiles: List[ProfileSlot],
        answer_window: Optional[Any] = None,
        timeout_s: float = ANSWER_WINDOW_S,
    ) -> Tuple[bool, str]:
        """
        Interactive conversational profile selection flow.
        ALFRED speaks: 'Which profile shall I select, sir?'
        Opens single-utterance mic window (no wake word needed).
        """
        ans_win = answer_window or self._get_answer_window()
        user_answer = ans_win.request_answer_sync(
            prompt_speech=PROMPT_WHICH_PROFILE,
            timeout_s=timeout_s,
        )

        if not user_answer:
            _LOGGER.info("[NetflixActions] Profile selection timed out without answer.")
            return False, "No profile specified."

        matched = match_profile_selection(user_answer, profiles)
        if not matched:
            self._speak(MSG_PROFILE_NOT_FOUND)
            return False, MSG_PROFILE_NOT_FOUND

        ok = self.select_profile(matched)
        if ok:
            confirm = MSG_ACCESSING_PROFILE.format(profile=matched.name)
            self._speak(confirm)
            return True, confirm

        return False, "Failed to activate profile."

    def open_netflix(
        self,
        answer_window: Optional[Any] = None,
    ) -> str:
        """
        Open Netflix, check state on launch, and navigate profile gate if present.
        """
        webbrowser.open(NETFLIX_HOME_URL)
        time.sleep(INSPECT_SETTLE_DELAY_S)

        state, profiles = self.detector.inspect_state(force=True)

        if state == NetflixState.NOT_LOGGED_IN:
            self._speak(MSG_NOT_LOGGED_IN)
            return MSG_NOT_LOGGED_IN

        if state == NetflixState.PROFILE_GATE:
            _, msg = self.handle_profile_gate(profiles, answer_window=answer_window)
            return msg

        if state in (NetflixState.BROWSE_HOME, NetflixState.PLAYING):
            self._speak(MSG_NETFLIX_READY)
            return MSG_NETFLIX_READY

        return "Opened Netflix, sir."

    def search_netflix(
        self,
        query: str,
    ) -> str:
        """
        Search Netflix for query by focusing search hotkey or navigating directly.
        Keystrokes use humanized KEY_DELAY_MS.
        """
        clean_query = query.strip()
        speech = MSG_SEARCHING.format(query=clean_query)
        self._speak(speech)

        if self.detector.is_netflix_frontmost():
            try:
                import pyautogui
                # Focus search via '/' key or click
                pyautogui.press("/")
                time.sleep(KEY_DELAY_MS / 1000.0)
                # Type query with humanized delay
                pyautogui.typewrite(clean_query, interval=KEY_DELAY_MS / 1000.0)
                pyautogui.press("enter")
                return speech
            except Exception as exc:
                _LOGGER.warning("[NetflixActions] In-page search hotkey failed (%s), opening URL.", exc)

        # Fallback / Direct navigation
        from urllib.parse import quote_plus
        url = NETFLIX_SEARCH_URL.format(query=quote_plus(clean_query))
        webbrowser.open(url)
        return speech

    def play_netflix(
        self,
        title: str,
    ) -> str:
        """
        Execute search, settle on results grid, target first card, and trigger playback.
        """
        clean_title = title.strip()
        self.search_netflix(clean_title)

        time.sleep(SETTLE_DELAY_MS / 1000.0)

        # Target first search result
        try:
            import pyautogui
            sw, sh = pyautogui.size()
            # The first search result on Netflix grid is located at ~25% width, ~32% height
            first_card_x = int(0.25 * sw)
            first_card_y = int(0.32 * sh)
            pyautogui.click(first_card_x, first_card_y)
            time.sleep(0.3)
            # Send Enter or Space to ensure playback engages
            pyautogui.press("enter")
        except Exception as exc:
            _LOGGER.warning("[NetflixActions] Failed to target first card: %s", exc)

        speech = MSG_PLAYING.format(title=clean_title)
        self._speak(speech)
        return speech

    def browse_genre(
        self,
        genre: str,
    ) -> str:
        """Browse specific genre on Netflix."""
        clean_genre = genre.strip().lower()
        speech = MSG_BROWSE_GENRE.format(genre=clean_genre.capitalize())
        self._speak(speech)

        genre_id = GENRE_MAP.get(clean_genre)
        if genre_id:
            url = f"{NETFLIX_GENRE_BASE_URL}{genre_id}"
            webbrowser.open(url)
        else:
            self.search_netflix(clean_genre)

        return speech


_GLOBAL_NETFLIX_ACTIONS: Optional[NetflixActions] = None


def get_netflix_actions() -> NetflixActions:
    global _GLOBAL_NETFLIX_ACTIONS
    if _GLOBAL_NETFLIX_ACTIONS is None:
        _GLOBAL_NETFLIX_ACTIONS = NetflixActions()
    return _GLOBAL_NETFLIX_ACTIONS
