"""
tests/hud_visuals/test_visuals.py — Automated verification suite for HUD Visuals v1.
Covers:
  - Registry completeness (theme_id × slot_index resolution)
  - Headless QImage rendering smoke across multiple aspect ratios
  - Zero-allocation paint checks (tracemalloc delta ≈ 0)
  - Performance watchdog budget demotion to LOD_LOW
  - Central skin resolution
  - DeveloperDataGridWidget snapshot handling and changes
"""
import sys
import time
import tracemalloc
import unittest
from pathlib import Path

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter

from core.hud.datagrid.providers import DataGridWorker, GridDataSnapshot
from core.hud.visuals import HudSignals, SlotVisual, get_visual_class, instantiate_visual
from core.hud.visuals.base import (
    ALLOC_TOLERANCE_BYTES,
    BUDGET_WINDOW_FRAMES,
    SLOT_PAINT_BUDGET_MS,
    TRIG_STEPS,
    fast_cos,
    fast_sin,
)
from core.hud.visuals.central import CentralSkin, get_central_skin
from core.ui.themes import ThemeChrome
from core.ui.themes.schema import PaletteDefinition


app = QGuiApplication.instance() or QGuiApplication(sys.argv)


class TestHudVisualsCore(unittest.TestCase):
    def setUp(self):
        self.palette = ThemeChrome.get_active().palette

    def test_trig_lookup_accuracy(self):
        """Precomputed trig tables must be smooth and fast."""
        import math
        for deg in (0, 30, 45, 90, 180, 270, 360):
            rad = math.radians(deg)
            s_fast = fast_sin(rad)
            c_fast = fast_cos(rad)
            self.assertAlmostEqual(s_fast, math.sin(rad), delta=0.05)
            self.assertAlmostEqual(c_fast, math.cos(rad), delta=0.05)

    def test_registry_completeness(self):
        """Every registered (theme_id, slot) pair must resolve and instantiate."""
        all_themes = [
            "dossier", "catwoman", "vector", "beyond",
            "mr_freeze", "joker", "harvey_two_face", "arkham", "watchtower", "riddler",
        ]
        for theme_id in all_themes:
            for slot_idx in range(3):
                cls = get_visual_class(theme_id, slot_idx)
                self.assertIsNotNone(cls, f"Missing class for {theme_id}:{slot_idx}")
                instance = instantiate_visual(theme_id, slot_idx)
                self.assertIsInstance(instance, SlotVisual)
                instance.dispose()

    def test_headless_paint_smoke_all_visuals(self):
        """Paint all visuals on diverse viewport geometries for 30 ticks without crash."""
        all_themes = [
            "dossier", "catwoman", "vector", "beyond",
            "mr_freeze", "joker", "harvey_two_face", "arkham", "watchtower", "riddler",
        ]
        sizes = [(100, 80), (200, 120), (320, 200), (400, 60)]  # small, default, large, extreme-aspect

        signals = HudSignals(cpu_pct=42.0, mem_pct=60.0, alert_level=1)

        for theme_id in all_themes:
            for slot_idx in range(3):
                visual = instantiate_visual(theme_id, slot_idx)
                for w, h in sizes:
                    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
                    img.fill(Qt.GlobalColor.black)
                    rect = QRectF(0.0, 0.0, float(w), float(h))
                    visual.prepare(self.palette, rect)

                    p = QPainter(img)
                    for _ in range(30):
                        visual.tick(0.033, signals)
                        visual.paint(p, rect)
                    p.end()
                    self.assertFalse(visual.disabled, f"Visual {visual.describe()} tripped error boundary")
                visual.dispose()

    def test_zero_allocations_in_paint(self):
        """Verify that paint() performs zero/minimal allocations in steady state."""
        visual = instantiate_visual("dossier", 0)
        w, h = 240, 140
        img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        rect = QRectF(0.0, 0.0, float(w), float(h))
        visual.prepare(self.palette, rect)
        signals = HudSignals(cpu_pct=25.0)

        p = QPainter(img)
        # Warm up JIT/caches
        for _ in range(50):
            visual.tick(0.033, signals)
            visual.paint(p, rect)

        tracemalloc.start()
        snapshot1 = tracemalloc.take_snapshot()

        for _ in range(300):
            visual.tick(0.033, signals)
            visual.paint(p, rect)

        snapshot2 = tracemalloc.take_snapshot()
        tracemalloc.stop()

        top_stats = snapshot2.compare_to(snapshot1, 'lineno')
        total_delta = sum(stat.size_diff for stat in top_stats if stat.size_diff > 0)
        p.end()
        visual.dispose()

        # Delta should be well within ALLOC_TOLERANCE_BYTES
        self.assertLess(total_delta, ALLOC_TOLERANCE_BYTES, f"Excessive allocation in paint(): {total_delta} bytes")

    def test_paint_budget_watchdog_auto_degrade(self):
        """Visual exceeding SLOT_PAINT_BUDGET_MS drops to lod_low."""
        class SlowVisual(SlotVisual):
            def prepare(self, palette, rect):
                pass

            def tick(self, dt, signals):
                pass

            def paint(self, painter, rect):
                pass

        slow = SlowVisual()
        rect = QRectF(0.0, 0.0, 100.0, 100.0)
        slow.prepare(self.palette, rect)
        self.assertFalse(slow.lod_low)

        for _ in range(BUDGET_WINDOW_FRAMES + 5):
            slow.record_paint_time(SLOT_PAINT_BUDGET_MS + 1.5)

        self.assertTrue(slow.lod_low)

    def test_central_skin_resolver(self):
        """Central skin parameters must exist and vary by theme."""
        skins = {
            t: get_central_skin(t)
            for t in ["dossier", "catwoman", "vector", "beyond", "mr_freeze", "joker", "watchtower"]
        }
        self.assertEqual(skins["dossier"].ring_count, 7)
        self.assertEqual(skins["vector"].ring_count, 9)
        self.assertEqual(skins["catwoman"].ring_count, 5)
        self.assertEqual(skins["joker"].orbit_nodes, ("HA", "HA", "HA", "HA"))

    def test_data_grid_snapshot_dataclass(self):
        """GridDataSnapshot holds formatted strings and styling states."""
        snap = GridDataSnapshot(
            git_text="main • 2 mod",
            git_state="accent",
            ports_text="11434 · 8000",
            ports_state="accent",
            proc_text="code.exe • 420 MB",
            proc_state="accent",
            session_text="00:02:05 • 18.4k tok",
            session_state="accent",
        )
        self.assertEqual(snap.git_text, "main • 2 mod")
        self.assertEqual(snap.ports_text, "11434 · 8000")
        self.assertEqual(snap.proc_text, "code.exe • 420 MB")
        self.assertEqual(snap.session_text, "00:02:05 • 18.4k tok")


if __name__ == "__main__":
    unittest.main()
