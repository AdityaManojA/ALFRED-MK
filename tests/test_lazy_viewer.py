"""
tests/test_lazy_viewer.py — Unit tests for lazy construction and memory release of Image Viewer v2.
"""

import sys
import unittest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImage, QColor

from core.registry import lookup, unregister
from core.image_viewer import get_image_viewer, ImageViewerWindow


class TestLazyViewer(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        unregister("image_viewer")

    def tearDown(self):
        viewer = lookup("image_viewer")
        if viewer is not None:
            viewer.close_viewer()
            viewer.deleteLater()
        unregister("image_viewer")

    def test_clean_boot_constructs_no_viewer(self):
        """Assert that clean boot leaves the viewer unconstructed in the registry."""
        self.assertIsNone(
            lookup("image_viewer"),
            "image_viewer must NOT be constructed or registered at boot",
        )

    def test_first_request_lazily_creates_viewer(self):
        """First call to get_image_viewer constructs and registers the viewer."""
        self.assertIsNone(lookup("image_viewer"))
        viewer = get_image_viewer()
        self.assertIsNotNone(viewer)
        self.assertIsInstance(viewer, ImageViewerWindow)
        # It must be registered
        self.assertIs(lookup("image_viewer"), viewer)
        # Hidden by default before explicit show_image
        self.assertFalse(viewer.isVisible())

    def test_show_and_close_releases_memory(self):
        """Showing an image allocates pixmap; closing viewer frees the pixmap and raw image."""
        viewer = get_image_viewer()

        # Create a small in-memory test image
        img = QImage(200, 150, QImage.Format.Format_RGB32)
        img.fill(QColor("blue"))

        shown = viewer.show_image(img, caption="test", host="test.org")
        self.assertTrue(shown)
        self.assertIsNotNone(viewer._canvas._raw_image)
        self.assertIsNotNone(viewer._canvas._cached_pixmap)

        # Close viewer
        viewer.close_viewer()
        self.assertFalse(viewer.isVisible())
        # Assert memory freed
        self.assertIsNone(viewer._canvas._raw_image)
        self.assertIsNone(viewer._canvas._cached_pixmap)
        self.assertEqual(viewer._native_size, (0, 0))


if __name__ == "__main__":
    unittest.main()
