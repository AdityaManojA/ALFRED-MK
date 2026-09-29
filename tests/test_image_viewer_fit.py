"""
tests/test_image_viewer_fit.py — Unit tests for Image Viewer v2 geometric fitting.
"""

import unittest

from core.image_viewer.fit import (
    fit_size,
    VIEWER_MAX_SCREEN_FRAC,
    VIEWER_MIN_PX,
    VIEWER_MAX_DECODE_PX,
)


class TestImageViewerFit(unittest.TestCase):

    def test_native_fitting_landscape(self):
        """Image smaller than screen max bounds stays at native size."""
        w, h = fit_size(800, 500, 1920, 1080)
        self.assertEqual((w, h), (800, 500))

    def test_native_fitting_square(self):
        """Square image smaller than screen stays at native size."""
        w, h = fit_size(600, 600, 1920, 1080)
        self.assertEqual((w, h), (600, 600))

    def test_oversized_landscape_downscaling(self):
        """Large landscape image is downscaled to fit screen bounds without cropping."""
        avail_w, avail_h = 1920, 1080
        max_w = int(avail_w * VIEWER_MAX_SCREEN_FRAC)   # 1632
        max_h = int(avail_h * VIEWER_MAX_SCREEN_FRAC)   # 918

        w, h = fit_size(3000, 1500, avail_w, avail_h)  # 2:1 aspect ratio
        self.assertLessEqual(w, max_w)
        self.assertLessEqual(h, max_h)
        # Verify 2:1 aspect ratio preserved within rounding tolerance
        self.assertAlmostEqual(w / h, 2.0, delta=0.01)

    def test_oversized_portrait_downscaling(self):
        """Tall portrait image is constrained by max screen height."""
        avail_w, avail_h = 1920, 1080
        max_h = int(avail_h * VIEWER_MAX_SCREEN_FRAC)   # 918

        w, h = fit_size(1000, 2000, avail_w, avail_h)  # 1:2 aspect ratio
        self.assertLessEqual(h, max_h)
        self.assertEqual(h, max_h)
        self.assertAlmostEqual(w / h, 0.5, delta=0.01)

    def test_8k_image_downscaling(self):
        """8K image (7680x4320) is downscaled and fits screen with no off-screen overflow."""
        avail_w, avail_h = 1920, 1080
        max_w = int(avail_w * VIEWER_MAX_SCREEN_FRAC)
        max_h = int(avail_h * VIEWER_MAX_SCREEN_FRAC)

        w, h = fit_size(7680, 4320, avail_w, avail_h)  # 16:9
        self.assertLessEqual(w, max_w)
        self.assertLessEqual(h, max_h)
        self.assertAlmostEqual(w / h, 16 / 9, delta=0.02)

    def test_tiny_image_meets_minimum_px(self):
        """Tiny images (e.g. 50x50, 64x32) meet VIEWER_MIN_PX while keeping aspect ratio."""
        w, h = fit_size(50, 50, 1920, 1080)
        self.assertGreaterEqual(w, VIEWER_MIN_PX)
        self.assertGreaterEqual(h, VIEWER_MIN_PX)
        self.assertAlmostEqual(w / h, 1.0, delta=0.01)

        w2, h2 = fit_size(60, 30, 1920, 1080)  # 2:1
        self.assertGreaterEqual(max(w2, h2), VIEWER_MIN_PX)
        self.assertAlmostEqual(w2 / h2, 2.0, delta=0.02)

    def test_invalid_dimensions(self):
        """Zero or negative dimensions return minimum size safely."""
        w, h = fit_size(0, 0, 1920, 1080)
        self.assertEqual((w, h), (VIEWER_MIN_PX, VIEWER_MIN_PX))


if __name__ == "__main__":
    unittest.main()
