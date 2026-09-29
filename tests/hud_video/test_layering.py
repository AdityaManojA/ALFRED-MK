"""
tests/hud_video/test_layering.py — Headless verification of Z-order constants, overlay raising, and minimize session state.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QWidget

_app = QApplication.instance()
if _app is None:
    _app = QApplication(["test", "-platform", "offscreen"])

from core.hud_video.layering import (
    Z_VISUAL_HUD,
    Z_HUD_BUTTONS,
    Z_DROPDOWN_CARD_TOAST,
    Z_SETTINGS_MODAL,
    raise_overlay,
    make_frameless_overlay,
)
from core.hud_video.controller import HudVideoController, VideoStatus, VideoState
from core.hud_video.resolve import PlayableRef


class TestLayering(unittest.TestCase):

    def test_z_constants_ordering(self):
        """Verify strict ordering: Z_VISUAL_HUD < Z_HUD_BUTTONS < Z_DROPDOWN_CARD_TOAST < Z_SETTINGS_MODAL."""
        self.assertLess(Z_VISUAL_HUD, Z_HUD_BUTTONS)
        self.assertLess(Z_HUD_BUTTONS, Z_DROPDOWN_CARD_TOAST)
        self.assertLess(Z_DROPDOWN_CARD_TOAST, Z_SETTINGS_MODAL)

    def test_raise_overlay_shows_and_raises(self):
        parent = QWidget()
        parent.show()
        overlay = QWidget(parent)
        self.assertFalse(overlay.isVisible())

        raise_overlay(overlay, parent)
        self.assertTrue(overlay.isVisible())

    def test_make_frameless_overlay_flags(self):
        parent = QWidget()
        overlay = QWidget()
        make_frameless_overlay(overlay, parent)

        flags = overlay.windowFlags()
        self.assertTrue(bool(flags & Qt.WindowType.FramelessWindowHint))
        self.assertTrue(bool(flags & Qt.WindowType.Tool))

    def test_minimize_and_restore_state_preservation(self):
        """Minimise should pause playing video and restore it; paused video stays paused."""
        controller = HudVideoController()
        ref = PlayableRef(
            kind="direct_url",
            uri="https://stream.cdn/video.mp4",
            title="Sample Video",
        )

        controller.play(ref)
        controller.on_backend_duration(100.0)
        controller.on_backend_ready()
        self.assertEqual(controller.state().status, VideoStatus.PLAYING)

        # Minimise window
        controller.on_minimise()
        self.assertEqual(controller.state().status, VideoStatus.PAUSED)

        # Restore window
        controller.on_restore()
        self.assertEqual(controller.state().status, VideoStatus.PLAYING)

        # If already paused before minimise:
        controller.pause()
        self.assertEqual(controller.state().status, VideoStatus.PAUSED)
        controller.on_minimise()
        self.assertEqual(controller.state().status, VideoStatus.PAUSED)
        controller.on_restore()
        # Should stay paused because it was NOT playing when minimised
        self.assertEqual(controller.state().status, VideoStatus.PAUSED)


if __name__ == "__main__":
    unittest.main()
