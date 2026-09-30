"""
Process-level Audio Ducking for ALFRED.

Automatically ducks background media applications (Spotify, Chrome, VLC, Edge, etc.)
by a configured factor (default: 70% reduction -> volume_factor=0.3) when ALFRED
speaks, and restores their original volumes when speech ends or is interrupted.
"""

from __future__ import annotations

import logging
import os
import platform
import sys
import threading
from typing import Dict, Optional

logger = logging.getLogger("audio_ducker")

# Default target media processes (case-insensitive)
# Default target media processes (case-insensitive)
DEFAULT_MEDIA_PROCESSES = {
    "spotify.exe",
    "chrome.exe",
    "vlc.exe",
    "msedge.exe",
    "brave.exe",
    "firefox.exe",
    "opera.exe",
    "discord.exe",
    "wmplayer.exe",
    "musicbee.exe",
    "itunes.exe",
    "tidal.exe",
    "foobar2000.exe",
    "mpv.exe",
    "potplayer.exe",
    "potplayermini64.exe",
    "kmplayer.exe",
    "aimp.exe",
    "audacity.exe",
    "netflix.exe",
    "steam.exe",
    "vivaldi.exe",
    "arc.exe",
    "thorium.exe",
    "zen.exe",
    "waterfox.exe",
    "chromium.exe",
    "apple music.exe",
    # Linux common process names (without .exe)
    "spotify",
    "chrome",
    "vlc",
    "msedge",
    "brave",
    "firefox",
    "opera",
    "discord",
    "mpv",
    "chromium",
}

_duck_lock = threading.Lock()
# Maps PID -> original volume (float 0.0 - 1.0)
_original_volumes: Dict[int, float] = {}
_is_ducked = False

# Watchdog to guarantee ducked apps are NEVER stuck ducked permanently
_watchdog_timer: Optional[threading.Timer] = None
_watchdog_lock = threading.Lock()


def _cancel_auto_unduck_watchdog() -> None:
    global _watchdog_timer
    with _watchdog_lock:
        if _watchdog_timer:
            _watchdog_timer.cancel()
            _watchdog_timer = None


def _schedule_auto_unduck_watchdog(timeout_s: float = 30.0) -> None:
    global _watchdog_timer
    with _watchdog_lock:
        if _watchdog_timer:
            _watchdog_timer.cancel()
        _watchdog_timer = threading.Timer(timeout_s, _on_watchdog_timeout)
        _watchdog_timer.daemon = True
        _watchdog_timer.start()


def _on_watchdog_timeout() -> None:
    logger.warning("Audio ducker watchdog timeout: auto-restoring external media app volume levels.")
    unduck_media_apps(sync=True)


def _duck_windows(volume_factor: float, targets: set[str]) -> dict[str, float]:
    """Execute ducking on Windows via pycaw with resilient session inspection."""
    global _is_ducked
    ducked_apps: dict[str, float] = {}
    current_pid = os.getpid()

    try:
        import comtypes
        comtypes.CoInitialize()
    except Exception:
        pass

    try:
        from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume

        sessions = AudioUtilities.GetAllSessions()
        for session in sessions:
            try:
                proc = session.Process
            except Exception:
                proc = None

            pid = None
            raw_pid = getattr(session, "ProcessId", None)
            if isinstance(raw_pid, int):
                pid = raw_pid
            elif proc and isinstance(getattr(proc, "pid", None), int):
                pid = proc.pid

            # Constraint: Do not affect ALFRED's own process audio or invalid PIDs
            if not pid or pid == current_pid:
                continue

            pname = ""
            if proc:
                try:
                    pname = proc.name().lower()
                except Exception:
                    pass
            if not pname and pid:
                try:
                    import psutil
                    pname = psutil.Process(pid).name().lower()
                except Exception:
                    pass

            if pname in targets or "*" in targets or "all" in targets:
                try:
                    vol_ctrl = None
                    if hasattr(session, "_ctl") and hasattr(session._ctl, "QueryInterface"):
                        try:
                            vol_ctrl = session._ctl.QueryInterface(ISimpleAudioVolume)
                        except Exception:
                            vol_ctrl = None
                    if vol_ctrl is None:
                        vol_ctrl = getattr(session, "SimpleAudioVolume", None)

                    if vol_ctrl is not None:
                        cur_vol = float(vol_ctrl.GetMasterVolume())

                        # Record original volume only if not already recorded
                        if pid not in _original_volumes:
                            _original_volumes[pid] = cur_vol

                        target_vol = max(0.0, min(1.0, _original_volumes[pid] * volume_factor))
                        vol_ctrl.SetMasterVolume(target_vol, None)
                        ducked_apps[pname or str(pid)] = target_vol
                except Exception as e:
                    logger.debug(f"Failed to duck session {pname} (PID {pid}): {e}")

        if ducked_apps or _original_volumes:
            _is_ducked = True
            _schedule_auto_unduck_watchdog(timeout_s=30.0)
    except Exception as e:
        logger.debug(f"Windows pycaw audio ducking error: {e}")
    finally:
        try:
            import comtypes
            comtypes.CoUninitialize()
        except Exception:
            pass

    return ducked_apps


def _unduck_windows(targets: set[str]) -> dict[str, float]:
    """Execute unducking on Windows via pycaw, restoring exact prior volume levels."""
    global _is_ducked
    restored_apps: dict[str, float] = {}

    if not _original_volumes:
        _is_ducked = False
        _cancel_auto_unduck_watchdog()
        return restored_apps

    try:
        import comtypes
        comtypes.CoInitialize()
    except Exception:
        pass

    try:
        from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume

        sessions = AudioUtilities.GetAllSessions()
        restored_pids = set()

        for session in sessions:
            try:
                proc = session.Process
            except Exception:
                proc = None

            pid = None
            raw_pid = getattr(session, "ProcessId", None)
            if isinstance(raw_pid, int):
                pid = raw_pid
            elif proc and isinstance(getattr(proc, "pid", None), int):
                pid = proc.pid

            if not pid:
                continue

            pname = ""
            if proc:
                try:
                    pname = proc.name().lower()
                except Exception:
                    pass
            if not pname and pid:
                try:
                    import psutil
                    pname = psutil.Process(pid).name().lower()
                except Exception:
                    pass

            if pid in _original_volumes:
                try:
                    orig_vol = _original_volumes[pid]
                    vol_ctrl = None
                    if hasattr(session, "_ctl") and hasattr(session._ctl, "QueryInterface"):
                        try:
                            vol_ctrl = session._ctl.QueryInterface(ISimpleAudioVolume)
                        except Exception:
                            vol_ctrl = None
                    if vol_ctrl is None:
                        vol_ctrl = getattr(session, "SimpleAudioVolume", None)

                    if vol_ctrl is not None:
                        vol_ctrl.SetMasterVolume(orig_vol, None)
                        restored_apps[pname or str(pid)] = orig_vol
                        restored_pids.add(pid)
                except Exception as e:
                    logger.debug(f"Failed to restore volume for {pname} (PID {pid}): {e}")

        # Remove restored sessions from original volumes tracking
        for pid in restored_pids:
            _original_volumes.pop(pid, None)

        # Also purge any PIDs whose processes have exited in the meantime
        try:
            import psutil
            stale_pids = [p for p in _original_volumes if not psutil.pid_exists(p)]
            for p in stale_pids:
                _original_volumes.pop(p, None)
        except Exception:
            pass

        # Clear tracking if everything restored or no active sessions remain
        if not _original_volumes or len(restored_apps) > 0:
            _original_volumes.clear()
            _is_ducked = False
            _cancel_auto_unduck_watchdog()
    except Exception as e:
        logger.debug(f"Windows pycaw audio unducking error: {e}")
        # On error, if all or most were handled, ensure we don't leave ducked state permanently
        if not _original_volumes:
            _is_ducked = False
            _cancel_auto_unduck_watchdog()
    finally:
        try:
            import comtypes
            comtypes.CoUninitialize()
        except Exception:
            pass

    return restored_apps


def _duck_linux(volume_factor: float, targets: set[str]) -> dict[str, float]:
    """Execute ducking on Linux via pulsectl."""
    global _is_ducked
    ducked_apps: dict[str, float] = {}
    current_pid = os.getpid()

    try:
        import pulsectl
        with pulsectl.Pulse("alfred-ducker") as pulse:
            for sink_input in pulse.sink_input_list():
                pname = (sink_input.proplist.get("application.process.binary") or
                         sink_input.proplist.get("application.name") or "").lower()
                pid_str = sink_input.proplist.get("application.process.id")
                try:
                    pid = int(pid_str) if pid_str else sink_input.index
                except Exception:
                    pid = sink_input.index

                if pid == current_pid:
                    continue

                if pname in targets or "*" in targets or "all" in targets:
                    cur_vol = sink_input.volume.value_flat
                    if pid not in _original_volumes:
                        _original_volumes[pid] = cur_vol

                    target_vol = max(0.0, min(1.0, _original_volumes[pid] * volume_factor))
                    pulse.volume_set_all_flat(sink_input, target_vol)
                    ducked_apps[pname or str(pid)] = target_vol

            if ducked_apps or _original_volumes:
                _is_ducked = True
                _schedule_auto_unduck_watchdog(timeout_s=30.0)
    except Exception as e:
        logger.debug(f"Linux pulsectl audio ducking error: {e}")

    return ducked_apps


def _unduck_linux(targets: set[str]) -> dict[str, float]:
    """Execute unducking on Linux via pulsectl."""
    global _is_ducked
    restored_apps: dict[str, float] = {}

    if not _original_volumes:
        _is_ducked = False
        _cancel_auto_unduck_watchdog()
        return restored_apps

    try:
        import pulsectl
        with pulsectl.Pulse("alfred-ducker") as pulse:
            for sink_input in pulse.sink_input_list():
                pname = (sink_input.proplist.get("application.process.binary") or
                         sink_input.proplist.get("application.name") or "").lower()
                pid_str = sink_input.proplist.get("application.process.id")
                try:
                    pid = int(pid_str) if pid_str else sink_input.index
                except Exception:
                    pid = sink_input.index

                if pid in _original_volumes:
                    orig_vol = _original_volumes[pid]
                    pulse.volume_set_all_flat(sink_input, orig_vol)
                    restored_apps[pname or str(pid)] = orig_vol

            _original_volumes.clear()
            _is_ducked = False
            _cancel_auto_unduck_watchdog()
    except Exception as e:
        logger.debug(f"Linux pulsectl audio unducking error: {e}")

    return restored_apps


def duck_media_apps(
    volume_factor: float = 0.3,
    targets: Optional[set[str]] = None,
    sync: bool = False,
) -> dict[str, float]:
    """
    Lower external media application volume (by default to 30%, i.e. ducking by 70%).

    :param volume_factor: Remaining volume fraction (0.3 = duck by 70%).
    :param targets: Set of process names to target (e.g. spotify.exe, chrome.exe).
    :param sync: If False (default), run in a background daemon thread to avoid blocking audio stream.
    :return: Dict of {process_name: new_volume}.
    """
    target_names = {t.lower() for t in (targets or DEFAULT_MEDIA_PROCESSES)}

    def _worker():
        with _duck_lock:
            sys_name = platform.system()
            if sys_name == "Windows":
                return _duck_windows(volume_factor, target_names)
            elif sys_name == "Linux":
                return _duck_linux(volume_factor, target_names)
            return {}

    if sync:
        return _worker()
    else:
        threading.Thread(target=_worker, daemon=True, name="alfred-audio-duck").start()
        return {}


def unduck_media_apps(
    targets: Optional[set[str]] = None,
    sync: bool = False,
) -> dict[str, float]:
    """
    Restore ducked media applications to their exact original volume levels.

    :param targets: Set of process names to target.
    :param sync: If False (default), run in a background daemon thread to avoid blocking audio stream.
    :return: Dict of {process_name: restored_volume}.
    """
    target_names = {t.lower() for t in (targets or DEFAULT_MEDIA_PROCESSES)}

    def _worker():
        with _duck_lock:
            sys_name = platform.system()
            if sys_name == "Windows":
                return _unduck_windows(target_names)
            elif sys_name == "Linux":
                return _unduck_linux(target_names)
            return {}

    if sync:
        return _worker()
    else:
        threading.Thread(target=_worker, daemon=True, name="alfred-audio-unduck").start()
        return {}


def is_ducked() -> bool:
    """Return whether media ducking is currently active."""
    return _is_ducked

