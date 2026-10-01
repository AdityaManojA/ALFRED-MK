"""
core/memory_trimmer.py — Windows working set trimming and Python garbage collection helper.
"""
from __future__ import annotations

import gc
import sys


def get_process_memory_mb() -> dict[str, float]:
    """Return dictionary with current process RSS, VMS, and Private working set in MB."""
    try:
        import psutil
        p = psutil.Process()
        mem = p.memory_info()
        return {
            "rss": round(mem.rss / 1048576, 2),
            "vms": round(mem.vms / 1048576, 2),
            "private": round(getattr(mem, "private", 0) / 1048576, 2),
        }
    except Exception:
        return {"rss": 0.0, "vms": 0.0, "private": 0.0}


def trim_process_memory() -> bool:
    """
    Comprehensive memory trim for idle/sleep states:
    1. Full generational garbage collection (gen 0, 1, 2)
    2. Purges internal string/regex/line caches
    3. Clears PyQt6 pixmap cache if GUI is loaded
    4. Clears PyTorch CUDA cache if loaded
    5. Compacts C-runtime CRT heaps via _heapmin()
    6. Trims Windows process working set (RSS) back to OS
    """
    try:
        # 1. Full cyclic GC across all generations
        gc.collect()

        # 2. Clear Python runtime standard caches
        try:
            import linecache
            linecache.clearcache()
        except Exception:
            pass

        try:
            import re
            re.purge()
        except Exception:
            pass

        # 3. Clear PyQt6 global pixmap cache if GUI module is active
        if "PyQt6.QtGui" in sys.modules:
            try:
                from PyQt6.QtGui import QPixmapCache
                QPixmapCache.clear()
            except Exception:
                pass

        # 4. PyTorch memory cache purge if active
        if "torch" in sys.modules:
            try:
                import torch
                if hasattr(torch, "cuda") and torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass

        # 5. Windows CRT heap compaction & Working Set trim
        if sys.platform == "win32":
            import ctypes
            try:
                if hasattr(ctypes.cdll, "msvcrt"):
                    ctypes.cdll.msvcrt._heapmin()
            except Exception:
                pass
            try:
                ctypes.CDLL("ucrtbase.dll")._heapmin()
            except Exception:
                pass

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
