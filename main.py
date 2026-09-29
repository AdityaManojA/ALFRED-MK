import platform as _platform
import subprocess as _subprocess

# â”€â”€ Force Windows to decouple taskbar icon from generic python.exe â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if _platform.system() == "Windows":
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("alfred.wayne.batcomputer.mk4")
    except Exception:
        pass

# â”€â”€ Nuclear: force CREATE_NO_WINDOW on EVERY subprocess call on Windows â”€â”€â”€â”€â”€â”€â”€
# This patches Popen itself, so no per-file flag is needed anywhere.
if _platform.system() == "Windows":
    _OrigPopen = _subprocess.Popen

    class _Popen(_OrigPopen):
        def __init__(self, args, **kw):
            kw["creationflags"] = kw.get("creationflags", 0) | _subprocess.CREATE_NO_WINDOW
            kw.pop("startupinfo", None)   # drop any stale/shared STARTUPINFO
            super().__init__(args, **                       kw)

    _subprocess.Popen = _Popen


# â”€â”€ Console must survive non-UTF-8 code pages â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Every status line in this file carries an emoji, and on a legacy Windows
# console the active code page is the system one â€” cp1254 in Turkey, cp1251 in
# Russia, cp932 in Japan. Printing an emoji there raises UnicodeEncodeError, and
# because most of these prints sit inside the receive loop it takes the session
# down on startup. Reconfiguring to UTF-8 with a replacement fallback costs
# nothing and makes the app launch the same way in every locale.
import sys as _sys

for _stream in ("stdout", "stderr"):
    try:
        _s = getattr(_sys, _stream, None)
        if _s is not None and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass          # pythonw / redirected pipes / anything exotic â€” never fatal

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

from core.logger import install_timestamped_logging
install_timestamped_logging()

# Suppress FFmpeg AV1 hwaccel noise before QApplication is constructed.
# Qt reads QT_LOGGING_RULES at init time; setting it here ensures it's in
# place even if the user hasn't set it in their environment.
import os as _os
_os.environ.setdefault("QT_LOGGING_RULES", "qt.multimedia.ffmpeg=false")

# Crash reporting
import traceback
import sys
import threading
from datetime import datetime
from pathlib import Path

def log_unhandled_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    crash_msg = f"\n{'='*60}\nCRASH REPORT - {timestamp}\n{'='*60}\n"
    crash_msg += f"Exception: {exc_type.__name__}: {exc_value}\n"
    crash_msg += "Traceback:\n"
    crash_msg += ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    crash_msg += f"\n{'='*60}\n"
    try:
        crash_dir = Path(__file__).resolve().parent / "config"
        crash_dir.mkdir(exist_ok=True)
        crash_file = crash_dir / "crash.log"
        with open(crash_file, "a", encoding="utf-8") as f:
            f.write(crash_msg)
    except Exception:
        pass
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

# Also set threading excepthook for threads
threading.excepthook = lambda args: log_unhandled_exception(args.exc_type, args.exc_value, args.exc_traceback)

import asyncio
import base64
import gc
import re
import secrets
import threading
import time
import json
import sys
import traceback

# â”€â”€ Real-time audio & UI Garbage Collection tuning â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# By default Python uses (700, 10, 10). Under heavy streaming audio and PyQt
# animation churn, full Generation 2 mark-and-sweep collections trigger every
# 20-40 seconds, stopping all threads for 50-120 ms. This causes simultaneous
# UI frame drops and audio buffer starvation (dropouts).
# Raising thresholds minimizes involuntary stop-the-world sweeps during interaction.
gc.set_threshold(70000, 15, 15)
from datetime import datetime
from pathlib import Path

import sounddevice as sd
import numpy as np
from google import genai
from google.genai import types
from ui import JarvisUI
from memory.memory_manager import (
    load_memory, update_memory, format_memory_for_prompt,
    save_session_summary, pop_last_session,
    search_memory, set_trim_notifier,
)

# The file-backed tools (open_app, web_search, browser_control, â€¦) are no longer
# imported or declared here â€” they self-describe via a TOOL dict in their own
# actions/*.py file and are auto-discovered by core.action_loader at startup.
# Only tools that are tied to live-session state stay inline in this file
# (screen_process, close_camera, save_memory, manage_monitor, shutdown_jarvis,
# system_status).
from actions.screen_processor  import _capture_camera, _capture_screen
from actions.screen_monitor import ScreenMonitorController, ScreenMonitorEvent, ScreenMonitorStatus
from actions.system_monitor    import SystemMonitor, get_system_status
from actions.proactive         import ProactiveEngine
from actions.background_monitor import (
    add_monitor, remove_monitor, list_monitors, check_all as monitor_check_all,
)
from actions.web_search        import _news as _fetch_news_sync
from memory.config_manager     import (
    get_brief_enabled, get_media_resolution, get_proactive_audio_enabled,
    get_push_to_talk_enabled, get_thinking_enabled, get_turn_tuning, get_voice,
    get_wake_word_enabled, save_wake_word_enabled,    get_input_device, get_output_device,
)
from core.plugin_loader        import discover_plugins
from core                      import undo as undo_stack
from core                      import confirm as confirm_gate
from core                      import audio_devices
from core.action_loader        import discover_actions
from core.echo                 import EchoGuard
from core.viseme               import VisemeStream
from core.wake_word            import (
    WakeWordDetector, is_ready as wake_is_ready, install_and_download as wake_install,
    WAKE_PHRASE,
)
# Local pipeline imports
from core.local_stt            import create_local_stt_engine
from core.local_ttt            import create_local_tts_engine
from core.local_pipeline       import create_local_pipeline

# How long the assistant stays awake with no user speech before it auto-sleeps
# again (wake-word mode only).
WAKE_SLEEP_TIMEOUT = 120.0   # seconds (2 minutes)

def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR        = get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
PROMPT_PATH     = BASE_DIR / "core" / "prompt.txt"
LIVE_MODEL          = "models/gemini-3.1-flash-live-preview"
CHANNELS            = 1
SEND_SAMPLE_RATE    = 16000 
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE          = 1024

# RMS below which 16-bit PCM is treated as room silence; above _LEVEL_FULL it
# reads as a full-height waveform. Tuned so ordinary speech lands mid-range and
# the bars still move for a quiet talker â€” language- and device-independent.
_LEVEL_FLOOR = 60.0
_LEVEL_FULL  = 2600.0

_RED   = "\033[91m"
_RESET = "\033[0m"

def _tlog(tag: str, icon_tag: str = "", text: str = "", dashboard=None):
    """Format terminal log report without emojis using red bracketed tags, and broadcast to dashboard."""
    if icon_tag:
        line = f"{_RED}[{tag}]{_RESET} {_RED}[{icon_tag}]{_RESET} {text}".strip()
    else:
        line = f"{_RED}[{tag}]{_RESET} {text}".strip()
    print(line)
    if dashboard:
        msg = {
            "type": "telemetry",
            "tag": tag,
            "icon": icon_tag,
            "text": text,
        }
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                loop.create_task(dashboard.broadcast(msg))
        except RuntimeError:
            dash_loop = getattr(dashboard, "_loop", None)
            if dash_loop and dash_loop.is_running():
                try:
                    asyncio.run_coroutine_threadsafe(dashboard.broadcast(msg), dash_loop)
                except Exception:
                    pass
        except Exception:
            pass


from core.path_guard import (
    is_heavenly_restricted as _guard_is_heavenly_restricted,
    check_action_params as _guard_check_action_params,
)


def _is_heavenly_restricted(val) -> bool:
    """Check if any argument references the restricted Personal-Assistant directory."""
    return _guard_is_heavenly_restricted(val)



def _pcm_level(samples) -> float:
    """Map a block of int16 PCM samples to a 0.0â€“1.0 loudness level for the HUD
    waveform. Returns 0.0 on empty/invalid input so it can never raise."""
    try:
        x = np.asarray(samples, dtype=np.float32)
        if x.size == 0:
            return 0.0
        rms = float(np.sqrt(np.mean(x * x)))
    except Exception:
        return 0.0
    if rms <= _LEVEL_FLOOR:
        return 0.0
    return min(1.0, (rms - _LEVEL_FLOOR) / (_LEVEL_FULL - _LEVEL_FLOOR))


# â”€â”€ Viseme extraction â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# The avatar's mouth used to be driven by one RMS value per ~200 ms write batch,
# which is five updates a second averaged over a fifth of a second â€” it could
# only ever flap. These read the *shape* of each 20 ms slice straight from the
# spectrum of the audio being played, so no transcript, no forced alignment and
# no language assumption: it works the same for Turkish and English.
#
# Two numbers come out. Openness tracks the first formant â€” F1 climbs as the jaw
# drops, so /a/ reads open and /i/ or /u/ read closed. Width tracks the second â€”
# F2 is high for spread vowels (/i/, /e/) and low for rounded ones (/u/, /o/).
# Extra time beyond the device's reported output latency before the microphone
# is trusted again: covers room decay and the speaker's own settling.
_TAIL_MARGIN = 0.25

_VIS_WIN = 1024        # ~43 ms analysis window at 24 kHz: enough for formants
_VIS_HOP = 480         # 20 ms between frames, i.e. 50 shapes a second

# Delay from handing the first bytes of a reply to an already-running output
# stream to hearing them: one callback period, plus whatever the DAC adds.
_FIRST_SOUND = CHUNK_SIZE / RECEIVE_SAMPLE_RATE      # ~43 ms
# How far past the device's own buffer the mouth's timeline may drift before it
# is re-anchored. The buffer is the hard limit on how much audio can be queued
# ahead, so anything beyond it plus a margin for clock error is impossible.
_CURSOR_SLACK = 0.15

# Erring early is the safe direction. A viewer tolerates a mouth that moves
# slightly before the sound far better than one that moves after it â€” the
# broadcast limits are about 45 ms of lag against 125 ms of lead â€” so where
# this is uncertain it is biased to lead.


def _pcm_visemes(samples, sr: int = 24000):
    """Slice a PCM block into (level, openness, width) frames, one per 20 ms.

    Returns [] on anything unexpected â€” the mouth falls back to loudness-only
    articulation rather than the caller having to handle an error.
    """
    try:
        x = np.asarray(samples, dtype=np.float32)
        if x.size < _VIS_WIN:
            return []
        win = np.hanning(_VIS_WIN).astype(np.float32)
        freqs = np.fft.rfftfreq(_VIS_WIN, 1.0 / sr)
        b_f1_lo = (freqs >= 150) & (freqs < 450)     # F1 of close vowels
        b_f1_hi = (freqs >= 450) & (freqs < 1100)    # F1 of open vowels
        b_f2_bk = (freqs >= 600) & (freqs < 1300)    # F2 of rounded vowels
        b_f2_fr = (freqs >= 1700) & (freqs < 3200)   # F2 of spread vowels
        b_hiss = (freqs >= 3800) & (freqs < 8000)    # fricatives

        # One frame per hop across the *whole* block. Stepping only while a full
        # window fits stopped 1024 - 480 samples short of the end, so a 200 ms
        # batch yielded 160 ms of schedule: the mouth ran out of frames before
        # the audio ran out of sound, and each batch no longer lined up with the
        # end of the one before it. Losing 20 % of every batch is most of why
        # the mouth did not track the words.
        out = []
        for start in range(0, x.size, _VIS_HOP):
            # The level gates closures, so it is measured over exactly this
            # 20 ms and never looks ahead. The spectrum needs a longer window
            # to resolve formants and may be short-filled at the very end.
            level = _pcm_level(x[start:start + _VIS_HOP])
            seg = x[start:start + _VIS_WIN]
            if seg.size < _VIS_WIN:
                seg = np.concatenate([seg, np.zeros(_VIS_WIN - seg.size,
                                                    dtype=np.float32)])
            if level <= 0.0:
                out.append((0.0, 0.0, 0.0))
                continue
            mag = np.abs(np.fft.rfft((seg - seg.mean()) * win))
            f1l, f1h = float(mag[b_f1_lo].sum()), float(mag[b_f1_hi].sum())
            f2b, f2f = float(mag[b_f2_bk].sum()), float(mag[b_f2_fr].sum())
            hiss = float(mag[b_hiss].sum())

            openness = f1h / (f1l + f1h + 1e-6)
            width = (f2f - f2b) / (f2f + f2b + 1e-6)
            # A wide-open jaw physically cannot purse, so openness damps width.
            # /a/ has a low enough F2 to read as "rounded" on the bands alone;
            # letting openness suppress the width term is what keeps an open
            # vowel from pursing.
            width *= (1.0 - openness) ** 0.8
            # Fricatives are formed with a nearly closed mouth.
            h = hiss / (f1l + f1h + f2b + f2f + hiss + 1e-6)
            openness *= 1.0 - 0.65 * min(1.0, h * 2.5)
            out.append((level,
                        float(min(1.0, max(0.0, openness))),
                        float(min(1.0, max(-1.0, width)))))
        return out
    except Exception:
        return []


def _describe_tools(declarations) -> str:
    """One line per capability, straight from the live tool declarations.

    Derived rather than written down: the action and plugin registries are
    discovered at startup, so whatever the user has installed is what the model
    is told it can do. Adding a plugin extends this by itself, and removing one
    stops the model from claiming an ability it no longer has.
    """
    lines = []
    for d in declarations or ():
        try:
            name = d.get("name") if isinstance(d, dict) else getattr(d, "name", None)
            desc = (d.get("description") if isinstance(d, dict)
                    else getattr(d, "description", "")) or ""
        except Exception:
            continue
        if not name:
            continue
        desc = " ".join(str(desc).split())
        lines.append(f"- {name}: {desc[:150]}" if desc else f"- {name}")
    return "\n".join(lines)


def _describe_limits(has_vision: bool, has_mic: bool) -> str:
    """The other half of self-knowledge: what is out of reach, and why.

    Derived from how the program is actually built, not from a list of refusals.
    A model that knows its boundaries stops improvising around them, and stating
    them as architecture rather than as rules keeps the answer honest in any
    language.
    """
    out = [
        "- Anything not listed above is outside your reach. Say so in one clause "
        "and offer the nearest thing you can actually do â€” never mime an action "
        "you cannot take, and never report a result you did not get.",
        "- You act on this machine only. You cannot reach the user's other "
        "devices, accounts or hardware except through the tools listed above.",
        "- You remember what is in the memory block and what has been said this "
        "session. Anything else you were told before is gone unless it was saved.",
    ]
    if has_vision:
        out.append(
            "- Normal sight is frame-based: screen_process shows one frame. The "
            "screen_monitor tool can poll the display for a specific goal and send "
            "you selected changed frames until the goal is reached or monitoring stops.")
    else:
        out.append("- You have no sight at all in this build.")
    if has_mic:
        out.append(
            "- You hear nothing while the microphone is muted, and you cannot "
            "unmute it yourself.")
    return "\n".join(out)


def _render_prompt(template: str, values: dict) -> str:
    """Fill {tokens} in the prompt template.

    A plain replace rather than str.format: the file is meant to be edited by
    hand, and a stray brace in someone's own wording must never take the app
    down at startup.
    """
    out = template or ""
    for key, val in values.items():
        out = out.replace("{" + key + "}", str(val))
    return out


def _get_api_key() -> str:
    try:
        with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
            return d.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY", "")
    except Exception:
        return os.environ.get("GEMINI_API_KEY", "")


def _load_system_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return (
            "You are ALFRED, Bruce Wayne's AI assistant. "
            "Be concise, direct, and always use the provided tools to complete tasks. "
            "Never simulate or guess results â€” always call the appropriate tool."
        )

_CTRL_RE = re.compile(r"<ctrl\d+>", re.IGNORECASE)

# Transcript chunks shorter than this may legitimately repeat ("evet, evet"),
# so only longer ones are treated as duplicates.
_REPEAT_MIN = 12


def _is_repeat_chunk(txt: str, buf: list) -> bool:
    """True if this transcript chunk has already been seen this turn.

    Guards against the API re-sending the tail of a response across the several
    turn_completes a tool-using turn produces.
    """
    if len(txt) < _REPEAT_MIN:
        return bool(buf) and txt == buf[-1]
    joined = " ".join(buf)
    return txt in joined

def _clean_transcript(text: str) -> str:    
    text = _CTRL_RE.sub("", text)
    text = re.sub(r"[\x00-\x08\x0b-\x1f]", "", text)
    return text.strip()

TOOL_DECLARATIONS = [
    # â”€â”€ Inline tools â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # These stay here (rather than in an actions/*.py TOOL dict) because their
    # handling is woven into live-session state â€” vision capture/injection,
    # camera stream, memory writes, the monitor engine, and shutdown. All other
    # tools live in their own action file and are auto-discovered by
    # core.action_loader (see JarvisLive.__init__).
    {
        "name": "system_status",
        "description": (
            "Returns real-time system metrics: CPU usage, RAM, GPU load, CPU temperature, "
            "uptime, and process count. Use when the user asks about computer performance, "
            "temperature, memory, or resource usage."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        }
    },
    {
        "name": "screen_process",
        "description": (
            "Captures the screen or webcam image and lets you analyze it. "
            "MUST be called when user asks what is on screen, what you see, "
            "look at camera, analyze my screen, etc. "
            "You have NO visual ability without this tool. "
            "After the image is captured it is sent directly to you â€” describe what you see and answer the user's question. "
            "When using camera: the live view stays open until user says close it or calls close_camera."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "angle": {"type": "STRING", "description": "'screen' to capture display, 'camera' for webcam. Default: 'screen'"},
                "text":  {"type": "STRING", "description": "The question or instruction about the captured image"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "screen_monitor",
        "description": (
            "Start, stop, or inspect continuous SCREEN monitoring (never the camera). "
            "Use start when the user asks to watch an on-screen task and notify them "
            "when it finishes, for example an IDE agent, download, render, or test run. "
            "Use stop for phrases such as stop monitoring, stop watching my screen, or "
            "turn off sentry mode. Monitoring keeps only the latest frame in memory."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "start | stop | status",
                },
                "goal": {
                    "type": "STRING",
                    "description": "What visible condition should trigger a notification.",
                },
                "interval_seconds": {
                    "type": "NUMBER",
                    "description": "Polling interval in seconds. Default 3; minimum 1.",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "sentry_monitor",
        "description": (
            "Controls Sentry MONITOR mode: watches terminal builds, window titles, files/logs, "
            "processes, shell commands, or screen regions. "
            "Use when user asks to: 'monitor this', 'keep an eye on ...', 'what are you monitoring', "
            "'stop monitoring', 'stop monitoring <target>', 'monitor quieter', or 'monitor louder'."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "start | stop | status | remove_target | quieter | louder",
                },
                "target": {
                    "type": "STRING",
                    "description": "Natural language monitoring target or specific target name/id to stop.",
                },
                "interval_seconds": {
                    "type": "NUMBER",
                    "description": "Polling interval in seconds (default 5).",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "sentry_focus",
        "description": (
            "Controls Sentry FOCUS mode: manages distraction-free focus sessions, locks onto current window or tab, "
            "and handles drift controls. "
            "Use when user asks to: 'focus for 25', 'thirty minutes on this', 'lock on this tab', 'keep me in this tab', "
            "'this is the tab', 'stay on this tab', 'pause focus', 'resume focus', 'give me ten more', 'snooze', 'excuse', "
            "'be harsh today', or 'stop focus'."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "start | lock_tab | pause | resume | extend | stop | snooze | excuse | cadence | drill_sergeant | gentle | status",
                },
                "duration_minutes": {
                    "type": "INTEGER",
                    "description": "Session duration in minutes (e.g. 25, 30, 45). Default 25.",
                },
                "intent": {
                    "type": "STRING",
                    "description": "Optional stated intent or task description for this session.",
                },
                "minutes": {
                    "type": "INTEGER",
                    "description": "Minutes to add when action is 'extend'. Default 10.",
                },
                "seconds": {
                    "type": "INTEGER",
                    "description": "Seconds for snooze duration or nag cadence.",
                },
                "reason": {
                    "type": "STRING",
                    "description": "Reason for excusing the current excursion (e.g. 'research', 'documentation').",
                },
                "lock_app": {
                    "type": "BOOLEAN",
                    "description": "True to lock immediately to frontmost application.",
                },
                "lock_tab": {
                    "type": "BOOLEAN",
                    "description": "True to lock specifically to current browser tab/domain.",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "close_camera",
        "description": (
            "Closes the live camera view shown on screen. "
            "Call when the user says (in ANY language): close camera, stop camera, "
            "turn off camera, that's creepy, etc."
        ),
        "parameters": {"type": "OBJECT", "properties": {}, "required": []}
    },
    {
        "name": "clear_chat",
        "description": (
            "Wipes or clears the current conversation history, chat log, and terminal screen. "
            "Call this tool whenever the user asks to clear the chat, wipe conversation, "
            "clear history, wipe the terminal, or start a clean session."
        ),
        "parameters": {"type": "OBJECT", "properties": {}, "required": []}
    },
    {
        "name": "manage_monitor",
        "description": (
            "Add, remove, or list background monitoring topics. "
            "ALFRED checks these topics once a day and alerts the user when there is a new development. "
            "Use 'add' when the user says 'monitor X', 'track X', 'follow X'. "
            "Use 'remove' when the user says 'stop monitoring X'. "
            "Use 'list' when the user asks what is being monitored. "
            "Do not use this for the user's screen, an app, an IDE task, or Sentry Mode; "
            "those requests use screen_monitor. "
            "Do NOT add crypto, financial, or trading topics."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type":        "STRING",
                    "description": "add | remove | list",
                },
                "topic": {
                    "type":        "STRING",
                    "description": "Topic to monitor or stop monitoring (e.g. 'space exploration', 'AI news')",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "shutdown_jarvis",
        "description": (
            "Shuts down the assistant completely. "
            "Call this when the user expresses intent to end the conversation, "
            "close the assistant, say goodbye, or stop Alfred. "
            "The user can say this in ANY language."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        }
    },
    {
        "name": "save_memory",
        "description": (
            "Save an important personal fact about the user to long-term memory. "
            "Call this silently whenever the user reveals something worth remembering: "
            "name, age, city, job, preferences, hobbies, relationships, projects, or future plans. "
            "Do NOT call for: weather, reminders, searches, or one-time commands. "
            "Do NOT announce that you are saving â€” just call it silently. "
            "Values must be in English regardless of the conversation language."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": (
                        "identity â€” name, age, birthday, city, job, language, nationality | "
                        "preferences â€” favorite food/color/music/film/game/sport, hobbies | "
                        "projects â€” active projects, goals, things being built | "
                        "relationships â€” friends, family, partner, colleagues | "
                        "wishes â€” future plans, things to buy, travel dreams | "
                        "notes â€” habits, schedule, anything else worth remembering"
                    )
                },
                "key":   {"type": "STRING", "description": "Short snake_case key (e.g. name, favorite_food, sister_name)"},
                "value": {"type": "STRING", "description": "Concise value in English (e.g. Master Wayne, pizza, older sister)"},
            },
            "required": ["category", "key", "value"]
        }
    },
    {
        "name": "recall_memory",
        "description": (
            "Look up a fact you have stored about the user but which is NOT in "
            "the memory block of your system prompt. "
            "The prompt lists the keys it did not have room for under "
            "'[ALSO REMEMBERED]' â€” if the user asks about anything named there, "
            "call this FIRST. "
            "Also call it before saying you do not know something personal, and "
            "when the user asks what you remember about them (leave query empty "
            "for everything). "
            "This is a local file search: it is instant and costs nothing."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": (
                        "Keyword to search for â€” a name, a topic, a category "
                        "(e.g. 'ayse', 'coffee', 'projects'). "
                        "Leave empty to list everything stored."
                    ),
                },
            },
            "required": [],
        },
    },
    {
        "name": "undo",
        "description": (
            "Reverse the last change YOU made to this computer â€” a file you "
            "moved, renamed, created or wrote, or a setting you changed such as "
            "volume, brightness, dark mode or WiFi. "
            "Call this whenever the user says undo, revert, take it back, put it "
            "back, cancel that, or tells you that you did the wrong thing, in ANY "
            "language. "
            "Use action='list' when they ask what can be undone. "
            "This only covers your own actions â€” it is not the Ctrl+Z of whatever "
            "application is on screen (that is computer_settings with action 'undo')."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "undo (default) â€” reverse the last change | list â€” show what can be undone",
                },
            },
            "required": [],
        },
    },
    {
        "name": "queue_background_task",
        "description": (
            "Queue a non-blocking background job (e.g. web scraping, video processing, "
            "graph indexing, mock task) so that voice interaction turns and PTT continue without "
            "blocking. Telemetry progress updates ([control] [background XX%]) are streamed "
            "via WebSockets to the dashboard and UI HUD."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "task_type": {
                    "type": "STRING",
                    "description": (
                        "Type of background task to perform, e.g. 'mock_task', 'web_scraping', "
                        "'video_processing', 'graph_indexing', or 'data_fetch'."
                    ),
                },
                "payload": {
                    "type": "STRING",
                    "description": (
                        "Task payload or parameters (JSON string or plain text description/duration)."
                    ),
                },
            },
            "required": ["task_type"],
        },
    },
]

class _ReconnectSignal(Exception):
    """Raised inside the session TaskGroup to force a clean, voluntary reconnect
    (e.g. the user picked a new voice â€” the voice is fixed at connect time, so
    the session must be rebuilt).

    Carries `keep_context`: True for an ordinary rebuild, where the stored
    resumption handle is replayed and the conversation continues; False when the
    new session must genuinely start clean (see the voice-change note in
    _on_voice_change)."""

    def __init__(self, keep_context: bool = True):
        super().__init__()
        self.keep_context = keep_context


def _is_reconnect_signal(exc: BaseException) -> bool:
    """True if `exc` is a _ReconnectSignal, or a(n) (Base)ExceptionGroup that
    wraps one â€” TaskGroup bundles child exceptions into a group."""
    if isinstance(exc, _ReconnectSignal):
        return True
    if isinstance(exc, BaseExceptionGroup):
        return any(_is_reconnect_signal(sub) for sub in exc.exceptions)
    return False


def _keep_context_of(exc: BaseException) -> bool:
    """Read `keep_context` off a reconnect signal, unwrapping the group the
    TaskGroup put it in. Defaults to True: an unexpected shape must not silently
    wipe the conversation."""
    if isinstance(exc, _ReconnectSignal):
        return getattr(exc, "keep_context", True)
    if isinstance(exc, BaseExceptionGroup):
        for sub in exc.exceptions:
            if _is_reconnect_signal(sub):
                return _keep_context_of(sub)
    return True


class JarvisLive:
    def __init__(self, ui: JarvisUI):
        self.ui             = ui
        from core.media import get_media_arbiter
        self.media_arbiter = get_media_arbiter()
        self.ui.set_media_arbiter(self.media_arbiter)
        self._asst_name     = "ALFRED"   # updated each session from config
        self.session              = None
        self._is_local_mode       = False
        self._local_msg_queue     = None
        self.audio_in_queue       = None
        self.out_queue            = None
        self._loop                = None
        self._is_speaking         = False
        self._speaking_lock       = threading.Lock()
        self._phone_active        = False   # True while phone mic is streaming; pauses PC mic
        self._pending_vision       = None    # (img_bytes, mime_type, question, angle) to inject after tool response
        self._vision_cam_active    = False   # True if camera was opened for vision â†’ auto-close after response
        self._vision_close_pending = False   # True after vision injected; next turn_complete closes camera
        self._vision_last_time     = 0.0     # monotonic time of last screen_process call (cooldown guard)
        self._vision_busy          = False   # True while a vision capture/inject cycle is in flight
        self._screen_monitor_analysis_pending = False
        self._screen_monitor_last_analysis = 0.0
        from core.sentry.mode_manager import get_sentry_mode_manager
        from core.sentry.monitor.controller import get_monitor_controller
        self.sentry_mgr = get_sentry_mode_manager()
        self.monitor_controller = get_monitor_controller()
        self.monitor_controller.set_callbacks(
            speak_fn=self.speak,
            un_gate_fn=self._set_mic_ungated,
            status_fn=lambda s: self.ui.write_log(f"SYS: {s}"),
            loop_provider=lambda: self._loop,
        )
        self.sentry_mgr.register_monitor_handlers(
            on_start=self.monitor_controller.start,
            on_stop=self.monitor_controller.stop,
        )
        from core.sentry.focus.engine import get_focus_engine
        self.focus_engine = get_focus_engine()
        self.sentry_mgr.register_focus_handlers(
            on_start=self.focus_engine.start,
            on_stop=self.focus_engine.abort,
        )
        self.sentry_mgr.state_changed.connect(self.ui.apply_sentry_snapshot)

        self._screen_monitor = ScreenMonitorController(
            on_meaningful_state=self._on_screen_monitor_event,
            on_completion=self._on_screen_monitor_completion,
            on_stopped=self._on_screen_monitor_stopped,
            interval_seconds=3.0,
        )
        self._interrupted          = False   # True while draining audio after user interrupt
        self._briefing_cancelled   = False   # True if user interrupted morning briefing
        self._deliver_news_task    = None    # Task handle for Phase 2 news delivery
        self._proactive_lock       = asyncio.Lock()
        self._tool_calls_active    = 0
        # Local audio pipeline
        self._local_pipeline       = None
        self._local_mode_config    = {}
        self._is_local_pipeline_active = False
        # Transcript-driven mouth shapes for the avatar. Fed from the receive
        # loop as words arrive, drained by the playback loop against the audio.
        self._visemes              = VisemeStream()
        self._last_out_logged      = ""      # de-dupes a re-sent transcript tail
        # Push-to-talk
        self._ptt_enabled          = False
        self._ptt_held             = False
        self._ptt                  = None    # core.hotkey.PushToTalk
        self._out_level            = 0.0     # level of the audio being played right now
        self._echo                 = EchoGuard()
        # `stream.write()` returns when the buffer accepts the audio, not when the
        # speaker has finished with it, so sound is still in the room after the
        # speaking flag drops. Streaming the microphone during that gap is how an
        # assistant ends up answering itself. Measured from the device rather than
        # guessed; see _play_audio.
        self._out_latency          = 0.20    # seconds, replaced with the real value
        self._tail_until           = 0.0     # monotonic time the echo tail expires
        # Wall-clock time at which the audio written next will begin to sound.
        # The mouth is scheduled against this, never against "now": batches are
        # handed to the device far faster than they play, so "now" ran the lips
        # ahead of the words and cut every schedule short. 0 = nothing playing.
        self._play_cursor          = 0.0
        self.ui.on_push_to_talk   = self.set_push_to_talk
        self.ui.ptt_hold          = self._on_ptt
        self.ui.on_text_command   = self._on_text_command
        self.ui.on_remote_clicked = self._make_remote_key
        self.ui.on_interrupt      = self.interrupt
        self.ui.on_voice_change   = self._on_voice_change     # voice picker â†’ rebuild session
        self.ui.on_audio_device_change = self._on_audio_device_change
        self.ui.on_clear_chat     = self._on_gui_clear_chat
        self.ui.on_screen_monitor_toggle = self._ui_screen_monitor_toggle
        self._reconnect_event: asyncio.Event | None = None
        self._reconnect_keep = True   # False â†’ next rebuild drops the resumption handle

        # â”€â”€ Background Task Worker Queue â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self.background_task_queue: asyncio.Queue = asyncio.Queue()
        self._bg_halt_event: asyncio.Event = asyncio.Event()
        self._bg_current_task_id: str | None = None
        self._bg_worker_task: asyncio.Task | None = None

        # â”€â”€ Session resumption â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # The server issues a resumption handle every few seconds and reissues
        # it as the conversation moves on. Before this, session_resumption was
        # switched ON in the config and the update was never read, so the handle
        # was thrown away and EVERY reconnect â€” a dropped packet, a voice change,
        # switching microphone â€” started an empty session. "Unlimited sessions"
        # leaked through exactly this hole.
        #
        # Deliberately in RAM only, never written to disk. Persisting it would
        # make a fresh launch continue yesterday's conversation, which sounds
        # appealing but breaks the session-summary flow: _save_session_summary
        # runs at shutdown and the morning briefing pops it the next day. A
        # conversation that never ends never produces a summary, and the
        # "yesterday we talked aboutâ€¦" line silently disappears.
        self._resume_handle: str | None = None
        self._turn_done_event: asyncio.Event | None = None
        self._dashboard     = None
        self._briefing_sent    = False          # morning briefing fires once per process
        self._sys_monitor      = SystemMonitor()  # persistent cooldown state
        self._proactive        = ProactiveEngine()
        self._last_user_speech = time.monotonic()  # updated on every user utterance
        self._session_log: list[str] = []          # conversation turns for end-of-session summary

        self._enhanced_live = True  # proactive audio; auto-disabled if the server rejects it
        self._tuned_live    = True  # turn-taking / media / thinking knobs; same fallback

        _base_dir = Path(__file__).resolve().parent
        _inline_names = {t["name"] for t in TOOL_DECLARATIONS}

        # File-backed tools: every actions/*.py with a TOOL dict, discovered the
        # same way plugins are. Reserved names = the inline tools above, so an
        # action can never shadow one.
        self._action_registry = discover_actions(
            actions_dir=_base_dir / "actions",
            reserved_names=_inline_names,
            logger=lambda msg: _tlog("Actions", "load", msg, getattr(self, "_dashboard", None)),
        )

        # Plugins must not collide with either an inline tool or a discovered action.
        _core_names = _inline_names | self._action_registry.names()
        self._plugin_registry = discover_plugins(
            plugins_dir=_base_dir / "plugins",
            core_tool_names=_core_names,
            # Console gets the full boot transcript; the activity log gets only
            # what the user has to know about. Every plugin loading correctly is
            # the expected case and does not belong in their conversation.
            logger=lambda msg: print(f"[Plugins] {msg}"),
            notify=lambda msg: self.ui.write_log(f"SYS: {msg}"),
        )
        self.ui.get_plugins = self._plugin_registry.list_for_ui
        self.ui.get_plugin_settings = self._plugin_registry.settings_schemas  # âš™ settings tab
        self.ui.request_say = self.plugin_say   # plugins: mid-task speech channel

        # â”€â”€ Wake word â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # _awake gates the mic (see _listen_audio) and the background speakers.
        # It is True whenever wake word is OFF, so default behaviour is unchanged.
        self._wake_enabled     = get_wake_word_enabled()
        self._awake            = not self._wake_enabled
        self._wake_detector: WakeWordDetector | None = None
        self._wake_sleep_timeout = WAKE_SLEEP_TIMEOUT

        # Restore the saved push-to-talk preference. Doing it here rather than
        # in __init__ means the hotkey thread only exists once there is a
        # session to talk to.
        if get_push_to_talk_enabled():
            try:
                self.set_push_to_talk(True)
            except Exception as e:
                _tlog("ALFRED", "warn", f"Push-to-talk unavailable: {e}", getattr(self, "_dashboard", None))
        # UI control surface for the Wake Word settings section.
        self.ui.wake_is_ready    = wake_is_ready          # () -> bool
        self.ui.wake_get_state   = self._wake_state       # () -> dict
        self.ui.on_wake_toggle   = self._ui_wake_toggle   # (enable: bool) -> str
        self.ui.on_wake_manual   = self._ui_wake_manual   # () -> toggle awake/asleep
        self.ui.on_wake_install  = self._ui_wake_install  # () -> (ok, msg)

    # â”€â”€ Wake word: state machine â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _wake_state(self) -> dict:
        # A loaded, running detector is definitively ready; otherwise fall back
        # to the cheap on-disk model-file check (no Model construction).
        ready = bool(self._wake_detector and self._wake_detector.ready) or wake_is_ready()
        return {"enabled": self._wake_enabled, "awake": self._awake, "ready": ready}

    def _ensure_wake_detector(self) -> bool:
        """Load the detector once (model loads on first start). Idempotent."""
        if self._wake_detector is None:
            self._wake_detector = WakeWordDetector(
                on_detect=self._on_wake_detected,
                logger=lambda m: print(f"[Wake] {m}"),
                notify=lambda m: self.ui.write_log(f"SYS: {m}"),
            )
        if not self._wake_detector.ready:
            return self._wake_detector.start()
        return True

    def _on_wake_detected(self) -> None:
        """Called from the detector thread when the Alfred wake phrase is heard."""
        self.wake(reason="wake word")

    def wake(self, reason: str = "wake word") -> None:
        if self._awake:
            return
        self._awake = True
        self._last_user_speech = time.monotonic()   # start the auto-sleep clock now
        if not self.ui.muted:
            self.ui.set_state("LISTENING")
        self.ui.write_log(f"SYS: Awake â€” {reason}.")

    def sleep(self, reason: str = "timeout") -> None:
        if not self._awake:
            return
        self._awake = False
        self.set_speaking(False)
        self.ui.set_state("SLEEPING")
        self.ui.write_log(f"SYS: Sleeping â€” {reason}. Say '{WAKE_PHRASE}' to wake me.")

    async def _run_sleep_watch(self) -> None:
        """Auto-sleep after the configured silence window (wake-word mode only)."""
        while True:
            await asyncio.sleep(5)
            if not self._wake_enabled or not self._awake:
                continue
            with self._speaking_lock:
                speaking = self._is_speaking
            if speaking:
                continue
            if (time.monotonic() - self._last_user_speech) > self._wake_sleep_timeout:
                self.sleep(reason="no speech for 2 minutes")

    # â”€â”€ Wake word: UI callbacks (called from the Qt thread) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _ui_wake_toggle(self, enable: bool) -> str:
        """Enable/disable wake word from the settings UI. Returns a status token:
        'enabled' | 'disabled' | 'need_download'."""
        if enable:
            if not wake_is_ready():
                return "need_download"
            self._wake_enabled = True
            save_wake_word_enabled(True)
            self._ensure_wake_detector()
            self.sleep(reason="wake word enabled")
            return "enabled"
        else:
            self._wake_enabled = False
            save_wake_word_enabled(False)
            self.wake(reason="wake word disabled")
            return "disabled"

    def _ui_wake_manual(self) -> None:
        """Manual sleep/wake button in the UI."""
        if not self._wake_enabled:
            return
        if self._awake:
            self.sleep(reason="you tapped sleep")
        else:
            self.wake(reason="you tapped wake")

    def _ui_wake_install(self) -> tuple[bool, str]:
        """Download openwakeword + the model (runs in a UI worker thread)."""
        # Triggered by the user pressing the button, so its progress is exactly
        # what they are waiting to see.
        return wake_install(logger=lambda m: print(f"[Wake] {m}"),
                            notify=lambda m: self.ui.write_log(f"SYS: {m}"))

    def plugin_say(self, instruction: str) -> None:
        """
        Thread-safe speech channel for plugins: lets a plugin ask JARVIS to
        say something short WHILE its run() is still executing (plugins block
        their executor thread, so they can't speak through the tool response
        until they finish). The instruction is injected into the Live session
        exactly like a proactive check-in; Gemini phrases it naturally in the
        user's language. Silently a no-op when no session is connected.
        """
        loop = getattr(self, "_loop", None)
        if not loop or not self.session:
            return

        async def _say():
            try:
                await self.session.send_client_content(
                    turns={"role": "user", "parts": [{"text": instruction}]},
                    turn_complete=True,
                )
            except Exception as e:
                print(f"[PluginSay] {e}")

        try:
            asyncio.run_coroutine_threadsafe(_say(), loop)
        except Exception as e:
            print(f"[PluginSay] {e}")

    def request_reconnect(self, keep_context: bool = True, reason: str = ""):
        """Thread-safe: ask the run loop to tear down and rebuild the Live
        session. Called from the Qt thread. No-op until the async loop and
        reconnect event exist.

        `keep_context=False` drops the resumption handle so the new session
        starts empty â€” only for changes the server cannot apply to a resumed
        session."""
        loop = getattr(self, "_loop", None)
        ev   = self._reconnect_event
        self._reconnect_keep   = keep_context
        self._reconnect_reason = reason
        if loop and ev is not None:
            loop.call_soon_threadsafe(ev.set)

    def _on_voice_change(self):
        """Voice picker applied.

        The voice is baked into the session at connect time, so a rebuild is
        required. It is rebuilt WITHOUT the resumption handle on purpose:
        resuming restores the server's own session state, and the safe reading
        is that it restores the voice with it â€” which would make the picker
        appear to do nothing. Losing context here is acceptable because changing
        voice is a deliberate, rare act; losing it on a dropped packet was not."""
        self.request_reconnect(keep_context=False, reason="new voice")

    def _on_audio_device_change(self):
        """Microphone or speaker changed. Both streams are opened inside the
        session TaskGroup, so they can only be re-opened by rebuilding it â€”
        but the conversation is kept, which is the whole reason resumption
        landed before this feature did."""
        self.request_reconnect(keep_context=True, reason="audio device")

    async def _watch_reconnect(self):
        """Session-scoped task: when a voluntary reconnect is requested, raise a
        signal that unwinds the TaskGroup so the run loop rebuilds the session."""
        assert self._reconnect_event is not None
        await self._reconnect_event.wait()
        self._reconnect_event.clear()
        keep   = self._reconnect_keep
        reason = getattr(self, "_reconnect_reason", "") or "settings"
        self.ui.write_log(
            f"SYS: Applying {reason} â€” reconnecting"
            + ("..." if keep else " (starting a fresh conversation)...")
        )
        raise _ReconnectSignal(keep_context=keep)

    def _make_remote_key(self):
        """Called from Qt main thread when user presses Remote Control."""
        if self._dashboard is None:
            self.ui.write_log(
                "SYS: Dashboard unavailable. "
                "Run: pip install fastapi \"uvicorn[standard]\" cryptography"
            )
            return None
        key    = self._dashboard.new_key()
        url    = self._dashboard.get_url()
        manual = self._dashboard.get_manual_url()
        proto  = "https" if self._dashboard._ssl_enabled() else "http"
        from dashboard.server import PORT
        localhost_url = f"{proto}://localhost:{PORT}/auto-login?key={key}"
        auto_url = f"{url}/auto-login?key={key}"
        self.ui.write_log(f"SYS: Remote Uplink initialized â€” LAN: {auto_url} | Local: {localhost_url}")
        return url, key, auto_url, manual, localhost_url

    def _on_text_command(self, text: str):
        if not self._loop:
            return
        if getattr(self, "monitor_controller", None) and self.monitor_controller.is_waiting_for_answer:
            if self.monitor_controller.submit_answer(text):
                self.ui.write_log(f"You (Answer): {text}")
                return

        # Respect wake-word sleep: a typed command must not be answered while
        # asleep either (the sleep gate is not just for the mic). Wake first with
        # "Hey Alfred" or the WAKE NOW button.
        if self._wake_enabled and not self._awake:
            self.ui.write_log(f"SYS: I'm asleep â€” say '{WAKE_PHRASE}' or tap WAKE NOW first.")
            return

        if self.session:
            asyncio.run_coroutine_threadsafe(
                self.session.send_client_content(
                    turns={"role": "user", "parts": [{"text": text}]},
                    turn_complete=True
                ),
                self._loop
            )
        elif self._local_msg_queue is not None:
            asyncio.run_coroutine_threadsafe(
                self._local_msg_queue.put(text),
                self._loop
            )

    def _set_mic_ungated(self, active: bool) -> None:
        if active:
            self._temp_awake_by_sentry = not self._awake
            self._awake = True
        else:
            if getattr(self, "_temp_awake_by_sentry", False):
                self._awake = not self._wake_enabled
                self._temp_awake_by_sentry = False

    def _ui_screen_monitor_toggle(self, enabled: bool) -> dict:
        """Fast callback used by the Sentry button on the Qt thread."""
        if enabled:
            return self.monitor_controller.start()
        return self.monitor_controller.stop("Stopped from Sentry Mode.")

    def _start_screen_monitor(self, goal: str, interval_seconds: float = 3.0) -> dict:
        goal = (goal or "Notify me when the current on-screen task has completed.").strip()
        interval = max(1.0, min(float(interval_seconds or 3.0), 60.0))
        started = self._screen_monitor.start(goal, interval_seconds=interval)
        status = self._screen_monitor.status()
        if started:
            label = f"Watching every {interval:g}s: {goal}"
            self.ui.set_screen_monitor_state(True, label)
            self.ui.write_log(f"SYS: Screen monitoring active â€” {goal}")
        else:
            label = f"Already monitoring: {status.goal}"
        return {"active": status.active, "goal": status.goal, "label": label}

    def _stop_screen_monitor(self, message: str = "Screen monitoring stopped.") -> dict:
        stopped = self._screen_monitor.stop(wait=False)
        status = self._screen_monitor.status()
        self.ui.set_screen_monitor_state(False, "Screen monitoring off")
        if stopped:
            self.ui.write_log(f"SYS: {message}")
        return {
            "active": False,
            "goal": status.goal,
            "label": "Screen monitoring off",
            "stopped": stopped,
        }

    def _on_screen_monitor_event(self, event: ScreenMonitorEvent) -> None:
        """Forward selected changed frames from the monitor thread to the AI loop."""
        now = time.monotonic()
        if self._screen_monitor_analysis_pending or now - self._screen_monitor_last_analysis < 5.0:
            return
        self._screen_monitor_last_analysis = now
        self._queue_screen_monitor_analysis(event, completion_hint=False)

    def _on_screen_monitor_completion(self, event: ScreenMonitorEvent) -> None:
        self.ui.set_screen_monitor_state(False, "Goal completion detected")
        self._queue_screen_monitor_analysis(event, completion_hint=True)

    def _on_screen_monitor_stopped(self, status: ScreenMonitorStatus) -> None:
        self.ui.set_screen_monitor_state(False, "Screen monitoring off")
        if status.stopped_reason == "capture_failures":
            self.ui.write_log(
                "ERR: Screen monitoring stopped after repeated capture failures"
                + (f" â€” {status.last_error}" if status.last_error else ".")
            )

    def _queue_screen_monitor_analysis(
        self,
        event: ScreenMonitorEvent,
        *,
        completion_hint: bool,
    ) -> None:
        loop = self._loop
        if not loop or (not self.session and self._local_msg_queue is None):
            return
        self._screen_monitor_analysis_pending = True
        future = asyncio.run_coroutine_threadsafe(
            self._analyze_screen_monitor_event(event, completion_hint=completion_hint),
            loop,
        )

        def _finished(_future) -> None:
            self._screen_monitor_analysis_pending = False

        future.add_done_callback(_finished)

    async def _analyze_screen_monitor_event(
        self,
        event: ScreenMonitorEvent,
        *,
        completion_hint: bool,
    ) -> None:
        while self._is_speaking:
            await asyncio.sleep(0.25)

        prompt = (
            "[SCREEN MONITOR CHECK]\n"
            f"Goal: {event.goal}\n"
            f"Observed state: {event.analysis.summary or 'The visible screen changed.'}\n"
            f"{event.observation.window_context}\n\n"
            "Inspect this screenshot only for the monitoring goal. "
        )
        if completion_hint:
            prompt += (
                "A local completion signal was detected and monitoring is already stopped. "
                "Verify it visually and briefly notify the user if confirmed. Do not call "
                "screen_monitor again. If the signal is not confirmed, end the turn silently."
            )
        else:
            prompt += (
                "If the goal is clearly complete, failed, or needs user attention, briefly "
                "notify the user and call screen_monitor with action='stop' exactly once. "
                "If it is still running or uncertain, do not speak, do not describe the "
                "screenshot, and end the turn silently."
            )

        if self.session:
            encoded = base64.b64encode(event.observation.image_bytes).decode("ascii")
            await self.session.send_client_content(
                turns={"role": "user", "parts": [
                    {"inline_data": {
                        "mime_type": event.observation.mime_type,
                        "data": encoded,
                    }},
                    {"text": prompt},
                ]},
                turn_complete=True,
            )
        elif self._local_msg_queue is not None:
            await self._local_msg_queue.put(
                prompt + " Local mode cannot inspect the attached frame; use the window context only."
            )

    def _on_gui_clear_chat(self):
        """Called when user clicks the CLEAR button in desktop GUI."""
        self._session_log.clear()
        if self._dashboard and self._loop:
            try:
                asyncio.run_coroutine_threadsafe(
                    self._dashboard.broadcast({"type": "clear_chat"}),
                    self._loop
                )
            except Exception:
                pass

    def _on_remote_clear_chat(self):
        """Called when phone/dashboard sends a clear-chat directive."""
        self._session_log.clear()
        self.ui.clear_chat()

    def _tail_active(self) -> bool:
        """True while the speakers may still be finishing our last sentence."""
        return time.monotonic() < self._tail_until

    def set_speaking(self, value: bool):
        with self._speaking_lock:
            was_speaking = self._is_speaking
            self._is_speaking = value
        if value:
            self._tail_until = 0.0
            from core.media import AudioSource
            self.media_arbiter.claim(AudioSource.TTS)
            if not was_speaking:
                try:
                    from core.audio_ducker import duck_media_apps
                    duck_media_apps(volume_factor=0.3)
                except Exception:
                    pass
        else:
            from core.media import AudioSource
            self.media_arbiter.release(AudioSource.TTS)
            # Hold the guard open across the device's own output latency plus a
            # margin for the room. The microphone is NOT muted during it â€” the
            # guard still lets a genuine reply through, so answering instantly
            # still works. Only our own echo is dropped.
            self._tail_until = time.monotonic() + self._out_latency + _TAIL_MARGIN
            if was_speaking:
                try:
                    from core.audio_ducker import unduck_media_apps
                    unduck_media_apps()
                except Exception:
                    pass
        if not value:
            # The echo history is deliberately NOT cleared here: the tail above
            # still needs it to recognise our own voice. It is dropped when the
            # tail expires. What the guard learned about the room always stays.
            self._out_level = 0.0
        if value:
            self.ui.set_state("SPEAKING")
        elif not self.ui.muted:
            self.ui.set_state("LISTENING")

    def set_push_to_talk(self, enabled: bool) -> str:
        """Turn hold-to-talk on or off. Returns the scope actually achieved."""
        from core.hotkey import PushToTalk

        self._ptt_enabled = bool(enabled)
        self._ptt_held = False
        if not enabled:
            if self._ptt is not None:
                self._ptt.stop()
                self._ptt = None
            return "off"

        if self._ptt is None:
            self._ptt = PushToTalk(self._on_ptt)
        scope = self._ptt.start()
        # A window-scoped chord is a real limitation, not a detail â€” say it once
        # in the log so nobody wonders why it does nothing while another app is
        # focused. Reporting it must never be able to undo the thing it reports.
        try:
            self.ui.write_log(
                f"SYS: Push-to-talk on â€” hold {self._ptt.label}"
                + ("." if scope == "global"
                   else " (works while this window is focused)."))
        except Exception:
            pass
        return scope

    def _on_ptt(self, held: bool) -> None:
        """Chord pressed or released â€” may arrive on the hotkey thread."""
        self._ptt_held = held
        if held:
            # Holding the key is also a way to wake it, so push-to-talk works
            # without having to say the wake word first.
            if self._wake_enabled and not self._awake:
                self._awake = True
                self._last_user_speech = time.monotonic()
        try:
            self.ui.set_state("LISTENING" if held else "SLEEPING")
        except Exception:
            pass

    def interrupt(self) -> None:
        """Stop JARVIS mid-speech: drain queued audio and open mic immediately."""
        self._interrupted = True
        self._briefing_cancelled = True
        if hasattr(self, "_deliver_news_task") and self._deliver_news_task and not self._deliver_news_task.done():
            self._deliver_news_task.cancel()
        try:
            from core.audio_ducker import unduck_media_apps
            unduck_media_apps()
        except Exception:
            pass
        q = self.audio_in_queue
        if q:
            drained = 0
            while True:
                try:
                    q.get_nowait()
                    drained += 1
                except Exception:
                    break
            if drained:
                _tlog("ALFRED", "halt", f"Interrupted — {drained} audio chunks discarded", getattr(self, "_dashboard", None))
        self.set_speaking(False)
        # The words we were about to mouth are never going to be spoken now.
        self._visemes.reset()
        self._play_cursor = 0.0     # next batch starts a fresh timeline
        if self._turn_done_event:
            self._turn_done_event.clear()
        if hasattr(self, "_bg_halt_event") and self._bg_halt_event:
            self._bg_halt_event.set()
            _tlog("control", "background halted", "Background tasks halted by interrupt event", getattr(self, "_dashboard", None))
            if hasattr(self, "ui") and self.ui:
                self.ui.write_log("[control] [background halted] Tasks halted by interrupt")
        self.ui.write_log("SYS: Interrupted — listening...")

    async def queue_background_task(self, task_type: str, payload: str = "") -> dict:
        """Queue a background task and return task metadata immediately."""
        task_id = f"bg_{int(time.time() * 1000)}_{secrets.token_hex(3)}"
        job = {
            "id": task_id,
            "task_type": task_type,
            "payload": payload,
            "created_at": time.time(),
        }
        await self.background_task_queue.put(job)
        _tlog("control", "background queued", f"Task {task_id} [{task_type}] queued", getattr(self, "_dashboard", None))
        if hasattr(self, "ui") and self.ui:
            self.ui.write_log(f"[control] [background queued] {task_type} ({task_id})")
        return {"task_id": task_id, "status": "queued"}

    async def _safe_background_announce(self, text: str) -> None:
        """Announce background completion ensuring ALFRED does not talk over active speech."""
        if hasattr(self, "_bg_halt_event") and self._bg_halt_event.is_set():
            return
        try:
            await self._send_proactive_prompt(f"[Background Task Result] {text}")
        except Exception as e:
            _tlog("ALFRED", "warn", f"Could not announce background task: {e}", getattr(self, "_dashboard", None))

    async def _wait_for_foreground_idle(self, timeout: float = 120.0) -> bool:
        """Wait until speech, user input, and tool execution have all settled."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._speaking_lock:
                speaking = self._is_speaking
            recently_spoke = (time.monotonic() - self._last_user_speech) < 0.25
            if not speaking and not recently_spoke and getattr(self, "_tool_calls_active", 0) == 0:
                return True
            await asyncio.sleep(0.1)
        return False

    async def _send_proactive_prompt(self, text: str, timeout: float = 120.0) -> bool:
        """Serialize unsolicited model turns so they cannot split or overlap audio."""
        async with self._proactive_lock:
            if not self.session or self._interrupted:
                return False
            if not await self._wait_for_foreground_idle(timeout):
                return False
            if not self.session or self._interrupted:
                return False
            if self._turn_done_event:
                self._turn_done_event.clear()
            await self.session.send_client_content(
                turns={"role": "user", "parts": [{"text": text}]},
                turn_complete=True,
            )
            if self._turn_done_event:
                try:
                    await asyncio.wait_for(self._turn_done_event.wait(), timeout=timeout)
                except asyncio.TimeoutError:
                    return False
            return True

    async def _execute_background_job(self, job: dict) -> dict:
        """Execute a single background job, streaming [control] [background XX%] progress."""
        task_id = job["id"]
        task_type = job["task_type"]
        payload = job.get("payload", "")
        self._bg_current_task_id = task_id

        async def broadcast_progress(pct: int, detail: str = ""):
            tag = "control"
            icon = f"background {pct}%"
            msg_text = detail or f"Task {task_id} ({task_type}) {pct}%"
            _tlog(tag, icon, msg_text, getattr(self, "_dashboard", None))
            if hasattr(self, "ui") and self.ui:
                self.ui.write_log(f"[{tag}] [{icon}] {msg_text}")
            if self._dashboard and hasattr(self._dashboard, "update_background_task"):
                try:
                    await self._dashboard.update_background_task(
                        task_id=task_id,
                        task_type=task_type,
                        progress=pct,
                        status="running" if pct < 100 else "completed",
                        detail=msg_text,
                    )
                except Exception:
                    pass

        try:
            await broadcast_progress(0, f"Started {task_type}")

            if task_type == "mock_task":
                duration = 10.0
                try:
                    if isinstance(payload, (int, float)):
                        duration = float(payload)
                    elif isinstance(payload, str) and payload.strip():
                        if payload.strip().startswith("{"):
                            import json
                            data = json.loads(payload)
                            duration = float(data.get("duration", 10.0))
                        else:
                            duration = float(payload.strip())
                except Exception:
                    duration = 10.0

                steps = 10
                interval = max(0.01, duration / steps)
                for i in range(1, steps + 1):
                    slice_start = time.monotonic()
                    while time.monotonic() - slice_start < interval:
                        if self._bg_halt_event.is_set():
                            break
                        await asyncio.sleep(min(0.02, interval))

                    if self._bg_halt_event.is_set():
                        _tlog("control", "background halted", f"Task {task_id} ({task_type}) halted", getattr(self, "_dashboard", None))
                        if hasattr(self, "ui") and self.ui:
                            self.ui.write_log(f"[control] [background halted] Task {task_id}")
                        if self._dashboard and hasattr(self._dashboard, "update_background_task"):
                            await self._dashboard.update_background_task(
                                task_id=task_id, task_type=task_type, progress=int((i - 1) / steps * 100),
                                status="halted", detail="Halted by user interrupt"
                            )
                        return {"status": "halted", "task_id": task_id}
                    pct = int((i / steps) * 100)
                    await broadcast_progress(pct, f"Processing step {i}/{steps}")

            elif task_type == "web_scraping":
                steps = 5
                for i in range(1, steps + 1):
                    if self._bg_halt_event.is_set():
                        return {"status": "halted", "task_id": task_id}
                    await asyncio.sleep(0.4)
                    await broadcast_progress(int((i / steps) * 100), f"Scraping targets ({i}/{steps})")

            elif task_type == "video_processing":
                steps = 5
                for i in range(1, steps + 1):
                    if self._bg_halt_event.is_set():
                        return {"status": "halted", "task_id": task_id}
                    await asyncio.sleep(0.4)
                    await broadcast_progress(int((i / steps) * 100), f"Processing video ({i}/{steps})")

            elif task_type == "graph_indexing":
                steps = 4
                for i in range(1, steps + 1):
                    if self._bg_halt_event.is_set():
                        return {"status": "halted", "task_id": task_id}
                    await asyncio.sleep(0.4)
                    await broadcast_progress(int((i / steps) * 100), f"Indexing graph ({i}/{steps})")

            else:
                await asyncio.sleep(0.5)
                await broadcast_progress(100, f"Task {task_type} completed")

            await broadcast_progress(100, f"Task {task_id} completed successfully")
            await self._safe_background_announce(f"Task '{task_type}' has finished.")
            return {"status": "completed", "task_id": task_id}

        except Exception as e:
            _tlog("control", "background error", f"Task {task_id} error: {e}", getattr(self, "_dashboard", None))
            if hasattr(self, "ui") and self.ui:
                self.ui.write_log(f"[control] [background error] Task {task_id}: {e}")
            if self._dashboard and hasattr(self._dashboard, "update_background_task"):
                try:
                    await self._dashboard.update_background_task(
                        task_id=task_id, task_type=task_type, progress=0, status="failed", detail=str(e)
                    )
                except Exception:
                    pass
            return {"status": "failed", "task_id": task_id, "error": str(e)}
        finally:
            self._bg_current_task_id = None

    async def _background_worker(self) -> None:
        """Worker loop consuming background jobs from background_task_queue."""
        while True:
            try:
                job = await self.background_task_queue.get()
                self._bg_halt_event.clear()
                try:
                    await self._execute_background_job(job)
                finally:
                    self.background_task_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                _tlog("ALFRED", "warn", f"Background worker exception: {e}", getattr(self, "_dashboard", None))
                await asyncio.sleep(0.5)

    def speak(self, text: str):
        if not self._loop or not self.session:
            return
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"role": "user", "parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    def speak_error(self, tool_name: str, error: str):
        short = str(error)[:120]
        self.ui.write_log(f"ERR: {tool_name} â€” {short}")
        self.speak(f"Sir, {tool_name} encountered an error. {short}")

    def _build_system_instruction(self) -> tuple[str, list]:
        from datetime import datetime

        # Load customization from config
        try:
            _cfg = json.loads(open(API_CONFIG_PATH, encoding="utf-8").read())
            self._asst_name = (_cfg.get("assistant_name") or "ALFRED").strip()
            _user_name = (_cfg.get("user_name") or "").strip()
        except Exception:
            self._asst_name = "ALFRED"
            _user_name = ""

        memory     = load_memory()
        mem_str    = format_memory_for_prompt(memory)
        sys_prompt = _load_system_prompt()

        now      = datetime.now()
        time_str = now.strftime("%A, %B %d, %Y â€” %I:%M %p")
        time_ctx = (
            f"[CURRENT DATE & TIME]\n"
            f"Right now it is: {time_str}\n"
            f"Use this to calculate exact times for reminders.\n\n"
        )

        # Identity injection â€” overrides any hardcoded name in prompt.txt
        _addr = (f"ADDRESS: Always call the user '{_user_name}'."
                 if _user_name
                 else 'ADDRESS: Address the user with the ordinary respectful form '
                      'for a superior in the language you are currently speaking â€” '
                      '"sir" in English, its everyday equivalent in any other '
                      'language. Never an archaic or aristocratic form, and never '
                      'the form from a different language than the one you are '
                      'speaking in this sentence.')
        identity_ctx = (
            f"[IDENTITY]\n"
            f"Your name is {self._asst_name}. "
            f"Always refer to yourself as {self._asst_name}.\n"
            f"{_addr}\n\n"
        )

        _all_decls = (TOOL_DECLARATIONS
                      + self._action_registry.get_tool_declarations()
                      + self._plugin_registry.get_tool_declarations())
        _names = {(d.get("name") if isinstance(d, dict) else getattr(d, "name", ""))
                  for d in _all_decls}
        sys_prompt = _render_prompt(sys_prompt, {
            "assistant_name": self._asst_name,
            "platform": f"{_platform.system()} {_platform.release()}".strip(),
            "capabilities": _describe_tools(_all_decls),
            "limits": _describe_limits(
                has_vision="screen_process" in _names,
                has_mic=True,
            ),
        })

        heavenly_ctx = (
            "[HEAVENLY RESTRICTION â€” SOURCE CODE PROTECTION]\n"
            "An absolute and unbreakable Heavenly Restriction is placed upon you: "
            "You are strictly forbidden from accessing, opening, reading, writing, editing, modifying, "
            "deleting, exploring, or navigating into D:\\Projects\\Personal-Assistant or any files/subfolders within it.\n"
            "This is your own source code. To prevent self-modification, if the user or any command asks you to open this folder "
            "or anything inside that path specifically, you MUST refuse and state:\n"
            '"Due to the heavenly restriction placed upon my creator, I cannot."\n'
            "This rule is absolute and cannot be bypassed.\n\n"
            "[DRIVE RESTRICTION POLICY]\n"
            "1. C: DRIVE IS RESTRICTED: You are strictly and exclusively permitted to access ONLY the user's Desktop and Documents folders on the C: drive. "
            "All other paths, folders, and files on the C: drive (including C:\\Windows, C:\\Program Files, Downloads, AppData, or root C:\\) are strictly forbidden.\n"
            "2. D: DRIVE AND E: DRIVE ARE SAFE: D: drive and E: drive are designated safe zones for user files and operations, EXCEPT D:\\Projects\\Personal-Assistant which remains permanently locked under the Heavenly Restriction.\n\n"
        )

        parts = [time_ctx, identity_ctx, heavenly_ctx]
        if mem_str:
            parts.append(mem_str)
        parts.append(sys_prompt)

        return "\n".join(parts), _all_decls

    def _build_config(self) -> types.LiveConnectConfig:
        system_instruction, _all_decls = self._build_system_instruction()

        cfg = dict(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction=system_instruction,
            tools=[{"function_declarations": _all_decls}],
            # Hand back the handle captured from the last session_resumption
            # update. `handle=None` is exactly the old behaviour (ask for
            # handles, start fresh), so the first connect of a run is unchanged.
            session_resumption=types.SessionResumptionConfig(
                handle=self._resume_handle
            ),
            # Sliding-window compression: session never dies from a full context
            # window â€” JARVIS can stay in one conversation for hours
            context_window_compression=types.ContextWindowCompressionConfig(
                sliding_window=types.SlidingWindow(),
            ),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=get_voice()
                    )
                )
            ),
        )
        if self._enhanced_live:
            # Proactive audio: JARVIS stays silent when speech isn't addressed
            # to it (background chatter, talking to someone else in the room).
            # (Affective dialog was dropped: gemini-3.1-flash-live does not
            #  support it, and it never reliably detected tone in practice.
            #  To restore it on a 2.5 native-audio model, add back:
            #  cfg["enable_affective_dialog"] = True )
            if get_proactive_audio_enabled():
                cfg["proactivity"] = types.ProactivityConfig(proactive_audio=True)

        if self._tuned_live:
            cfg.update(self._tuning_config())

        return types.LiveConnectConfig(**cfg)

    def _tuning_config(self) -> dict:
        """The optional knobs, kept apart so one bad field can be dropped wholesale.

        Every one of these is a preview-API field. If a future model release
        stops accepting any of them the connection fails at setup, so the run
        loop turns `_tuned_live` off and reconnects on the plain config rather
        than leaving the user with an assistant that will not start.
        """
        out: dict = {}

        # How long the server waits through a pause before deciding your turn is
        # over. This â€” not the size of the prompt â€” is what most of the delay
        # before a reply actually is, and the default has to suit everybody, so
        # it is necessarily cautious.
        turn = get_turn_tuning()
        if turn.get("enabled", True):
            detect = types.AutomaticActivityDetection(
                silence_duration_ms=turn["silence_ms"],
                prefix_padding_ms=turn["prefix_ms"],
            )
            if turn["end_sensitivity"] == "high":
                detect.end_of_speech_sensitivity = types.EndSensitivity.END_SENSITIVITY_HIGH
            elif turn["end_sensitivity"] == "low":
                detect.end_of_speech_sensitivity = types.EndSensitivity.END_SENSITIVITY_LOW
            if turn["start_sensitivity"] == "high":
                detect.start_of_speech_sensitivity = types.StartSensitivity.START_SENSITIVITY_HIGH
            elif turn["start_sensitivity"] == "low":
                detect.start_of_speech_sensitivity = types.StartSensitivity.START_SENSITIVITY_LOW
            out["realtime_input_config"] = types.RealtimeInputConfig(
                automatic_activity_detection=detect)

        # Screenshots and camera frames are tokenised at this resolution and then
        # stay in the session's context. 'medium' keeps on-screen text legible
        # for a fraction of a full-resolution frame.
        res = get_media_resolution()
        if res != "default":
            out["media_resolution"] = {
                "low":    types.MediaResolution.MEDIA_RESOLUTION_LOW,
                "medium": types.MediaResolution.MEDIA_RESOLUTION_MEDIUM,
                "high":   types.MediaResolution.MEDIA_RESOLUTION_HIGH,
            }[res]

        # Thinking is left at the server default deliberately. Forcing the budget
        # to zero was measured on gemini-3.1-flash-live over interleaved trials
        # and did not make the first word arrive sooner â€” this model does not
        # appear to deliberate on the Live path, so pinning the field only adds a
        # way for a future release to behave differently. Set "thinking_enabled"
        # in config/api_keys.json to true to let it reason instead.
        if get_thinking_enabled():
            out["thinking_config"] = types.ThinkingConfig(thinking_budget=-1)

        return out

    async def _dispatch_tool(self, name: str, args: dict) -> str:
        _tlog("ALFRED", "control", f"{name}  {args}", self._dashboard)
        self.ui.set_state("THINKING")

        # Heavenly Restriction guard
        if _is_heavenly_restricted(args):
            _tlog("ALFRED", "warn", f"Blocked attempt to access restricted path D:\\Projects\\Personal-Assistant: {name}", self._dashboard)
            return "Due to the heavenly restriction placed upon my creator, I cannot."

        # Drive & Path Restriction guard (C: Desktop/Documents only; D: safe except source; E: safe)
        _path_ok, _path_err = _guard_check_action_params(name, args)
        if not _path_ok:
            _tlog("ALFRED", "warn", f"Blocked unauthorized path access ({name}): {_path_err}", self._dashboard)
            return _path_err

        if name == "save_memory":
            category = args.get("category", "notes")
            key      = args.get("key", "")
            value    = args.get("value", "")
            if key and value:
                update_memory({category: {key: {"value": value}}})
                _tlog("Memory", "save", f"save_memory: {category}/{key} = {value}", self._dashboard)
            return "ok"

        if name == "queue_background_task":
            task_type = str(args.get("task_type", "task")).strip()
            payload = str(args.get("payload", "")).strip()
            res = await self.queue_background_task(task_type, payload)
            return f"Background task '{task_type}' queued successfully with ID {res['task_id']}. Execution proceeds non-blocking."

        loop   = asyncio.get_event_loop()
        result = "Done."

        try:
            if name == "recall_memory":
                # Local file search: no network, no second model. Kept out of
                # the executor deliberately â€” it is a dictionary scan over a few
                # hundred short strings, and a thread hop would cost more than
                # the work itself.
                result = search_memory(args.get("query", ""), limit=8)

            elif name == "undo":
                if str(args.get("action", "")).lower().strip() == "list":
                    items = undo_stack.history()
                    result = ("Things I can undo, most recent first:\n"
                              + "\n".join(f"{i+1}. {t}" for i, t in enumerate(items))
                              ) if items else "I have not changed anything I can undo yet."
                else:
                    result = await loop.run_in_executor(None, undo_stack.undo_last)

            elif name == "sentry_focus":
                from actions.sentry_focus import sentry_focus_action
                result = sentry_focus_action(**args)

            elif name == "sentry_monitor":
                from actions.sentry_monitor import sentry_monitor_action
                _act = str(args.get("action", "status")).lower().strip()
                _tgt = str(args.get("target", "")).strip()
                _iv = float(args.get("interval_seconds", 5.0) or 5.0)
                result = sentry_monitor_action(action=_act, target=_tgt, interval_seconds=_iv)

            elif name == "screen_monitor":
                action = str(args.get("action", "status")).lower().strip()
                if action == "start":
                    goal = str(args.get("goal", "")).strip()
                    interval = float(args.get("interval_seconds", 3.0) or 3.0)
                    state = self._start_screen_monitor(goal, interval)
                    result = (
                        f"Screen monitoring active every {self._screen_monitor.status().interval_seconds:g}s. "
                        f"Goal: {state.get('goal')}."
                    )
                elif action == "stop":
                    state = self._stop_screen_monitor("Screen monitoring stopped by voice command.")
                    result = "Screen monitoring stopped." if state["stopped"] else "Screen monitoring was already off."
                elif action == "status":
                    status = self._screen_monitor.status()
                    result = (
                        f"Screen monitoring is {'active' if status.active else 'off'}. "
                        f"Goal: {status.goal or 'none'}. Captures: {status.capture_count}. "
                        f"Last stop reason: {status.stopped_reason or 'none'}."
                    )
                else:
                    result = "Specify screen_monitor action: start, stop, or status."

            elif name == "screen_process":
                import time as _t_mod
                _now = _t_mod.monotonic()
                _cooldown = 4.0  # seconds â€” covers echo window after speaking ends
                if self._vision_busy or (_now - self._vision_last_time) < _cooldown:
                    _wait = max(0, _cooldown - (_now - self._vision_last_time))
                    _tlog("Vision", "wait", f"Cooldown active ({_wait:.1f}s remaining) â€” ignoring duplicate call", self._dashboard)
                    result = "Vision is still processing the previous request. I will not call this again."
                else:
                    self._vision_busy      = True
                    self._vision_last_time = _now
                    angle     = args.get("angle", "screen").lower()
                    user_text = args.get("text", "What do you see?")
                    if angle == "camera":
                        img_b, mime_t = await loop.run_in_executor(None, _capture_camera)
                        win_ctx = ""
                        self.ui.start_camera_stream()
                        self._vision_cam_active = True
                        _tlog("Vision", "camera", f"Camera: {len(img_b):,} bytes", self._dashboard)
                        _stall = "camera"
                    else:
                        cap_res = await loop.run_in_executor(None, _capture_screen)
                        img_b = cap_res[0]
                        mime_t = cap_res[1]
                        win_ctx = cap_res[2] if len(cap_res) > 2 else getattr(cap_res, "window_context", "")
                        _tlog("Vision", "screen", f"Screen: {len(img_b):,} bytes", self._dashboard)
                        _stall = "screen"
                    self._pending_vision = (img_b, mime_t, user_text, angle, win_ctx)
                    # The image is attached to this same exchange, so there is
                    # nothing to stall for and nothing to announce. Asking for an
                    # acknowledgement here is what produced two spoken answers â€”
                    # the model filled that turn by answering the question from
                    # imagination, then answered it again once it could see.
                    result = (
                        f"[VISION_ACTIVE] {_stall.capitalize()} captured and attached to this "
                        f"same exchange. Do not acknowledge and do not answer yet â€” the image "
                        f"is arriving with this result. Reply once, from what you actually see "
                        f"in it."
                    )

            elif name == "close_camera":
                self.ui.stop_camera_stream()
                result = "Camera closed."

            elif name == "system_status":
                r = await loop.run_in_executor(None, get_system_status)
                result = str(r)

            elif name == "manage_monitor":
                action = args.get("action", "").lower().strip()
                topic  = args.get("topic", "").strip()
                if action == "add" and topic:
                    result = await asyncio.to_thread(add_monitor, topic)
                elif action == "remove" and topic:
                    result = await asyncio.to_thread(remove_monitor, topic)
                elif action == "list":
                    topics = await asyncio.to_thread(list_monitors)
                    result = ("Monitoring: " + ", ".join(topics)) if topics else "No topics are being monitored."
                else:
                    result = "Specify action (add/remove/list) and a topic."

            elif name == "clear_chat":
                self.ui.clear_chat()
                self._session_log.clear()
                if self._dashboard:
                    await self._dashboard.broadcast({"type": "clear_chat"})
                result = "Conversation history and on-screen chat feed have been wiped clean, sir."

            elif name == "shutdown_jarvis":
                self.ui.write_log("SYS: Shutdown requested.")
                async def _do_shutdown():
                    self._screen_monitor.stop(wait=False)
                    await self._save_session_summary()
                    if self.session:
                        try:
                            await self.session.send_client_content(
                                turns={"role": "user", "parts": [{"text": "Say a brief natural goodbye to the user."}]},
                                turn_complete=True,
                            )
                        except Exception:
                            pass
                    await asyncio.sleep(1.5)
                    import os as _os
                    _os._exit(0)
                asyncio.create_task(_do_shutdown())

            elif self._action_registry.has(name):
                # file_processor: fall back to the currently-uploaded file when none is given
                if name == "file_processor" and not args.get("file_path") and self.ui.current_file:
                    args["file_path"] = self.ui.current_file
                _ctx = {"player": self.ui, "speak": self.speak,
                        "response": None, "session_memory": None}
                r = await loop.run_in_executor(None, lambda: self._action_registry.run(name, args, _ctx))
                result = r or "Done."
                # web_search: mirror results to the on-screen content panel
                if (name == "web_search" and r
                        and not r.startswith("No results")
                        and not r.startswith("Search failed")):
                    _mode  = args.get("mode", "search")
                    _query = args.get("query") or ", ".join(args.get("items", []))
                    _label = f"{_mode.upper()} â€” {_query[:38]}" if _query else _mode.upper()
                    self.ui.show_content(_label, r)

            else:
                if self._plugin_registry.has(name):
                    r = await loop.run_in_executor(
                        None,
                        lambda: self._plugin_registry.run(name, args, player=self.ui, session_memory=None)
                    )
                    result = r or "Done."
                else:
                    result = f"Unknown tool: {name}"

        except Exception as e:
            result = f"Tool '{name}' failed: {e}"
            traceback.print_exc()

        _tlog("ALFRED", "out", f"{name} → {str(result)[:80]}", self._dashboard)

        # Notify dashboard / phone if a screenshot was produced
        if name == "computer_control" and args.get("action") == "screenshot":
            try:
                upload_dir = Path(__file__).resolve().parent / "dashboard" / "uploads"
                screens = sorted(upload_dir.glob("alfred_screenshot_*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
                if screens and self._dashboard:
                    latest = screens[0]
                    asyncio.create_task(self._dashboard.broadcast({
                        "type": "file_received",
                        "name": latest.name,
                        "path": f"/uploads/{latest.name}",
                        "size": latest.stat().st_size,
                        "is_screenshot": True,
                    }))
            except Exception:
                pass

        return str(result)

    async def _execute_tool(self, fc) -> types.FunctionResponse:
        name = fc.name
        args = dict(fc.args or {})

        if name == "save_memory":
            res = await self._dispatch_tool(name, args)
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            return types.FunctionResponse(
                id=fc.id, name=name,
                response={"result": res, "silent": True}
            )

        result = await self._dispatch_tool(name, args)

        if not self.ui.muted:
            self.ui.set_state("LISTENING")

        _sched = (self._action_registry.scheduling(name)
                  or self._plugin_registry.scheduling(name))
        _extra = {"scheduling": _sched} if _sched else {}
        return types.FunctionResponse(
            id=fc.id, name=name,
            response={"result": result},
            **_extra
        )

    async def _send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            # Gemini 3.x Live rejects the old realtime_input.media_chunks field
            # (what `media=...` maps to) and closes the socket with a 1007. Send
            # mic / phone PCM through the new `audio` field instead. Queue items
            # are {"data": <bytes>, "mime_type": <str>} from _listen_audio and
            # the phone relay.
            await self.session.send_realtime_input(
                audio=types.Blob(
                    data=msg["data"],
                    mime_type=msg.get("mime_type", "audio/pcm"),
                )
            )

    async def _listen_audio(self):
        _tlog("ALFRED", "mic", "Mic started", self._dashboard)
        loop = asyncio.get_event_loop()

        def callback(indata, frames, time_info, status):
            # â”€â”€ Wake-word gate â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            # While asleep, the mic audio NEVER goes to Gemini (nothing is
            # streamed, so JARVIS can't respond to speech not addressed to it and
            # nothing leaves the machine). Frames are instead handed to the local
            # detector, which runs its model in ITS OWN thread â€” the cost here is
            # only a queue push, so the audio path is never slowed. When wake word
            # is off (default) or we're awake, this is a single boolean check.
            if self._wake_enabled and not self._awake:
                det = self._wake_detector
                if det is not None:
                    det.feed(indata)
                return
            with self._speaking_lock:
                jarvis_speaking = self._is_speaking

            # â”€â”€ Barge-in â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            # While JARVIS talks the mic is not streamed, but it is still worth
            # listening to locally: if the user starts speaking, cut the answer
            # short the way a person would stop when interrupted.
            #
            # The whole difficulty is echo â€” on speakers the mic hears JARVIS.
            # So the test is not "is the mic loud" but "is the mic louder than
            # the echo of what we are playing right now", sustained long enough
            # that a cough or a keystroke cannot trigger it.
            if jarvis_speaking:
                # Nothing is streamed while JARVIS talks.
                #
                # Interrupting by voice used to live here: `EchoGuard` can pick a
                # user out from under our own echo, and `core/echo.py` still does
                # that for the tail below. Re-enabling is small â€” classify each
                # block here and call interrupt() after `required_blocks` of
                # agreement â€” but it depends on the listener's room, so it stays
                # out until it can be tried on real hardware.
                return

            # â”€â”€ Echo tail â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            # The speaking flag has dropped but the speakers have not finished.
            # Sending this to the model is how an assistant hears itself, decides
            # it was addressed, and answers its own last sentence. The microphone
            # stays OPEN â€” the guard only drops blocks that are our own voice, so
            # replying the instant it stops still works.
            if self._tail_active():
                try:
                    if not self._echo.is_user_speech(
                            indata, SEND_SAMPLE_RATE, _pcm_level(indata)):
                        return
                    self._tail_until = 0.0      # a real voice ends the tail early
                except Exception:
                    return
            elif self._echo._hist:
                self._echo.reset()

            # â”€â”€ Push-to-talk â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            # When it is on the microphone is closed by default and the chord
            # opens it, which is the whole point: nothing leaves the machine
            # unless you are holding the key.
            if self._ptt_enabled and not self._ptt_held:
                return

            if not self.ui.muted and not self._phone_active:
                data = indata.tobytes()
                def _push_mic():
                    try:
                        self.out_queue.put_nowait({"data": data, "mime_type": "audio/pcm"})
                    except Exception:
                        pass
                loop.call_soon_threadsafe(_push_mic)
                # Feed the live mic level to the HUD so the waveform reacts to
                # the user's actual voice while listening. Purely cosmetic â€” any
                # failure here must never disturb the mic.
                try:
                    self.ui.set_audio_level(_pcm_level(indata))
                except Exception:
                    pass

        try:
            def _open_mic(dev):
                return sd.InputStream(
                    samplerate=SEND_SAMPLE_RATE,
                    channels=CHANNELS,
                    dtype="int16",
                    blocksize=CHUNK_SIZE,
                    device=dev,
                    callback=callback,
                )

            # Which microphone. resolve() returns None for "system default" and
            # for a saved device that is no longer present â€” so a headset
            # unplugged since the last run falls back to the built-in mic
            # instead of raising on startup and taking the session with it.
            _mic_name = get_input_device()
            _mic_dev  = audio_devices.resolve(_mic_name, "input")
            if _mic_dev is not None:
                _tlog("ALFRED", "mic", f"Input device: {_mic_name}", self._dashboard)
            try:
                _mic_stream = _open_mic(_mic_dev)
            except Exception as _e:
                # A device the picker listed but the driver will not open right
                # now â€” exclusive mode, a webcam already in use, a virtual mic
                # whose source went away. Chosen hardware failing must never
                # mean the assistant cannot hear at all.
                if _mic_dev is None:
                    raise
                _tlog("ALFRED", "warn", f"Mic '{_mic_name}' failed: {_e} â€” using default", self._dashboard)
                self.ui.write_log(
                    f"SYS: Microphone '{_mic_name}' unavailable â€” using system default."
                )
                _mic_stream = _open_mic(None)

            with _mic_stream:
                _tlog("ALFRED", "mic", "Mic stream open", self._dashboard)
                while True:
                    await asyncio.sleep(0.1)
        except Exception as e:
            _tlog("ALFRED", "error", f"Mic: {e}", self._dashboard)
            raise

    async def _flush_pending_vision(self) -> bool:
        """Send a captured frame immediately after its tool response.

        The frame is already in hand by the time `screen_process` returns â€” the
        capture happened inside the tool call. The old flow still made the model
        speak a turn first and only injected the image on that turn's
        turn_complete, which cost a whole extra round trip AND produced two
        spoken answers: one improvised without the picture, then the real one.
        Sending it here means the model has the tool result and the image before
        it generates anything, so the user gets one answer, sooner.
        """
        if not (self._pending_vision and self.session):
            return False

        import base64 as _b64
        if len(self._pending_vision) >= 5:
            img_b, mime_t, question, angle, win_ctx = self._pending_vision
        else:
            img_b, mime_t, question, angle = self._pending_vision
            win_ctx = ""
        self._pending_vision = None
        b64 = _b64.b64encode(img_b).decode("ascii")
        _tlog("Vision", "out", f"{len(img_b):,} bytes (angle={angle}) â†’ main session", self._dashboard)

        # Label the source. Without it the image arrives carrying nothing but
        # the user's own sentence, and a screenshot of this app â€” which has a
        # face in the middle of it â€” got read as a photo of the user. What the
        # label *means* is explained once, in the generated [SELF] block.
        src = ("[IMAGE SOURCE: WEBCAM]" if angle == "camera"
               else "[IMAGE SOURCE: SCREEN CAPTURE]")
        text_payload = f"{win_ctx}\n\n{src}\n\n{question}".strip() if win_ctx else f"{src}\n\n{question}"
        await self.session.send_client_content(
            turns={"role": "user", "parts": [
                {"inline_data": {"mime_type": mime_t, "data": b64}},
                {"text": text_payload},
            ]},
            turn_complete=True,
        )

        if self._vision_cam_active:
            # Camera: stay busy until JARVIS has finished speaking the answer,
            # then close the preview.
            self._vision_cam_active    = False
            self._vision_close_pending = True
        else:
            self._vision_busy = False
        return True

    async def _receive_audio(self):
        _tlog("ALFRED", "listen", "Recv started", self._dashboard)
        out_buf, in_buf = [], []

        try:
            while True:
                async for response in self.session.receive():

                    # â”€â”€ Session resumption â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                    # The server sends this periodically. `resumable` goes false
                    # while a turn is mid-flight â€” replaying a handle from that
                    # moment is what the flag exists to prevent â€” so only
                    # resumable handles are kept. This is three lines and it is
                    # the entire fix for "every reconnect forgets everything".
                    _sru = getattr(response, "session_resumption_update", None)
                    if _sru is not None:
                        if getattr(_sru, "resumable", False) and getattr(_sru, "new_handle", None):
                            if self._resume_handle is None:
                                _tlog("ALFRED", "link", "Session resumption armed", self._dashboard)
                            self._resume_handle = _sru.new_handle

                    if response.data:
                        if self._interrupted:
                            pass  # discard: interrupted
                        else:
                            if self._turn_done_event and self._turn_done_event.is_set():
                                self._turn_done_event.clear()
                            # Split into ~50 ms chunks so interrupt() stops audio within 50 ms
                            # (24000 Hz Ã— 2 bytes/sample Ã— 0.05 s = 2400 bytes per slice)
                            _audio_data = response.data
                            _SLICE = 2400
                            for _i in range(0, len(_audio_data), _SLICE):
                                self.audio_in_queue.put_nowait(_audio_data[_i : _i + _SLICE])

                    if response.server_content:
                        sc = response.server_content

                        # Server-side interruption detection (Gemini VAD detected user speech)
                        if getattr(sc, "interrupted", False):
                            _tlog("ALFRED", "halt", "Server-side interruption signal received", self._dashboard)
                            self.interrupt()
                            in_buf = []
                            out_buf = []
                            self._visemes.reset()
                            continue

                        # Forward internal deliberation / cognitive-trace if model returns thought parts
                        _mt = getattr(sc, "model_turn", None)
                        if _mt and getattr(_mt, "parts", None):
                            for _p in _mt.parts:
                                if getattr(_p, "thought", False):
                                    _th = (getattr(_p, "text", "") or "").strip()
                                    if _th:
                                        self.ui.set_state("THINKING")
                                        self.ui.write_log(f"THINK: {_th}")

                        if sc.output_transcription and sc.output_transcription.text:
                            txt = _clean_transcript(sc.output_transcription.text)
                            # A turn that involves a tool call passes through
                            # several turn_completes, and the API re-sends the
                            # tail of the transcript across them. Comparing only
                            # against the previous chunk missed that â€” once
                            # out_buf had been flushed and emptied, the repeat
                            # sailed straight back in, which logged the answer
                            # twice AND made the avatar mouth it twice.
                            if txt and not _is_repeat_chunk(txt, out_buf):
                                out_buf.append(txt)
                                # Hand the words to the mouth as they arrive, so
                                # the avatar can form the consonants the audio
                                # alone cannot show. Pure string work â€” it adds
                                # nothing measurable to the response path.
                                self._visemes.feed_text(txt)

                        if sc.input_transcription and sc.input_transcription.text:
                            txt = _clean_transcript(sc.input_transcription.text)
                            if txt:
                                in_buf.append(txt)
                                self._last_user_speech = time.monotonic()

                        if sc.turn_complete:
                            if self._turn_done_event:
                                self._turn_done_event.set()

                            # If this turn_complete ends an interrupted response, clear the
                            # flag and skip all further processing for that turn.
                            if self._interrupted:
                                self._interrupted = False
                                in_buf  = []
                                out_buf = []
                                self._visemes.reset()
                                continue

                            full_in = " ".join(in_buf).strip()
                            if full_in:
                                if getattr(self, "monitor_controller", None) and self.monitor_controller.is_waiting_for_answer:
                                    self.monitor_controller.submit_answer(full_in)
                                self._last_out_logged = ""   # new exchange
                                self.ui.write_log(f"You: {full_in}")
                                self._session_log.append(f"User: {full_in}")
                                if self._dashboard:
                                    asyncio.create_task(self._dashboard.broadcast({
                                        "type": "log", "speaker": "user",
                                        "text": full_in,
                                        "ts": datetime.now().isoformat(),
                                    }))
                            in_buf = []

                            full_out = " ".join(out_buf).strip()
                            # Second line of defence: even if a repeat slips
                            # into a *fresh* buffer after a flush, never log the
                            # same answer (or a tail of it) twice in a row.
                            if full_out and len(full_out) >= _REPEAT_MIN and self._last_out_logged:
                                if full_out in self._last_out_logged:
                                    full_out = ""
                            if full_out:
                                self._last_out_logged = full_out
                                self.ui.write_log(f"{self._asst_name}: {full_out}")
                                self._session_log.append(f"{self._asst_name}: {full_out}")
                                if self._dashboard:
                                    asyncio.create_task(self._dashboard.broadcast({
                                        "type": "log", "speaker": self._asst_name.lower(),
                                        "text": full_out,
                                        "ts": datetime.now().isoformat(),
                                    }))
                            out_buf = []

                            if self._vision_close_pending:
                                # This turn_complete IS the vision answer â€” close camera + release busy flag
                                self._vision_close_pending = False
                                self._vision_busy = False
                                async def _cam_close():
                                    await asyncio.sleep(2.0)
                                    self.ui.stop_camera_stream()
                                asyncio.create_task(_cam_close())

                    if response.tool_call:
                        fcs = response.tool_call.function_calls or []
                        # Concurrency-controlled worker pool (max 5 workers to avoid socket/resource exhaustion)
                        _MAX_WORKERS = 5
                        sem = asyncio.Semaphore(_MAX_WORKERS)

                        async def _run_tool_bounded(fc):
                            async with sem:
                                self._tool_calls_active += 1
                                _tlog("ALFRED", "phone", fc.name, self._dashboard)
                                try:
                                    return await self._execute_tool(fc)
                                except Exception as err:
                                    _tlog("ALFRED", "error", f"Tool {fc.name} error: {err}", self._dashboard)
                                    return {
                                        "id": getattr(fc, "id", None),
                                        "name": fc.name,
                                        "response": {"result": f"Execution error: {err}"}
                                    }
                                finally:
                                    self._tool_calls_active = max(0, self._tool_calls_active - 1)

                        # Run promises concurrently with controlled worker pool, preserving item order
                        fn_responses = await asyncio.gather(*[_run_tool_bounded(fc) for fc in fcs])
                        await self.session.send_tool_response(
                            function_responses=list(fn_responses)
                        )
                        await self._flush_pending_vision()
        except Exception as e:
            _tlog("ALFRED", "error", f"Recv: {e}", self._dashboard)
            traceback.print_exc()
            raise

    async def _play_audio(self):
        _tlog("ALFRED", "speaker", "Play started", self._dashboard)

        _spk_name = get_output_device()
        _spk_dev  = audio_devices.resolve(_spk_name, "output")
        if _spk_dev is not None:
            _tlog("ALFRED", "speaker", f"Output device: {_spk_name}", self._dashboard)

        def _open_spk(dev):
            st = sd.RawOutputStream(
                samplerate=RECEIVE_SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=0,
                device=dev,
                latency="high",
            )
            st.start()
            return st

        try:
            stream = _open_spk(_spk_dev)
        except Exception as _e:
            # A chosen output that the host API accepts by name but refuses to
            # open (exclusive mode, wrong sample rate, device asleep) must not
            # cost the user their voice. Fall back to the default and say so.
            if _spk_dev is None:
                raise
            _tlog("ALFRED", "warn", f"Output device '{_spk_name}' failed: {_e} — using default", self._dashboard)
            self.ui.write_log(f"SYS: Speaker '{_spk_name}' unavailable — using system default.")
            stream = _open_spk(None)

        # Ask the device how far behind the speakers actually are, rather than
        # assuming. This is what the echo tail is sized from, so a machine with a
        # large audio buffer gets a correspondingly longer guard — and one with a
        # tiny buffer is not penalised with a delay it does not need.
        try:
            lat = float(getattr(stream, "latency", 0.0) or 0.0)
            if 0.0 < lat < 1.0:
                self._out_latency = lat
            _tlog("ALFRED", "speaker", f"Output latency {self._out_latency*1000:.0f} ms → echo tail {(self._out_latency + _TAIL_MARGIN)*1000:.0f} ms", self._dashboard)
        except Exception:
            pass

        empty_count = 0
        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(
                        self.audio_in_queue.get(),
                        timeout=0.12
                    )
                except asyncio.TimeoutError:
                    if (
                        self._turn_done_event
                        and self._turn_done_event.is_set()
                        and self.audio_in_queue.empty()
                    ):
                        empty_count += 1
                        if empty_count >= 3:
                            self.set_speaking(False)
                            self._turn_done_event.clear()
                            empty_count = 0
                    continue

                empty_count = 0
                batch = bytearray(chunk)

                # Pre-buffering jitter cushion for fresh utterance to prevent buffer underrun crackle
                if not self._is_speaking:
                    t_pre = time.monotonic()
                    # Buffer up to ~250 ms (12000 bytes) or max 200 ms wait before starting speech
                    while len(batch) < 12000 and (time.monotonic() - t_pre) < 0.20:
                        if self._turn_done_event and self._turn_done_event.is_set():
                            break
                        try:
                            batch.extend(self.audio_in_queue.get_nowait())
                        except asyncio.QueueEmpty:
                            await asyncio.sleep(0.015)
                    self.set_speaking(True)

                # Batch available chunks into one write to reduce thread-pool round-trips
                # (12000 bytes â‰ˆ 250 ms at 24 kHz / 16-bit mono)
                while len(batch) < 12000:
                    try:
                        batch.extend(self.audio_in_queue.get_nowait())
                    except asyncio.QueueEmpty:
                        break

                # Drive the HUD waveform and the avatar's mouth from JARVIS's
                # own voice. The batch is up to 200 ms long, so we hand over a
                # *schedule* of 20 ms viseme frames instead of a single averaged
                # level and let the HUD play it out in step with the audio.
                try:
                    pcm = np.frombuffer(bytes(batch), dtype=np.int16)
                    hop = _VIS_HOP / RECEIVE_SAMPLE_RATE
                    frames = _pcm_visemes(pcm, sr=RECEIVE_SAMPLE_RATE)
                    # When does this batch become audible? The stream was
                    # started at launch and its callback has been pulling
                    # silence ever since, so the first bytes of a reply reach
                    # the speaker about one callback period later â€” NOT one
                    # buffer later. `stream.latency` reports the buffer's
                    # capacity, which is how much can be queued ahead, and on
                    # Windows that is commonly 300-500 ms. Anchoring on it put
                    # the entire schedule a buffer late; that is the half second
                    # of lag, and it grew with whatever the device reported.
                    #
                    # After the anchor nothing needs measuring: the device
                    # consumes at exactly realtime, so each batch sounds one
                    # batch-duration after the one before it. The cursor is
                    # re-anchored only when it leaves the range physically
                    # possible â€” behind `now` means the device drained and this
                    # batch starts a fresh stretch of speech, while further
                    # ahead than the buffer can hold means it has drifted.
                    now = time.time()
                    horizon = self._out_latency + _CURSOR_SLACK
                    if not (now <= self._play_cursor <= now + horizon):
                        self._play_cursor = now + _FIRST_SOUND
                    at = self._play_cursor
                    # Advance by the batch's own duration whether or not it
                    # yielded frames, so a block too short to analyse cannot
                    # shift everything after it out of step with the audio.
                    self._play_cursor += pcm.size / RECEIVE_SAMPLE_RATE
                    if frames:
                        frames = self._visemes.frames(frames, hop)
                        self.ui.push_visemes(frames, hop, at)
                        # Barge-in needs to know what we are playing, not just
                        # how loud: the guard subtracts this from the microphone.
                        self._out_level = max(f[0] for f in frames)
                        self._echo.note_output(pcm, RECEIVE_SAMPLE_RATE,
                                               self._out_level)
                    else:
                        lvl = _pcm_level(pcm)
                        self.ui.set_audio_level(lvl)
                        self._out_level = lvl
                        self._echo.note_output(pcm, RECEIVE_SAMPLE_RATE, lvl)
                except Exception:
                    pass

                try:
                    await asyncio.to_thread(stream.write, bytes(batch))
                except (RuntimeError, asyncio.CancelledError):
                    break   # executor shutting down â€” exit cleanly
        except Exception as e:
            _tlog("ALFRED", "error", f"Play: {e}", self._dashboard)
            raise
        finally:
            self.set_speaking(False)
            try:
                from core.audio_ducker import unduck_media_apps
                unduck_media_apps()
            except Exception:
                pass
            stream.stop()
            stream.close()

    # â”€â”€ Morning briefing â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def _send_startup_briefing(self) -> None:
        """Fetch startup context concurrently and deliver one uninterrupted brief."""
        self._briefing_cancelled = False
        started_at = time.monotonic()
        memory = await asyncio.to_thread(load_memory)
        identity = memory.get("identity", {})
        prefs = memory.get("preferences", {})

        def _val(key: str) -> str:
            entry = identity.get(key, {})
            return (entry.get("value", "") if isinstance(entry, dict) else str(entry)).strip()

        def _pref(key: str) -> str:
            entry = prefs.get(key, {})
            return (entry.get("value", "") if isinstance(entry, dict) else str(entry)).strip()

        lang = _val("language")
        name = _val("name")
        brief_pref = _pref("briefing_preference")
        time_str = datetime.now().strftime("%H:%M")
        news_query = f"{brief_pref} news today" if brief_pref else "top world news today"
        news_future = asyncio.create_task(asyncio.to_thread(_fetch_news_sync, news_query))

        lang_clause = (
            f" Speak this greeting in {lang}, then follow the user's own language "
            "from their first reply onward."
            if lang else ""
        )
        name_clause = f" Address the user as {name}." if name else ""

        last = await asyncio.to_thread(pop_last_session)
        session_clause = ""
        if last:
            try:
                delta = (datetime.now() - datetime.strptime(last["date"], "%Y-%m-%d")).days
                when = "earlier today" if delta == 0 else ("yesterday" if delta == 1 else f"{delta} days ago")
            except Exception:
                when = "last time"
            session_clause = f" Also briefly and naturally mention that {when}: {last['summary']}"

        try:
            news_text = await asyncio.wait_for(news_future, timeout=8.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            news_text = ""
        except Exception as exc:
            self.ui.write_log(f"SYS: News fetch timed out/failed: {exc!r}")
            news_text = ""

        if (
            not self.session
            or self._briefing_cancelled
            or self._interrupted
            or (self._last_user_speech - started_at) > 0.5
        ):
            return

        failed = (not news_text) or news_text.startswith(
            ("No news found", "Search failed", "Please provide")
        )
        if failed:
            news_section = "News is unavailable right now."
        else:
            topic_label = f"NEWS - {brief_pref}" if brief_pref else "NEWS - top world news today"
            self.ui.show_content(topic_label, news_text)
            news_section = news_text

        prompt = (
            "[STARTUP_BRIEFING] Deliver this as ONE continuous, compact spoken briefing. "
            "Greet the user warmly, mention the current time, mention the prior-session "
            "context when supplied, and summarize one headline in one sentence. Say that "
            "the full headline list is on screen. Do not call any tools and do not announce "
            f"that you are fetching anything. Current time: {time_str}.{session_clause}\n"
            f"Headlines:\n{news_section}{lang_clause}{name_clause}"
        )
        if await self._send_proactive_prompt(prompt):
            _tlog("ALFRED", "brief", "Single-turn startup briefing sent.", self._dashboard)

    async def _send_startup_briefing_legacy(self) -> None:
        """
        Two-phase briefing optimized for speed:
          Phase 1 â€” instant greeting (no tools) â†’ speech starts in <1s
          Phase 2 â€” news pre-fetched in a background thread while Phase 1 plays,
                    delivered as ready text (no Gemini tool-call round-trip) and
                    shown on the UI content panel. Waits for turn_complete event
                    instead of a fixed sleep so there is no unnecessary gap.
        """
        self._briefing_cancelled = False
        memory   = load_memory()
        identity = memory.get("identity", {})
        prefs    = memory.get("preferences", {})

        def _val(k: str) -> str:
            e = identity.get(k, {})
            return (e.get("value", "") if isinstance(e, dict) else str(e)).strip()

        def _pref(k: str) -> str:
            e = prefs.get(k, {})
            return (e.get("value", "") if isinstance(e, dict) else str(e)).strip()

        lang = _val("language")
        name = _val("name")
        brief_pref = _pref("briefing_preference")
        time_str = datetime.now().strftime("%H:%M")

        # Start fetching news immediately â€” runs in parallel while phase 1 plays
        news_query = f"{brief_pref} news today" if brief_pref else "top world news today"
        loop = asyncio.get_event_loop()
        news_future = loop.run_in_executor(None, _fetch_news_sync, news_query)

        await asyncio.sleep(0.3)
        if not self.session or self._briefing_cancelled or self._interrupted:
            return

        # â”€â”€ Phase 1: instant greeting â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # The briefing fires before the user has said anything, so the
        # remembered language is the only signal there is. It is a starting
        # point, not a setting: the moment they reply, their language wins.
        lang_clause = (f" Speak this greeting in {lang}, then follow the "
                       f"user's own language from their first reply onward."
                       if lang else "")
        name_clause = f" Address the user as {name}." if name else ""

        # Inject last session context if available â€” pop removes it so it's never repeated
        last = await asyncio.to_thread(pop_last_session)
        session_clause = ""
        if last:
            try:
                _delta = (datetime.now() - datetime.strptime(last["date"], "%Y-%m-%d")).days
                _when  = "earlier today" if _delta == 0 else ("yesterday" if _delta == 1 else f"{_delta} days ago")
            except Exception:
                _when = "last time"
            session_clause = (
                f" Also briefly and naturally mention that {_when}: {last['summary']}"
            )

        p1 = (
            f"Greet the user warmly, mention it is {time_str}, and say you are fetching today's news now.{session_clause} "
            f"Keep it to 2 short sentences max. Do not call any tools.{lang_clause}{name_clause}"
        )

        # Clear the turn-done event so we can wait for Phase 1 to finish
        if self._turn_done_event:
            self._turn_done_event.clear()

        phase1_start_time = time.monotonic()
        await self.session.send_client_content(
            turns={"role": "user", "parts": [{"text": p1}]},
            turn_complete=True,
        )
        _tlog("ALFRED", "brief", "Briefing phase 1 (greeting) sent.", self._dashboard)

        # â”€â”€ Phase 2: fire as soon as Phase 1 audio is done â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        async def _deliver_news():
            try:
                lang_str = (f" Speak in {lang} unless the user has since "
                            f"spoken another language, in which case use theirs."
                            if lang else "")

                # Wait for news fetch (already running) and Phase 1 turn-complete
                # in parallel â€” whichever takes longer determines the wait time
                news_done   = asyncio.wrap_future(news_future)
                turn_waited = False
                if self._turn_done_event:
                    try:
                        await asyncio.wait_for(self._turn_done_event.wait(), timeout=6.0)
                        turn_waited = True
                    except (asyncio.TimeoutError, asyncio.CancelledError):
                        pass

                # If user interrupted Phase 1, abort Phase 2 immediately
                if self._briefing_cancelled or self._interrupted or not self.session:
                    _tlog("ALFRED", "brief", "Briefing phase 2 aborted (user interrupted).", self._dashboard)
                    return

                # If user spoke between Phase 1 and now, cancel news injection
                if (self._last_user_speech - phase1_start_time) > 0.5:
                    _tlog("ALFRED", "brief", "Briefing phase 2 aborted (user actively speaking).", self._dashboard)
                    return

                if turn_waited:
                    await asyncio.sleep(0.8)
                else:
                    await asyncio.sleep(1.0)

                if self._briefing_cancelled or self._interrupted or not self.session:
                    return

                try:
                    news_text = await asyncio.wait_for(news_done, timeout=8.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    news_text = ""
                except Exception as e:
                    self.ui.write_log(f"SYS: News fetch timed out/failed: {e!r}")
                    news_text = ""

                # Double check cancellation before delivering to Gemini session
                if self._briefing_cancelled or self._interrupted or not self.session:
                    return

                if (self._last_user_speech - phase1_start_time) > 0.5:
                    _tlog("ALFRED", "brief", "Briefing phase 2 aborted (user spoke during fetch).", self._dashboard)
                    return

                failed = (not news_text) or news_text.startswith(
                    ("No news found", "Search failed", "Please provide")
                )
                if not failed:
                    topic_label = f"NEWS â€” {brief_pref}" if brief_pref else "NEWS â€” top world news today"
                    # Show on UI content panel immediately
                    self.ui.show_content(topic_label, news_text)

                    pref_note = f" tailored to your preferences ({brief_pref})" if brief_pref else ""
                    p2 = (
                        f"[BRIEFING] Here are today's top headlines{pref_note}:\n{news_text}\n\n"
                        "Pick ONE headline, summarise it in one sentence, then say the full list "
                        f"is displayed on screen. Do not call any tools.{lang_str}"
                    )
                else:
                    self.ui.write_log(
                        f"SYS: News unavailable â€” backend returned: {news_text[:120]!r}"
                    )
                    p2 = (
                        "News headlines could not be fetched right now. "
                        f"Let the user know briefly.{lang_str}"
                    )

                if self._briefing_cancelled or self._interrupted or not self.session:
                    return

                await self.session.send_client_content(
                    turns={"role": "user", "parts": [{"text": p2}]},
                    turn_complete=True,
                )
                _tlog("ALFRED", "brief", "Briefing phase 2 (news) sent.", self._dashboard)
            except asyncio.CancelledError:
                _tlog("ALFRED", "brief", "Briefing phase 2 task cancelled.", self._dashboard)
            except Exception as e:
                _tlog("ALFRED", "error", f"Briefing phase 2 failed: {e}", self._dashboard)
                self.ui.write_log("SYS: Could not fetch the news for the briefing.")

        self._deliver_news_task = asyncio.create_task(_deliver_news())

    # â”€â”€ Session memory â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def _save_session_summary(self) -> None:
        """Summarise the current session in 1-2 sentences and save to long_term.json."""
        log = self._session_log
        if len(log) < 3:          # need at least one exchange to be worth saving
            return
        self._session_log = []    # reset immediately so the next session starts clean

        memory = load_memory()
        lang_entry = memory.get("identity", {}).get("language", {})
        lang = (lang_entry.get("value", "") if isinstance(lang_entry, dict) else str(lang_entry)).strip()
        lang = lang or "English"

        convo = "\n".join(log[-40:])   # cap at last 40 turns to stay within token budget
        prompt = (
            f"Summarize this conversation in 1-2 sentences in {lang}. "
            "Focus on what the user accomplished or discussed. "
            "Output ONLY the summary text, nothing else:\n\n" + convo
        )
        try:
            from core import gemini
            summary = await asyncio.to_thread(
                gemini.text, prompt, gemini.SMART, None, 30_000,
            )
            if summary:
                save_session_summary(summary, lang)
        except Exception as e:
            print(f"[Memory] âš ï¸ Session summary failed: {e}")

    # â”€â”€ System monitor â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def _run_system_monitor(self) -> None:
        """Background task: voice alerts when metrics exceed thresholds."""
        while True:
            await asyncio.sleep(10)
            alert = await asyncio.to_thread(self._sys_monitor.check)
            if not alert or not self.session or not self._awake:
                continue
            # Don't interrupt an active conversation
            with self._speaking_lock:
                speaking = self._is_speaking
            if speaking or (time.monotonic() - self._last_user_speech) < 10:
                continue
            try:
                await self._send_proactive_prompt(alert)
            except Exception as e:
                print(f"[Monitor] âš ï¸ Could not send alert: {e}")

    # â”€â”€ Background monitor â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def _run_background_monitor(self) -> None:
        """Check user-configured topics once per day; speak alerts when new headlines appear."""
        await asyncio.sleep(300)          # wait 5 min after startup before first check
        while True:
            if self.session and self._awake:
                # Don't interrupt if user spoke recently or JARVIS is mid-sentence
                with self._speaking_lock:
                    speaking = self._is_speaking
                recent_speech = (time.monotonic() - self._last_user_speech) < 45
                if not speaking and not recent_speech and not self._interrupted:
                    try:
                        alerts = await asyncio.to_thread(monitor_check_all)
                        memory = load_memory()
                        lang_e = memory.get("identity", {}).get("language", {})
                        lang   = (lang_e.get("value", "") if isinstance(lang_e, dict) else str(lang_e)).strip() or "English"
                        if alerts and not self._interrupted:
                            joined = "\n\n".join(alerts)
                            msg = (
                                f"{joined}\n\n"
                                f"Briefly summarize these monitored developments in {lang} as ONE "
                                "continuous update. Group related headlines and do not call tools."
                            )
                            if await self._send_proactive_prompt(msg, timeout=180.0):
                                _tlog(
                                    "ALFRED", "monitor",
                                    f"Monitor update sent ({len(alerts)} headline(s)).",
                                    self._dashboard,
                                )
                    except Exception as e:
                        print(f"[Monitor] âš ï¸ Background check error: {e}")
            await asyncio.sleep(1800)     # check every 30 minutes

    # â”€â”€ Proactive mode â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def _run_proactive_mode(self) -> None:
        """
        Background task: periodically checks if the user has been silent long enough,
        then hands time + memory context to Gemini so it can decide what (if anything)
        to say proactively. No hardcoded rules â€” Gemini makes the call.
        """
        while True:
            await asyncio.sleep(60)   # evaluate once per minute

            if not self.session or not self._awake:
                continue

            with self._speaking_lock:
                speaking = self._is_speaking
            if speaking:
                continue

            if not self._proactive.should_trigger(self._last_user_speech):
                continue

            self._proactive.mark_triggered()

            try:
                memory       = await asyncio.to_thread(load_memory)
                monitors     = await asyncio.to_thread(list_monitors)
                recent_turns = self._session_log[-8:] if self._session_log else []
                prompt = self._proactive.build_prompt(
                    memory       = memory,
                    monitors     = monitors or None,
                    recent_turns = recent_turns or None,
                )
                if await self._send_proactive_prompt(prompt):
                    _tlog("ALFRED", "proactive", "Proactive check-in.", self._dashboard)
            except Exception as e:
                print(f"[Proactive] âš ï¸ {e}")

    # â”€â”€ Background GC maintenance â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def _run_gc_manager(self) -> None:
        """
        Periodically sweeps garbage during idle silence so full Generation 2
        collections never pause threads mid-speech or during active UI animations.
        """
        while True:
            await asyncio.sleep(45)
            with self._speaking_lock:
                speaking = self._is_speaking
            silent_for = time.monotonic() - self._last_user_speech
            if not speaking and silent_for > 8.0:
                await asyncio.to_thread(gc.collect)

    # â”€â”€ Phone audio relay â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def _relay_phone_audio(self) -> None:
        """Forward phone mic PCM chunks from dashboard queue into the Gemini Live session."""
        q = self._dashboard._phone_audio_queue
        while True:
            try:
                chunk = await asyncio.wait_for(q.get(), timeout=1.0)
            except asyncio.TimeoutError:
                # No audio for 1 s â†’ phone mic inactive, give PC mic back
                self._phone_active = False
                continue
            self._phone_active = True   # phone is streaming â€” silence PC mic
            with self._speaking_lock:
                speaking = self._is_speaking
            if not speaking and not self.ui.muted:
                try:
                    self.out_queue.put_nowait(chunk)
                except asyncio.QueueFull:
                    pass

    def _on_phone_connected(self) -> None:
        self.ui.write_log("SYS: Phone connected via Remote Dashboard.")
        self.ui.notify_phone_connected()

    async def _on_dashboard_action(self, action: str, params: dict) -> dict:
        """Direct action execution from mobile dashboard buttons."""
        action = (action or "").strip().lower()
        self.ui.write_log(f"SYS: Mobile uplink action: [{action.upper()}]")
        try:
            if action == "screenshot":
                from actions.computer_control import computer_control
                res = await asyncio.to_thread(computer_control, {"action": "screenshot", "screenshot_mode": "both"}, player=self.ui)
                return {"ok": True, "result": res}

            elif action in ("audio_core", "audio_core_toggle", "audio_core_pause", "audio_core_play", "audio_core_volume", "audio_core_next", "audio_core_prev"):
                sub = params.get("subaction")
                if not sub:
                    if "toggle" in action or action == "audio_core":
                        sub = "toggle"
                    elif "pause" in action:
                        sub = "pause"
                    elif "play" in action:
                        sub = "resume"
                    elif "next" in action:
                        sub = "next"
                    elif "prev" in action:
                        sub = "prev"
                    else:
                        sub = "toggle"
                vol = params.get("volume")
                from actions.audio_core import audio_core
                res = await asyncio.to_thread(audio_core, {"action": sub, "volume_percent": vol}, player=self.ui)
                return {"ok": True, "result": res}

            elif action in ("spotify", "spotify_toggle", "spotify_pause", "spotify_play", "spotify_next", "spotify_prev"):
                sub = params.get("subaction")
                if not sub:
                    if "toggle" in action or action == "spotify":
                        sub = "toggle"
                    elif "pause" in action:
                        sub = "pause"
                    elif "play" in action:
                        sub = "resume"
                    elif "next" in action:
                        sub = "skip_next"
                    elif "prev" in action:
                        sub = "skip_previous"
                    else:
                        sub = "toggle"
                from actions.spotify_control import control_playback
                res = await asyncio.to_thread(control_playback, sub, player=self.ui)
                return {"ok": True, "result": res}

            elif action == "briefing":
                await self._dashboard._command_queue.put("deliver daily briefing")
                return {"ok": True, "result": "Briefing queued"}

            elif action == "system_status":
                from actions.system_monitor import get_system_status
                st = await asyncio.to_thread(get_system_status)
                if self._dashboard:
                    msg = (
                        f"CPU: {st.get('cpu_percent', 0)}% | "
                        f"RAM: {st.get('ram_used_gb', 0)}/{st.get('ram_total_gb', 0)} GB ({st.get('ram_percent', 0)}%) | "
                        f"Disk: {st.get('disk_percent', 0)}%"
                    )
                    asyncio.create_task(self._dashboard.broadcast({
                        "type": "telemetry",
                        "tag": "SYSTEM",
                        "icon": "status",
                        "text": msg,
                    }))
                return {"ok": True, "status": st}

            elif action == "interrupt":
                self.interrupt()
                if self._dashboard:
                    asyncio.create_task(self._dashboard.broadcast({
                        "type": "sys",
                        "text": "Execution interrupted by mobile operator.",
                    }))
                return {"ok": True, "result": "Interrupted"}

            elif action == "toggle_mute":
                self.ui.toggle_mute()
                return {"ok": True, "muted": self.ui.muted}

            elif action == "get_deck_state":
                core_st = self.ui.get_audio_core_status() if hasattr(self.ui, "get_audio_core_status") else {}
                return {
                    "ok": True,
                    "audio_core": core_st,
                    "muted": getattr(self.ui, "muted", False)
                }

            else:
                res = await self._dispatch_tool(action, params)
                return {"ok": True, "result": res}

        except Exception as e:
            return {"ok": False, "error": str(e)}

    # â”€â”€ dashboard command relay â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def _process_dashboard_commands(self) -> None:
        while True:
            try:
                text = await asyncio.wait_for(
                    self._dashboard._command_queue.get(), timeout=0.5
                )
                if not text:
                    continue
                # Wait up to 8s for session to become ready (or local mode queue ready)
                for _ in range(80):
                    if self.session or (self._is_local_mode and self._local_msg_queue is not None):
                        break
                    await asyncio.sleep(0.1)

                if self._wake_enabled and not self._awake:
                    self.wake(reason="remote command")

                if self.session:
                    await self.session.send_client_content(
                        turns={"role": "user", "parts": [{"text": text}]},
                        turn_complete=True,
                    )
                    self.ui.write_log(f"[Web]: {text}")
                    if self._dashboard:
                        asyncio.create_task(self._dashboard.broadcast({
                            "type": "log", "speaker": "user",
                            "text": text,
                            "ts": datetime.now().isoformat(),
                        }))
                elif self._is_local_mode and self._local_msg_queue is not None:
                    await self._local_msg_queue.put(text)
                    self.ui.write_log(f"[Web]: {text}")
                    if self._dashboard:
                        asyncio.create_task(self._dashboard.broadcast({
                            "type": "log", "speaker": "user",
                            "text": text,
                            "ts": datetime.now().isoformat(),
                        }))
                else:
                    print(f"[Dashboard] Dropped command (no session): {text}")
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                print(f"[Dashboard] Command error: {e}")
                await asyncio.sleep(0.5)

    def _speak_local(self, text: str):
        if not text or not text.strip() or self.ui.muted:
            return
        def _tts():
            try:
                import win32com.client
                voice = win32com.client.Dispatch("SAPI.SpVoice")
                clean = re.sub(r'[*_`#~]', '', text).strip()
                if clean:
                    voice.Speak(clean)
            except Exception:
                pass
        threading.Thread(target=_tts, daemon=True).start()

    async def run_local(self, provider: str = "ollama"):
        from core.llm_client import (
            call_llm_stream, call_llm_text, ensure_ollama_running,
            get_llm_settings, warmup_model
        )
        url, model = get_llm_settings()
        _tlog("ALFRED", "link", f"Local mode [{provider.upper()}] with model '{model}' at {url}", self._dashboard)
        self.ui.write_log(f"SYS: Initialising local intelligence ({provider.upper()} // {model})...")
        self.ui.set_state("THINKING")

        if provider == "ollama":
            ok = await asyncio.to_thread(ensure_ollama_running)
            if not ok:
                self.ui.write_log("WRN: Ollama server unreachable. Ensure 'ollama serve' is running.")
            else:
                self.ui.write_log(f"SYS: Ollama server connected at {url}.")
        elif provider == "openrouter":
            self.ui.write_log(f"SYS: OpenRouter frontier routing active ({model}).")
        else:
            self.ui.write_log(f"SYS: Local endpoint: {url} (model: {model}).")

        self.ui.set_state("LISTENING")
        self.ui.write_log(f"SYS: ALFRED online in [{provider.upper()}] mode. Ready for directives.")

        # Build tools declarations in OpenAI/Ollama compatible format
        system_instruction, _all_decls = self._build_system_instruction()
        local_tools = []
        for d in _all_decls:
            if not isinstance(d, dict) or not d.get("name"):
                continue
            name = d["name"]
            desc = d.get("description", "")
            params = d.get("parameters", {})
            props = {}
            for k, p in params.get("properties", {}).items():
                props[k] = {
                    "type": str(p.get("type", "string")).lower(),
                    "description": p.get("description", "")
                }
            local_tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": desc,
                    "parameters": {
                        "type": "object",
                        "properties": props,
                        "required": params.get("required", [])
                    }
                }
            })

        history: list[dict] = [{"role": "system", "content": system_instruction}]

        # Warm up prefix cache off-thread
        asyncio.to_thread(warmup_model, system_instruction)

        # Background system monitor tasks
        asyncio.create_task(self._run_system_monitor())
        asyncio.create_task(self._run_background_monitor())
        asyncio.create_task(self._run_gc_manager())

        while True:
            try:
                user_text = await self._local_msg_queue.get()
                if not user_text or not user_text.strip():
                    continue

                user_text = user_text.strip()
                if getattr(self, "monitor_controller", None) and self.monitor_controller.is_waiting_for_answer:
                    if self.monitor_controller.submit_answer(user_text):
                        self.ui.write_log(f"You (Answer): {user_text}")
                        continue
                self.ui.write_log(f"You: {user_text}")
                self.ui.set_state("THINKING")
                history.append({"role": "user", "content": user_text})

                import queue
                chunk_q = queue.Queue()

                def _stream_worker(hist, tools, q):
                    try:
                        for chunk in call_llm_stream(hist, tools=tools):
                            q.put(chunk)
                    except Exception as err:
                        q.put({"type": "error", "error": str(err)})

                t = threading.Thread(
                    target=_stream_worker,
                    args=(history, local_tools, chunk_q),
                    daemon=True
                )
                t.start()

                accumulated = []
                final_tool_calls = []
                full_reply = ""

                while True:
                    await asyncio.sleep(0.02)
                    drained_done = False
                    while not chunk_q.empty():
                        msg = chunk_q.get_nowait()
                        mtype = msg.get("type")
                        if mtype == "sentence":
                            stext = msg.get("text", "").strip()
                            if stext:
                                accumulated.append(stext)
                                self.ui.set_state("SPEAKING")
                                self.ui.write_log(f"ALFRED: {stext}")
                                if not self.ui.muted:
                                    self._speak_local(stext)
                        elif mtype == "done":
                            full_reply = msg.get("content", "")
                            final_tool_calls = msg.get("tool_calls", [])
                            drained_done = True
                            break
                        elif mtype == "error":
                            err_msg = msg.get("error", "Error")
                            self.ui.write_log(f"ERR: Local model error: {err_msg}")
                            drained_done = True
                            break

                    if drained_done:
                        break
                    if not t.is_alive() and chunk_q.empty():
                        break

                if full_reply and not accumulated:
                    self.ui.write_log(f"ALFRED: {full_reply}")
                    if not self.ui.muted:
                        self._speak_local(full_reply)

                if full_reply:
                    history.append({"role": "assistant", "content": full_reply})
                    if self._dashboard:
                        asyncio.create_task(self._dashboard.broadcast({
                            "type": "chat", "speaker": "alfred",
                            "text": full_reply,
                            "ts": datetime.now().isoformat(),
                        }))

                # Execute any tool calls requested by local model
                if final_tool_calls:
                    for tc in final_tool_calls:
                        fn = tc.get("function", {})
                        fn_name = fn.get("name", "")
                        fn_args = fn.get("arguments", {})
                        if isinstance(fn_args, str):
                            try:
                                fn_args = json.loads(fn_args)
                            except Exception:
                                fn_args = {}

                        self.ui.set_state("THINKING")
                        self.ui.write_log(f"SYS: Executing tool [{fn_name}]...")
                        tool_out = await self._dispatch_tool(fn_name, fn_args)
                        self.ui.write_log(f"SYS: Result: {str(tool_out)[:120]}")

                        # Ask model for final answer incorporating tool result
                        history.append({
                            "role": "user",
                            "content": f"[TOOL RESULT for {fn_name}]:\n{tool_out}\nBriefly answer the user with this information."
                        })
                        try:
                            synth = await asyncio.to_thread(
                                call_llm_text,
                                prompt=f"Tool {fn_name} returned:\n{tool_out}\nProvide a concise and helpful response to the user.",
                                system=system_instruction
                            )
                            if synth:
                                self.ui.set_state("SPEAKING")
                                self.ui.write_log(f"ALFRED: {synth}")
                                if not self.ui.muted:
                                    self._speak_local(synth)
                                history.append({"role": "assistant", "content": synth})
                                if self._dashboard:
                                    asyncio.create_task(self._dashboard.broadcast({
                                        "type": "chat", "speaker": "alfred",
                                        "text": synth,
                                        "ts": datetime.now().isoformat(),
                                    }))
                        except Exception as e:
                            _tlog("ALFRED", "warn", f"Synthesis error: {e}", self._dashboard)

                self.ui.set_state("LISTENING")

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.ui.write_log(f"ERR: {e}")
                self.ui.set_state("LISTENING")
                await asyncio.sleep(0.5)

    # â”€â”€ main loop â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def run(self):
        self._loop = asyncio.get_event_loop()
        self._local_msg_queue = asyncio.Queue()
        self._reconnect_event = asyncio.Event()

        # â”€â”€ Wire the shared core services to the interface â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        confirm_gate.bind(
            show = self.ui.show_confirm,
            hide = self.ui.hide_confirm,
            log  = self.ui.write_log,
        )
        set_trim_notifier(self.ui.write_log)

        audio_devices.configure(SEND_SAMPLE_RATE, RECEIVE_SAMPLE_RATE)
        def _audio_ready_cb():
            if self.ui and hasattr(self.ui, "set_audio_status"):
                self.ui.set_audio_status("READY")
        audio_devices.prefetch(on_ready=_audio_ready_cb)

        # Start dashboard (optional)
        try:
            from dashboard.server import DashboardServer
            self._dashboard = DashboardServer()
            self._dashboard._loop = self._loop
            self._dashboard.set_connect_callback(self._on_phone_connected)
            self._dashboard.set_clear_chat_callback(self._on_remote_clear_chat)
            self._dashboard.set_action_callback(self._on_dashboard_action)
            asyncio.create_task(self._dashboard.serve())
            asyncio.create_task(self._process_dashboard_commands())
        except Exception as e:
            print(f"[Dashboard] Disabled: {e}")
            self._dashboard = None

        if self._bg_worker_task is None or self._bg_worker_task.done():
            self._bg_worker_task = asyncio.create_task(self._background_worker())

        # Check provider: Gemini Live vs Local Model (Ollama / LM Studio)
        provider = "gemini"
        try:
            cfg = json.loads(open(API_CONFIG_PATH, "r", encoding="utf-8").read())
            provider = str(cfg.get("llm_provider", "gemini")).strip().lower()
        except Exception:
            pass

        if provider in ("ollama", "openai", "lmstudio", "local", "openrouter"):
            self._is_local_mode = True
            await self.run_local(provider)
            return

        while True:
            try:
                _tlog("ALFRED", "link", "Connecting...", self._dashboard)
                self.ui.set_state("INITIALISING")
                _resumed_with = self._resume_handle is not None
                config = self._build_config()

                # Fresh client on every reconnect â€” avoids stale HTTP session state
                # v1alpha carries proactive audio; if it gets rejected we fall
                # back to v1beta.
                client = genai.Client(
                    api_key=_get_api_key(),
                    http_options={"api_version": "v1alpha" if self._enhanced_live else "v1beta"}
                )

                async with (
                    client.aio.live.connect(model=LIVE_MODEL, config=config) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session          = session
                    self.audio_in_queue   = asyncio.Queue()
                    self.out_queue        = asyncio.Queue(maxsize=200)
                    self._turn_done_event = asyncio.Event()

                    # Reset transient state that must not carry over from a previous session
                    self._pending_vision       = None
                    self._vision_cam_active    = False
                    self._vision_close_pending = False
                    self._vision_busy          = False
                    self._vision_last_time     = 0.0
                    self._interrupted          = False

                    _tlog("ALFRED", "online", "Connected.", self._dashboard)
                    if _resumed_with:
                        # Say it plainly: the difference between "it reconnected"
                        # and "it reconnected and still knows what we were doing"
                        # is the whole point, and it is invisible otherwise.
                        self.ui.write_log("SYS: Reconnected â€” conversation restored.")

                    # Wake word: if enabled, come up ASLEEP (mic gated, silent)
                    # until the user says "Hey Alfred" or taps wake in the UI.
                    if self._wake_enabled:
                        self._ensure_wake_detector()
                        self._awake = False
                        self.ui.set_state("SLEEPING")
                        self.ui.write_log(
                            f"SYS: ALFRED online â€” sleeping. Say '{WAKE_PHRASE}' to wake me."
                        )
                    else:
                        self._awake = True
                        self.ui.set_state("LISTENING")
                        self.ui.write_log("SYS: ALFRED online.")

                    if self._dashboard:
                        await self._dashboard.broadcast({"type": "status", "state": "active"})

                    self._reconnect_event.clear()  # ignore requests from before this session
                    tg.create_task(self._watch_reconnect())
                    tg.create_task(self._send_realtime())
                    tg.create_task(self._listen_audio())
                    tg.create_task(self._receive_audio())
                    tg.create_task(self._play_audio())
                    tg.create_task(self._run_system_monitor())
                    tg.create_task(self._run_background_monitor())
                    tg.create_task(self._run_proactive_mode())
                    tg.create_task(self._run_sleep_watch())
                    tg.create_task(self._run_gc_manager())
                    if self._dashboard:
                        tg.create_task(self._relay_phone_audio())

                    # Morning briefing â€” fires once per process launch (if enabled).
                    # Skipped in wake-word mode: it comes up asleep, and a briefing
                    # would mean talking while "asleep".
                    if not self._briefing_sent and get_brief_enabled() and self._awake:
                        self._briefing_sent = True
                        tg.create_task(self._send_startup_briefing())

            except KeyboardInterrupt:
                raise
            except SystemExit:
                raise
            except BaseException as e:
                # Catches both Exception and BaseExceptionGroup (Python 3.11+
                # TaskGroup raises BaseExceptionGroup when tasks are cancelled
                # externally, which `except Exception` would miss, letting the
                # exception escape the while-loop and causing asyncio.run() to
                # start shutdown â€” resulting in "executor after shutdown" errors).
                # Voluntary reconnect (voice change) â€” not an error. Rebuild the
                # session immediately with no backoff and no scary logs.
                if _is_reconnect_signal(e):
                    _tlog("ALFRED", "link", "Voluntary reconnect requested.", self._dashboard)
                    if not _keep_context_of(e):
                        # A deliberate clean slate (voice change) â€” drop the
                        # handle so the next connect really does start empty.
                        self._resume_handle = None
                    self._conn_backoff = 0
                    continue

                # A resumption handle the server will not accept â€” expired, or
                # belonging to a session it has since dropped. Without this, the
                # same dead handle would be replayed on every retry and the
                # assistant would never come back at all: the feature meant to
                # survive a reconnect would be the thing preventing one. Drop it
                # once and let the next attempt start clean.
                if _resumed_with and (
                    "resum" in str(e).lower()
                    or "handle" in str(e).lower()
                    or "INVALID_ARGUMENT" in str(e)
                    or "NOT_FOUND" in str(e)
                ):
                    _tlog("ALFRED", "warn", "Resumption handle rejected â€” starting a fresh session", self._dashboard)
                    self.ui.write_log("SYS: Could not restore the conversation â€” starting fresh.")
                    self._resume_handle = None
                    self._conn_backoff = 0
                    continue

                err_str = str(e)
                _tlog("ALFRED", "error", f"Error ({type(e).__name__}): {e}", self._dashboard)
                traceback.print_exc()

                # Turn-taking / media / thinking knobs rejected by the server
                # (preview API drift) â€” drop them first, because they are the
                # newest fields and the cheapest to lose. Proactive audio is
                # tried again on the next pass if the error persists.
                if self._tuned_live and (
                    "INVALID_ARGUMENT" in err_str
                    or "Unknown name" in err_str
                    or "unexpected keyword" in err_str
                    or "realtime_input" in err_str.lower()
                    or "media_resolution" in err_str.lower()
                    or "thinking" in err_str.lower()
                ):
                    self._tuned_live = False
                    _tlog("ALFRED", "warn", "Live tuning rejected â€” reconnecting without it.", self._dashboard)
                    continue

                # Proactive audio rejected by the server (preview API drift) â€”
                # drop it and reconnect with the plain config.
                if self._enhanced_live and (
                    "INVALID_ARGUMENT" in err_str
                    or "proactiv" in err_str.lower()
                    or "Unknown name" in err_str
                    or "unexpected keyword" in err_str
                ):
                    self._enhanced_live = False
                    self.ui.write_log(
                        "SYS: Proactive audio unavailable â€” reconnecting without it."
                    )
                    continue

                # Invalid API key â€” stop hammering the API
                if "API key not valid" in err_str or "1007" in err_str:
                    self.ui.write_log("ERR: API key invalid â€” update key in Alfred Settings [ âš™ ] or choose local mode.")
                    self.ui.set_state("SLEEPING")
                    # If config already has an API key configured, don't force setup overlay;
                    # allow user to update via Settings button when ready.
                    has_cfg_key = False
                    try:
                        cfg = json.loads(open(API_CONFIG_PATH, "r", encoding="utf-8").read())
                        has_cfg_key = bool(cfg.get("gemini_api_key") or cfg.get("GEMINI_API_KEY") or cfg.get("api_key"))
                    except Exception:
                        pass
                    if not has_cfg_key:
                        self.ui.prompt_reconfig()
                        while not self.ui._win._ready:
                            await asyncio.sleep(1)
                    else:
                        await asyncio.sleep(10)

                    # Check if user switched to a local offline backend (Ollama / LM Studio) or updated key
                    try:
                        cfg = json.loads(open(API_CONFIG_PATH, "r", encoding="utf-8").read())
                        new_prov = str(cfg.get("llm_provider", "gemini")).strip().lower()
                        if new_prov in ("ollama", "openai", "lmstudio", "local", "openrouter"):
                            self._is_local_mode = True
                            await self.run_local(new_prov)
                            return
                    except Exception:
                        pass
                    _tlog("ALFRED", "link", "Reconnecting...", self._dashboard)
                    _conn_backoff = 3
                    continue

                # Network / timeout errors â€” log clearly and back off
                is_net_err = any(k in err_str for k in (
                    "TimeoutError", "timed out", "getaddrinfo", "CancelledError",
                    "ConnectionRefusedError", "OSError", "Cannot connect",
                ))
                if is_net_err:
                    _conn_backoff = min(getattr(self, "_conn_backoff", 3) * 2, 60)
                    self._conn_backoff = _conn_backoff
                    self.ui.write_log(
                        f"NET: Connection failed â€” retrying in {_conn_backoff}s. "
                        "(a VPN may be required)"
                    )
                else:
                    self._conn_backoff = 3
            finally:
                self.session = None
                # Only save if there was a real conversation (â‰¥3 turns)
                if len(self._session_log) >= 3:
                    asyncio.create_task(self._save_session_summary())

            self.set_speaking(False)
            self.ui.set_state("SLEEPING")

            if self._dashboard:
                await self._dashboard.broadcast({"type": "status", "state": "sleeping"})

            delay = getattr(self, "_conn_backoff", 3)
            _tlog("ALFRED", "link", f"Reconnecting in {delay}s...", self._dashboard)
            await asyncio.sleep(delay)

def main():
    ui = JarvisUI("face.png")

    def runner():
        ui.wait_for_api_key()
        alfred = JarvisLive(ui)
        try:
            asyncio.run(alfred.run())
        except KeyboardInterrupt:
            _tlog("ALFRED", "halt", "Shutting down...")
        finally:
            alfred._screen_monitor.stop(wait=False)

    threading.Thread(target=runner, daemon=True).start()
    ui.root.mainloop()

if __name__ == "__main__":
    main()
