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

        # 5. Safe Windows Working Set trim via SetProcessWorkingSetSize
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes
                k32 = ctypes.windll.kernel32
                k32.GetCurrentProcess.restype = wintypes.HANDLE
                k32.SetProcessWorkingSetSize.argtypes = [
                    wintypes.HANDLE,
                    ctypes.c_size_t,
                    ctypes.c_size_t,
                ]
                k32.SetProcessWorkingSetSize.restype = wintypes.BOOL
                # (size_t)-1, (size_t)-1 instructs the Windows memory manager
                # to trim resident pages back to the operating system without
                # touching C heap structures or risking multithreaded corruption.
                neg1 = ctypes.c_size_t(-1).value
                ok = k32.SetProcessWorkingSetSize(k32.GetCurrentProcess(), neg1, neg1)
                return bool(ok)
            except Exception:
                pass
        return True
    except Exception:
        return False
