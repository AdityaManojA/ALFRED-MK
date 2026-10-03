"""
core/hud/visuals/base.py — Base abstractions, signals struct, guard watchdog,
and precomputed fast trig lookup table.
"""
from __future__ import annotations

import math
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Tuple

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QPainter

from core.ui.themes.schema import PaletteDefinition

# ── Performance & Safety Constants ───────────────────────────────────────────
TRIG_STEPS: int = 512
_TWO_PI: float = 2.0 * math.pi
_STEP_INV: float = TRIG_STEPS / _TWO_PI

# Precomputed sine & cosine table (zero-allocation fast trig during tick)
_SIN_TABLE: tuple[float, ...] = tuple(math.sin(i * _TWO_PI / TRIG_STEPS) for i in range(TRIG_STEPS))
_COS_TABLE: tuple[float, ...] = tuple(math.cos(i * _TWO_PI / TRIG_STEPS) for i in range(TRIG_STEPS))


def fast_sin(rad: float) -> float:
    """Precomputed sin lookup with zero allocation."""
    idx = int(rad * _STEP_INV) % TRIG_STEPS
    return _SIN_TABLE[idx]


def fast_cos(rad: float) -> float:
    """Precomputed cos lookup with zero allocation."""
    idx = int(rad * _STEP_INV) % TRIG_STEPS
    return _COS_TABLE[idx]


# ── Watchdog & Performance Constants ─────────────────────────────────────────
VISUAL_MAX_ERRORS: int = 3
SLOT_PAINT_BUDGET_MS: float = 3.5
BUDGET_WINDOW_FRAMES: int = 60
THEME_FADE_MS: int = 400
ALLOC_TOLERANCE_BYTES: int = 2048
LOD_HIGH: str = "HIGH"
LOD_LOW: str = "LOW"


@dataclass(frozen=True)
class HudSignals:
    """
    Read-only signals struct refreshed <= 2 Hz and shared by all slots.
    Visuals are strictly data-driven by this snapshot.
    """
    cpu_pct: float = 0.0
    mem_pct: float = 0.0
    net_kbps: float = 0.0
    disk_pct: float = 0.0
    proc_count: int = 0
    mic_level: float = 0.0
    sys_audio_level: float = 0.0
    monitor_active: bool = False
    focus_state: str = "IDLE"  # "IDLE" | "ON_TARGET" | "DRIFTING" | "PAUSED"
    drift: float = 0.0
    alert_level: int = 0  # 0 to 3


class SlotVisual(ABC):
    """
    Abstract Base Class for theme slot animations.
    Rule: Zero allocations in paint(). Everything built in prepare().
    """

    def __init__(self) -> None:
        self.lod_low: bool = False
        self.error_count: int = 0
        self.disabled: bool = False
        self._paint_times: list[float] = []
        self._frame_count: int = 0

    @abstractmethod
    def prepare(self, palette: PaletteDefinition, rect: QRectF) -> None:
        """
        Build pens, brushes, paths, static geometry, and fonts once.
        Called on initialisation, theme change, and resize.
        """
        pass

    @abstractmethod
    def tick(self, dt: float, signals: HudSignals) -> None:
        """
        Advance internal numeric/geometric state. Zero painting, zero allocation.
        """
        pass

    @abstractmethod
    def paint(self, painter: QPainter, rect: QRectF) -> None:
        """
        Draw using prebuilt objects only. Zero allocations.
        """
        pass

    def dispose(self) -> None:
        """Clean up references and cached native objects when unmounting."""
        pass

    def describe(self) -> str:
        """One-line description for telemetry/debug panel."""
        return self.__class__.__name__

    def record_paint_time(self, duration_ms: float) -> None:
        """Watchdog to degrade LOD if mean frame time exceeds budget, with recovery."""
        self._paint_times.append(duration_ms)
        if len(self._paint_times) > BUDGET_WINDOW_FRAMES:
            self._paint_times.pop(0)
            avg = sum(self._paint_times) / len(self._paint_times)
            if avg > SLOT_PAINT_BUDGET_MS and not self.lod_low:
                self.lod_low = True
                print(f"[HUD Watchdog] Visual '{self.describe()}' paint time ({avg:.2f}ms) exceeded budget ({SLOT_PAINT_BUDGET_MS}ms). Degrading to LOD_LOW.")
            elif avg < (SLOT_PAINT_BUDGET_MS * 0.65) and self.lod_low:
                self.lod_low = False
