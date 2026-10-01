"""
core/memory_trimmer.py — Windows working set trimming and Python garbage collection helper.
"""
from __future__ import annotations

import gc
import sys


def trim_process_memory() -> bool:
    """Collect Python garbage and trim Windows working set to release physical RAM back to OS."""
    try:
        gc.collect(generation=1)
        if sys.platform == "win32":
            import ctypes
            k32 = ctypes.windll.kernel32
            psapi = ctypes.windll.psapi
            pid = k32.GetCurrentProcessId()
            # PROCESS_SET_QUOTA (0x0100) | PROCESS_QUERY_INFORMATION (0x0400) = 0x0500
            h_proc = k32.OpenProcess(0x0500, False, pid)
            if h_proc:
                ok = psapi.EmptyWorkingSet(h_proc)
                k32.CloseHandle(h_proc)
                return bool(ok)
        return True
    except Exception:
        return False
