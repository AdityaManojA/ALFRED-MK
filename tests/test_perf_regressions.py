"""
tests/test_perf_regressions.py — Guards for the 2026-11-03 performance pass.

Each test pins one fix so it cannot quietly come back:

- Startup: importing main/wake_word must not load openwakeword (and with it
  scikit-learn, SciPy and pandas, ~2.4 s). Checked in a fresh interpreter,
  because this test process may already have them imported.
- wake_word.is_ready() must not import openwakeword either; it is called from
  the GUI thread and only needs the package's folder on disk.
- _ensure_openwakeword() stays safe when many worker threads call it at once.
- qcol() caches the hex parse but must hand out copies, so a caller's
  setAlpha() cannot change the colour every other caller gets.
- LogWidget's pending queue is a deque consumed FIFO (no list.pop(0)).
- requirements.txt pins edge-tts at a version Microsoft's service accepts.
- The UI profiler keeps one psutil.Process so CPU readings are real.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import unittest
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _fresh_python(code: str, timeout: float = 120.0) -> subprocess.CompletedProcess:
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONIOENCODING="utf-8")
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=timeout,
    )


class TestStartupImports(unittest.TestCase):

    def test_wake_word_import_does_not_load_openwakeword(self):
        r = _fresh_python(
            "import sys, core.wake_word\n"
            "print('OWW' if 'openwakeword' in sys.modules else 'no-oww')\n"
            "print('SKL' if 'sklearn' in sys.modules else 'no-skl')\n"
        )
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        self.assertIn("no-oww", r.stdout)
        self.assertIn("no-skl", r.stdout)

    def test_main_import_does_not_load_openwakeword(self):
        r = _fresh_python(
            "import sys, main\n"
            "print('OWW' if 'openwakeword' in sys.modules else 'no-oww')\n"
            "print('SKL' if 'sklearn' in sys.modules else 'no-skl')\n",
            timeout=180.0,
        )
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        self.assertIn("no-oww", r.stdout)
        self.assertIn("no-skl", r.stdout)

    def test_is_ready_does_not_import_openwakeword(self):
        r = _fresh_python(
            "import sys\n"
            "from core.wake_word import is_ready\n"
            "is_ready()\n"
            "print('OWW' if 'openwakeword' in sys.modules else 'no-oww')\n"
        )
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        self.assertIn("no-oww", r.stdout)


class TestOpenWakeWordLazyImport(unittest.TestCase):

    def test_package_dir_located_without_import(self):
        import importlib.util
        from core.wake_word import _openwakeword_package_dir
        if importlib.util.find_spec("openwakeword") is None:
            self.assertIsNone(_openwakeword_package_dir())
            return
        pkg = _openwakeword_package_dir()
        self.assertIsNotNone(pkg)
        self.assertTrue((pkg / "__init__.py").is_file())

    def test_concurrent_ensure_returns_one_complete_module(self):
        import importlib.util
        if importlib.util.find_spec("openwakeword") is None:
            self.skipTest("openwakeword not installed")
        from core.wake_word import _ensure_openwakeword

        results, errors = [], []
        start = threading.Barrier(8)

        def worker():
            try:
                start.wait(timeout=30)
                results.append(_ensure_openwakeword())
            except Exception as e:  # pragma: no cover - reported below
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=120)

        self.assertFalse(errors, errors)
        self.assertEqual(len(results), 8)
        self.assertTrue(all(m is not None for m in results))
        self.assertEqual(len({id(m) for m in results}), 1)
        # Fully initialised, not a half-imported module.
        self.assertTrue(hasattr(results[0], "get_pretrained_model_paths"))


class TestUiHotPaths(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication([])

    def test_qcol_returns_independent_copies(self):
        from ui import qcol
        a = qcol("#00f0ff", 200)
        a.setAlpha(10)
        a.setRed(1)
        b = qcol("#00f0ff", 200)
        self.assertEqual(b.alpha(), 200)
        self.assertEqual(b.red(), 0x00)
        self.assertEqual(b.green(), 0xF0)
        self.assertIsNot(a, b)

    def test_qcol_matches_uncached_parse(self):
        from PyQt6.QtGui import QColor
        from ui import qcol
        for h, alpha in (("#ff2a6d", 255), ("#05d9e8", 128), ("#000000", 0)):
            ref = QColor(h)
            ref.setAlpha(alpha)
            self.assertEqual(qcol(h, alpha).rgba(), ref.rgba())

    def test_log_widget_queue_is_fifo_deque(self):
        from ui import LogWidget
        w = LogWidget()
        try:
            self.assertIsInstance(w._queue, deque)
            w._typing = True          # hold the typing loop so items stay queued
            for line in ("SYS: one", "SYS: two", "SYS: three"):
                w._enqueue(line)
            w._typing = False
            w._next()
            self.assertEqual(w._text, "SYS: one")
            self.assertEqual(list(w._queue), ["SYS: two", "SYS: three"])
        finally:
            w._tmr.stop()
            w.deleteLater()


class TestDependencyPins(unittest.TestCase):

    def test_edge_tts_pinned_to_working_version(self):
        text = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        m = re.search(r"^edge-tts>=(\d+)\.(\d+)\.(\d+)", text, re.MULTILINE)
        self.assertIsNotNone(m, "edge-tts missing from requirements.txt")
        self.assertGreaterEqual(tuple(int(x) for x in m.groups()), (7, 3, 1))


class TestProfilerProbe(unittest.TestCase):

    def test_profiler_reuses_one_process_object(self):
        try:
            import psutil  # noqa: F401
        except ImportError:
            self.skipTest("psutil not installed")
        sys.path.insert(0, str(ROOT / "tools"))
        try:
            import profile_alfred_ui as prof
        finally:
            sys.path.pop(0)
        self.assertIs(prof._probe_process(), prof._probe_process())


if __name__ == "__main__":
    unittest.main()
