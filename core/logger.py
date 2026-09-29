"""core/logger.py — Centralized, thread-safe monotonic and wall-clock timestamped logger for ALFRED."""

import builtins
import json
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

# Module-level monotonic start time
_T0 = time.monotonic()
_print_lock = threading.Lock()
_orig_print = builtins.print
_installed = False


def _is_debug_timestamps_enabled() -> bool:
    """Read 'debug_timestamps' toggle from config/api_keys.json."""
    try:
        cfg_path = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            return bool(cfg.get("debug_timestamps", True))
    except Exception:
        pass
    return True


_DEBUG_TIMESTAMPS = _is_debug_timestamps_enabled()


def format_timestamp(now_wall: float, now_mono: float) -> str:
    """Format combined absolute and monotonic timestamp.

    Example: [15:42:07.318 | +00:03.412]
    """
    dt = datetime.fromtimestamp(now_wall)
    wall_str = dt.strftime("%H:%M:%S.") + f"{int(dt.microsecond / 1000):03d}"

    elapsed = max(0.0, now_mono - _T0)
    mins = int(elapsed // 60)
    secs = int(elapsed % 60)
    msecs = int((elapsed - int(elapsed)) * 1000)
    return f"[{wall_str} | +{mins:02d}:{secs:02d}.{msecs:03d}]"


def ts_print(*args, **kwargs):
    """Drop-in thread-safe print replacement with monotonic timestamp prefix."""
    if not _DEBUG_TIMESTAMPS:
        with _print_lock:
            _orig_print(*args, **kwargs)
        return

    # Check target stream
    target_file = kwargs.get("file", sys.stdout)
    if target_file not in (sys.stdout, sys.stderr, None):
        with _print_lock:
            _orig_print(*args, **kwargs)
        return

    now_wall = time.time()
    now_mono = time.monotonic()
    prefix = format_timestamp(now_wall, now_mono)

    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    flush = kwargs.get("flush", False)

    content = sep.join(str(a) for a in args)
    if not content.strip():
        with _print_lock:
            _orig_print(content, end=end, file=target_file, flush=flush)
        return

    lines = content.splitlines()

    with _print_lock:
        for i, line in enumerate(lines):
            line_end = end if i == len(lines) - 1 else "\n"
            if line.strip():
                _orig_print(f"{prefix} {line}", end=line_end, file=target_file, flush=flush)
            else:
                _orig_print(line, end=line_end, file=target_file, flush=flush)


def install_timestamped_logging() -> None:
    """Install the timestamped print hook into builtins once."""
    global _installed, _DEBUG_TIMESTAMPS
    if _installed:
        return
    _DEBUG_TIMESTAMPS = _is_debug_timestamps_enabled()
    builtins.print = ts_print
    _installed = True
