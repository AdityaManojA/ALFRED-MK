"""
core/hud_video/destination.py — Play destination prompting, explicit routing, and preference memory.

Flow:
1. "Play X" with no destination given:
   - ALFRED: "In the app, sir?"
   - Open answer window (ANSWER_WINDOW_S = 8.0).
2. Yes -> play in Visual HUD.
3. No -> ALFRED: "Default player, YouTube, or another window, sir?"
   - Default: OS default player / browser.
   - YouTube: YouTube result in default browser.
   - Another window: ALFRED: "Which one, sir?" -> opens in named app/browser. If unknown, speaks "Can't find that, sir."
4. Skip question when request already names a destination ("in the app", "on YouTube", "in Chrome").
5. Silence or unclear: re-ask once (DEST_REASK_MAX = 1), then cancel with toast "Cancelled, sir."
6. Memory preference: "always play in the app" saves preference, "ask me again" clears it.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import urllib.parse
import webbrowser
from typing import Any, Callable, Optional, Tuple

from core.hud_video.intent import VIDEO_LOCUS_PHRASES, PLAY_INTENT_WORDS
from memory.config_manager import (
    get_video_play_destination,
    save_video_play_destination,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

ANSWER_WINDOW_S: float = 8.0
DEST_REASK_MAX: int = 1
REMEMBER_DEST: bool = True

PROMPT_IN_APP: str = "In the app, sir?"
PROMPT_CHOICE: str = "Default player, YouTube, or another window, sir?"
PROMPT_WHICH_APP: str = "Which one, sir?"
LINE_APP_NOT_FOUND: str = "Can't find that, sir."
TOAST_CANCELLED: str = "Cancelled, sir."
TOAST_PREF_SAVED: str = "Preference saved: always play in the app, sir."
TOAST_PREF_CLEARED: str = "Preference cleared, sir."

# Known browser and player aliases
KNOWN_APP_EXECUTABLES: dict[str, dict[str, str]] = {
    "chrome":             {"Windows": "chrome",         "Darwin": "Google Chrome",        "Linux": "google-chrome"},
    "google chrome":      {"Windows": "chrome",         "Darwin": "Google Chrome",        "Linux": "google-chrome"},
    "firefox":            {"Windows": "firefox",        "Darwin": "Firefox",              "Linux": "firefox"},
    "edge":               {"Windows": "msedge",         "Darwin": "Microsoft Edge",       "Linux": "microsoft-edge"},
    "msedge":             {"Windows": "msedge",         "Darwin": "Microsoft Edge",       "Linux": "microsoft-edge"},
    "brave":              {"Windows": "brave",          "Darwin": "Brave Browser",        "Linux": "brave-browser"},
    "safari":             {"Windows": "msedge",         "Darwin": "Safari",               "Linux": "firefox"},
    "opera":              {"Windows": "opera",          "Darwin": "Opera",                "Linux": "opera"},
    "vlc":                {"Windows": "vlc",            "Darwin": "VLC",                  "Linux": "vlc"},
    "mpv":                {"Windows": "mpv",            "Darwin": "mpv",                  "Linux": "mpv"},
    "media player":       {"Windows": "wmplayer",       "Darwin": "QuickTime Player",     "Linux": "totem"},
}


# ---------------------------------------------------------------------------
# Preference & Destination Parser
# ---------------------------------------------------------------------------

def check_preference_command(text: str) -> tuple[bool, str, str | None]:
    """Check for 'always play in the app' or 'ask me again' commands.

    Returns: (is_pref_command, user_response_string, new_pref_value)
    """
    lower = (text or "").lower().strip()
    if re.search(r"\b(always\s+(play\s+)?in\s+(the\s+)?(app|hud|player|batcomputer))\b", lower):
        save_video_play_destination("app")
        return (True, TOAST_PREF_SAVED, "app")

    if re.search(r"\b(ask\s+(me\s+)?again|reset\s+(play\s+)?destination|forget\s+(play\s+)?destination|clear\s+(play\s+)?preference)\b", lower):
        save_video_play_destination(None)
        return (True, TOAST_PREF_CLEARED, None)

    return (False, "", None)


def parse_explicit_destination(text: str) -> tuple[str | None, str, str | None]:
    """Inspect utterance for explicit destination mentions.

    Returns: (dest_kind, clean_query, app_name)
      dest_kind: "app" | "youtube" | "default" | "window" | None
    """
    lower = (text or "").lower().strip()

    # 1. In App / Visual HUD
    for phrase in VIDEO_LOCUS_PHRASES:
        if phrase in lower:
            clean = re.sub(re.escape(phrase), "", text, flags=re.IGNORECASE).strip()
            clean = _clean_play_verbs(clean)
            return ("app", clean, None)

    # 2. YouTube
    yt_patterns = [r"\bon youtube\b", r"\bin youtube\b", r"\bon yt\b", r"\bin yt\b"]
    for pat in yt_patterns:
        if re.search(pat, lower):
            clean = re.sub(pat, "", text, flags=re.IGNORECASE).strip()
            clean = _clean_play_verbs(clean)
            return ("youtube", clean, None)

    # 3. Default player / browser
    def_patterns = [
        r"\bin (the )?default player\b",
        r"\bin default\b",
        r"\bon default\b",
        r"\bin (the )?system player\b",
        r"\bin (the )?default browser\b",
        r"\bin (the )?browser\b",
    ]
    for pat in def_patterns:
        if re.search(pat, lower):
            clean = re.sub(pat, "", text, flags=re.IGNORECASE).strip()
            clean = _clean_play_verbs(clean)
            return ("default", clean, None)

    # 4. Specific App / Window
    for app_name in KNOWN_APP_EXECUTABLES:
        pattern = rf"\bin {re.escape(app_name)}\b|\bon {re.escape(app_name)}\b"
        if re.search(pattern, lower):
            clean = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()
            clean = _clean_play_verbs(clean)
            return ("window", clean, app_name)

    # No destination specified
    clean = _clean_play_verbs(text)
    return (None, clean, None)


def _clean_play_verbs(query: str) -> str:
    """Remove leading play/watch/show/stream filler verbs."""
    clean = query.strip()
    for verb in PLAY_INTENT_WORDS:
        pattern = rf"^\s*{re.escape(verb)}\s+"
        clean = re.sub(pattern, "", clean, flags=re.IGNORECASE).strip()
    # Strip common filler
    clean = re.sub(r"^(me|us|the|a|an)\s+", "", clean, flags=re.IGNORECASE).strip()
    return clean


# ---------------------------------------------------------------------------
# Answer Classifier Helpers
# ---------------------------------------------------------------------------

def classify_yes_no(answer: str) -> str | None:
    """Classify user response to 'In the app, sir?' -> 'yes', 'no', or None."""
    lower = (answer or "").lower().strip()
    if not lower:
        return None

    # Check for direct destination keywords first
    if any(w in lower for w in ("youtube", "yt", "default", "browser", "chrome", "firefox", "vlc", "edge", "brave")):
        return "no"

    if re.search(r"\b(yes|yeah|yep|yup|sure|in the app|in app|app|hud|player|affirmative|please|do it|play it|play)\b", lower):
        return "yes"

    if re.search(r"\b(no|nope|nah|negative|outside|external|other|somewhere else)\b", lower):
        return "no"

    return None


def classify_dest_choice(answer: str) -> tuple[str | None, str | None]:
    """Classify response to 'Default player, YouTube, or another window, sir?'.

    Returns: (dest_kind, app_name)
    """
    lower = (answer or "").lower().strip()
    if not lower:
        return (None, None)

    if re.search(r"\b(youtube|yt)\b", lower):
        return ("youtube", None)

    if re.search(r"\b(default|default player|system player|browser|system|os default)\b", lower):
        return ("default", None)

    # Check for directly named apps
    for app in KNOWN_APP_EXECUTABLES:
        if re.search(rf"\b{re.escape(app)}\b", lower):
            return ("window", app)

    if re.search(r"\b(another window|other window|another app|other app|window|external app)\b", lower):
        return ("window", None)

    return (None, None)


def is_known_app(app_name: str) -> bool:
    """Check if app name is recognized in aliases or system PATH."""
    clean = (app_name or "").lower().strip()
    if clean in KNOWN_APP_EXECUTABLES:
        return True
    return bool(shutil.which(clean) or shutil.which(clean.split(".")[0]))


# ---------------------------------------------------------------------------
# Execution Handlers
# ---------------------------------------------------------------------------

def execute_destination(
    dest_kind: str,
    target: str,
    start_s: float | None = None,
    controller: Any = None,
    speak: Callable[[str], None] | None = None,
    app_name: str | None = None,
) -> str:
    """Route target playback to selected destination.

    Privacy rule: Only hosts are logged, never signed tokens.
    Speech rule: Confirmations are toasts only; speak only on fatal failure.
    """
    clean_target = (target or "").strip()
    if not clean_target:
        return "No target specified."

    if dest_kind == "app":
        # Visual HUD path
        if controller:
            controller.show_toast(f"Visual HUD: {clean_target[:40]}")
            # Use hud_video background resolve
            from actions.hud_video import _resolve_and_play
            controller.begin_resolve(f"Searching: {clean_target[:40]}…", source_query=clean_target)
            t = threading.Thread(
                target=_resolve_and_play,
                args=(clean_target, speak, controller, start_s, 0),
                daemon=True,
                name="hud-video-dest-play",
            )
            t.start()
        return f"Playing {clean_target} on the Visual HUD."

    if dest_kind == "youtube":
        encoded = urllib.parse.quote_plus(clean_target)
        url = f"https://www.youtube.com/results?search_query={encoded}"
        host = urllib.parse.urlparse(url).netloc
        log.info("[hud_video] opening YouTube host: %s", host)
        if controller:
            controller.show_toast(f"Opening YouTube: {clean_target[:40]}")
        webbrowser.open(url)
        return f"Opening {clean_target} on YouTube."

    if dest_kind == "default":
        # If target looks like a local file or direct URL, open directly
        if os.path.isfile(clean_target):
            log.info("[hud_video] opening local file in default player")
            if controller:
                controller.show_toast(f"Opening file: {os.path.basename(clean_target)}")
            if sys.platform == "win32":
                os.startfile(clean_target)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", clean_target])
            else:
                subprocess.Popen(["xdg-open", clean_target])
            return f"Opening {clean_target} in default player."

        # Search query -> open in default browser
        encoded = urllib.parse.quote_plus(clean_target)
        url = f"https://www.youtube.com/results?search_query={encoded}"
        host = urllib.parse.urlparse(url).netloc
        log.info("[hud_video] opening default player host: %s", host)
        if controller:
            controller.show_toast(f"Opening in default player: {clean_target[:40]}")
        webbrowser.open(url)
        return f"Opening {clean_target} in default player."

    if dest_kind == "window":
        chosen_app = (app_name or "").lower().strip()
        if not is_known_app(chosen_app):
            log.warning("[hud_video] unknown application requested: %s", chosen_app)
            if speak:
                speak(LINE_APP_NOT_FOUND)
            if controller:
                controller.show_toast(f"App not found: {chosen_app}")
            return f"Cannot find application {chosen_app}."

        encoded = urllib.parse.quote_plus(clean_target)
        url = f"https://www.youtube.com/results?search_query={encoded}"
        host = urllib.parse.urlparse(url).netloc
        log.info("[hud_video] opening in %s host: %s", chosen_app, host)
        if controller:
            controller.show_toast(f"Opening in {chosen_app}: {clean_target[:40]}")

        # Resolve platform executable
        plat = "Windows" if sys.platform == "win32" else ("Darwin" if sys.platform == "darwin" else "Linux")
        exe = KNOWN_APP_EXECUTABLES.get(chosen_app, {}).get(plat, chosen_app)

        try:
            subprocess.Popen([exe, url])
        except Exception as exc:
            log.warning("[hud_video] Popen failed for %s: %s; falling back to webbrowser", exe, exc)
            webbrowser.open(url)

        return f"Opening {clean_target} in {chosen_app}."

    return f"Unknown destination {dest_kind}."


# ---------------------------------------------------------------------------
# Play Destination Prompt Manager
# ---------------------------------------------------------------------------

class PlayDestinationManager:
    """Coordinates conversational destination prompting with single-flight guard."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._is_prompting: bool = False
        self._active_target: str = ""
        self._answer_window = None

    @property
    def is_prompting(self) -> bool:
        with self._lock:
            return self._is_prompting

    def _get_answer_window(self, speak: Callable[[str], None] | None):
        """Retrieve or create an AnswerWindow instance."""
        from core.sentry.answer_window import AnswerWindow
        if self._answer_window is None:
            self._answer_window = AnswerWindow(speak_fn=speak)
        else:
            if speak:
                self._answer_window.set_callbacks(speak_fn=speak, un_gate_fn=None)
        return self._answer_window

    def submit_answer(self, text: str) -> bool:
        """Feed text from STT or chat into the destination prompt window."""
        with self._lock:
            if not self._is_prompting or self._answer_window is None:
                return False
        return self._answer_window.submit_answer(text)

    def cancel(self, controller: Any = None) -> None:
        """Cancel active destination prompt and reset state."""
        with self._lock:
            self._is_prompting = False
            self._active_target = ""
            if self._answer_window:
                self._answer_window.cancel()
        if controller:
            controller.show_toast(TOAST_CANCELLED)

    def start_flow(
        self,
        target: str,
        start_s: float | None = None,
        controller: Any = None,
        speak: Callable[[str], None] | None = None,
    ) -> str:
        """Initiate asynchronous destination question flow.

        Returns immediately with a terminal confirmation string.
        """
        with self._lock:
            if self._is_prompting:
                return "Visual HUD is already asking for play destination."
            self._is_prompting = True
            self._active_target = target

        t = threading.Thread(
            target=self._worker_flow,
            args=(target, start_s, controller, speak),
            daemon=True,
            name="hud-video-dest-flow",
        )
        t.start()
        return f"Asked destination for {target}."

    def _worker_flow(
        self,
        target: str,
        start_s: float | None,
        controller: Any,
        speak: Callable[[str], None] | None,
    ) -> None:
        """Sequential conversational workflow across answer windows."""
        ans_win = self._get_answer_window(speak)
        reask_count = 0

        try:
            # ── 1. Question 1: "In the app, sir?" ────────────────────────────
            q1_ans = ""
            while True:
                q1_ans = ans_win.request_answer_sync(PROMPT_IN_APP, timeout_s=ANSWER_WINDOW_S)
                if q1_ans:
                    break
                if reask_count < DEST_REASK_MAX:
                    reask_count += 1
                    continue
                # Timed out after max re-asks
                self.cancel(controller)
                return

            # Check direct destination in answer 1
            explicit_dest, clean_q, explicit_app = parse_explicit_destination(q1_ans)
            if explicit_dest:
                with self._lock:
                    self._is_prompting = False
                execute_destination(
                    explicit_dest,
                    target,
                    start_s,
                    controller,
                    speak,
                    app_name=explicit_app,
                )
                return

            choice1 = classify_yes_no(q1_ans)
            if choice1 == "yes":
                with self._lock:
                    self._is_prompting = False
                execute_destination("app", target, start_s, controller, speak)
                return

            if choice1 is None and reask_count < DEST_REASK_MAX:
                # Re-ask Q1
                reask_count += 1
                q1_ans = ans_win.request_answer_sync(PROMPT_IN_APP, timeout_s=ANSWER_WINDOW_S)
                choice1 = classify_yes_no(q1_ans)
                if choice1 == "yes":
                    with self._lock:
                        self._is_prompting = False
                    execute_destination("app", target, start_s, controller, speak)
                    return
                elif choice1 != "no":
                    self.cancel(controller)
                    return

            # ── 2. Question 2: "Default player, YouTube, or another window, sir?" ──
            reask_count = 0
            q2_ans = ""
            while True:
                q2_ans = ans_win.request_answer_sync(PROMPT_CHOICE, timeout_s=ANSWER_WINDOW_S)
                if q2_ans:
                    break
                if reask_count < DEST_REASK_MAX:
                    reask_count += 1
                    continue
                self.cancel(controller)
                return

            choice2, named_app = classify_dest_choice(q2_ans)
            if choice2 == "youtube":
                with self._lock:
                    self._is_prompting = False
                execute_destination("youtube", target, start_s, controller, speak)
                return

            if choice2 == "default":
                with self._lock:
                    self._is_prompting = False
                execute_destination("default", target, start_s, controller, speak)
                return

            if choice2 == "window" and named_app:
                with self._lock:
                    self._is_prompting = False
                execute_destination("window", target, start_s, controller, speak, app_name=named_app)
                return

            if choice2 == "window" and not named_app:
                # ── 3. Question 3: "Which one, sir?" ─────────────────────────
                reask_count = 0
                q3_ans = ""
                while True:
                    q3_ans = ans_win.request_answer_sync(PROMPT_WHICH_APP, timeout_s=ANSWER_WINDOW_S)
                    if q3_ans:
                        break
                    if reask_count < DEST_REASK_MAX:
                        reask_count += 1
                        continue
                    self.cancel(controller)
                    return

                with self._lock:
                    self._is_prompting = False
                execute_destination("window", target, start_s, controller, speak, app_name=q3_ans.strip().lower())
                return

            # If unclear response to Q2, try re-ask once
            if reask_count < DEST_REASK_MAX:
                reask_count += 1
                q2_ans = ans_win.request_answer_sync(PROMPT_CHOICE, timeout_s=ANSWER_WINDOW_S)
                choice2, named_app = classify_dest_choice(q2_ans)
                if choice2 == "youtube":
                    with self._lock:
                        self._is_prompting = False
                    execute_destination("youtube", target, start_s, controller, speak)
                    return
                if choice2 == "default":
                    with self._lock:
                        self._is_prompting = False
                    execute_destination("default", target, start_s, controller, speak)
                    return
                if choice2 == "window":
                    app_to_use = named_app or "chrome"
                    with self._lock:
                        self._is_prompting = False
                    execute_destination("window", target, start_s, controller, speak, app_name=app_to_use)
                    return

            self.cancel(controller)

        finally:
            with self._lock:
                self._is_prompting = False


# Global singleton
_destination_manager = PlayDestinationManager()


def get_destination_manager() -> PlayDestinationManager:
    """Return the global PlayDestinationManager instance."""
    return _destination_manager
