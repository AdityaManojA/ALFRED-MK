"""Launch ALFRED with low-overhead Qt stall diagnostics.

Usage:
    py tools/profile_alfred_ui.py
    py tools/profile_alfred_ui.py --cpu-profile
"""
from __future__ import annotations

import argparse
import cProfile
import faulthandler
import io
import os
import pstats
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class ProbeLog:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._file = path.open("a", encoding="utf-8", buffering=1)
        self._lock = threading.Lock()

    @property
    def file(self):
        return self._file

    def write(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        line = f"[{stamp}] {message}"
        with self._lock:
            print(line, flush=True)
            self._file.write(line + "\n")

    def close(self) -> None:
        with self._lock:
            self._file.close()


def _runtime_snapshot() -> str:
    try:
        import psutil

        process = psutil.Process()
        return (
            f"cpu={process.cpu_percent(interval=None):.1f}% "
            f"rss={process.memory_info().rss / (1024 * 1024):.1f}MB "
            f"threads={process.num_threads()}"
        )
    except Exception:
        return f"python_threads={threading.active_count()}"


def _timed_slot(log: ProbeLog, label: str, fn: Callable):
    def wrapped(*args, **kwargs):
        started = time.perf_counter()
        log.write(f"BEGIN {label}")
        try:
            return fn(*args, **kwargs)
        finally:
            elapsed = (time.perf_counter() - started) * 1000.0
            log.write(f"END   {label} elapsed={elapsed:.1f}ms")

    wrapped.__name__ = getattr(fn, "__name__", label)
    wrapped.__doc__ = getattr(fn, "__doc__", None)
    return wrapped


def _install_probes(log: ProbeLog, stall_ms: float) -> None:
    from PyQt6.QtCore import QTimer

    import ui

    for name in (
        "_toggle_drawer",
        "_open_customize",
        "_show_setup",
        "_open_api_setup",
        "_open_plugin_manager",
        "_open_plugin_settings",
        "_open_audio_devices",
        "_open_memory_panel",
    ):
        original = getattr(ui.MainWindow, name, None)
        if original is not None:
            setattr(ui.MainWindow, name, _timed_slot(log, f"MainWindow.{name}", original))

    original_init = ui.MainWindow.__init__

    def instrumented_init(window, *args, **kwargs):
        original_init(window, *args, **kwargs)

        heartbeat = {"at": time.perf_counter(), "episode": 0, "running": True}
        timer = QTimer(window)

        def pulse() -> None:
            now = time.perf_counter()
            gap_ms = (now - heartbeat["at"]) * 1000.0
            heartbeat["at"] = now
            if gap_ms >= stall_ms:
                log.write(f"QT RECOVERED gap={gap_ms:.1f}ms {_runtime_snapshot()}")

        timer.timeout.connect(pulse)
        timer.start(20)
        window._perf_probe_timer = timer

        def watchdog() -> None:
            in_stall = False
            while heartbeat["running"]:
                age_ms = (time.perf_counter() - heartbeat["at"]) * 1000.0
                if age_ms >= stall_ms and not in_stall:
                    in_stall = True
                    heartbeat["episode"] += 1
                    log.write(f"QT STALL detected age={age_ms:.1f}ms {_runtime_snapshot()}")
                    log.write("STACKS follow in the probe log")
                    faulthandler.dump_traceback(file=log.file, all_threads=True)
                    log.file.flush()
                elif age_ms < stall_ms:
                    in_stall = False
                time.sleep(0.025)

        thread = threading.Thread(target=watchdog, daemon=True, name="alfred-ui-stall-watchdog")
        thread.start()
        window._perf_probe_heartbeat = heartbeat
        window._perf_probe_thread = thread
        log.write(f"Qt stall watchdog armed threshold={stall_ms:.0f}ms")

    ui.MainWindow.__init__ = instrumented_init


def _stop_probes() -> None:
    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        windows = app.topLevelWidgets() if app is not None else []
        for window in windows:
            heartbeat = getattr(window, "_perf_probe_heartbeat", None)
            if heartbeat is not None:
                heartbeat["running"] = False
            thread = getattr(window, "_perf_probe_thread", None)
            if thread is not None:
                thread.join(timeout=0.2)
    except Exception:
        pass


def _write_profile(profile: cProfile.Profile, output_dir: Path, run_id: str) -> None:
    raw_path = output_dir / f"alfred-ui-{run_id}.prof"
    report_path = output_dir / f"alfred-ui-{run_id}-profile.txt"
    profile.dump_stats(raw_path)

    report = io.StringIO()
    report.write("TOP 80 BY CUMULATIVE TIME\n")
    pstats.Stats(profile, stream=report).strip_dirs().sort_stats("cumulative").print_stats(80)
    report.write("\nTOP 80 BY INTERNAL TIME\n")
    pstats.Stats(profile, stream=report).strip_dirs().sort_stats("tottime").print_stats(80)
    report_path.write_text(report.getvalue(), encoding="utf-8")
    print(f"CPU profile: {raw_path}")
    print(f"Profile report: {report_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ALFRED while logging Qt stalls and slow settings callbacks.")
    parser.add_argument("--stall-ms", type=float, default=80.0)
    parser.add_argument("--cpu-profile", action="store_true")
    args = parser.parse_args()

    os.chdir(ROOT)
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = ROOT / "logs" / "perf"
    output_dir.mkdir(parents=True, exist_ok=True)
    log = ProbeLog(output_dir / f"alfred-ui-{run_id}-stalls.log")
    faulthandler.enable(file=log.file, all_threads=True)

    log.write(f"Performance run started cwd={ROOT}")
    log.write("Reproduce the freeze, wait two seconds, then close ALFRED normally.")
    _install_probes(log, max(40.0, args.stall_ms))

    import main as alfred_main

    profile = cProfile.Profile() if args.cpu_profile else None
    try:
        if profile is not None:
            profile.enable()
        alfred_main.main()
    finally:
        if profile is not None:
            profile.disable()
            _write_profile(profile, output_dir, run_id)
        _stop_probes()
        log.write(f"Performance run finished log={log.path}")
        faulthandler.disable()
        log.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
